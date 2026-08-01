"""docker logs 透传服务 — 用 Python docker SDK 走 Unix socket 调 docker daemon。

2026-07-23 patch (FE-160 ext): 让前端能在 /logs 页面看 backend 之外的所有容器
日志 (airflow-scheduler, airflow-webserver, postgres, redis, etl-cron 等)。

设计取舍 (rev2):
- 不用 docker CLI subprocess (镜像装 docker CLI 麻烦, Debian docker.io 只给 daemon)
- 用 Python `docker` lib 直接连 /var/run/docker.sock 走 HTTP API
- 容器名白名单 + 服务名映射, 不暴露整个 docker 表面
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# 延迟加载 docker (避免没装时 import 报错)
_client = None


def _get_client():
    """懒加载 DockerClient (单例)。"""
    global _client
    if _client is None:
        import docker
        _client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
    return _client


# 服务名 → docker 容器名 (跟 infra/docker-compose.yml 一致)
SERVICE_TO_CONTAINER: dict[str, str] = {
    "backend": "hunter_backend",
    "airflow-scheduler": "hunter_airflow_sched",
    "airflow-webserver": "hunter_airflow_web",
    "postgres": "hunter_postgres",
    "redis": "hunter_redis",
    "airflow-db": "hunter_airflow_db",
    "etl-cron": "hunter_etl_cron",
}


# airflow logger 内嵌时间戳 prefix: "[2026-07-22T22:52:57.910+0000]"
_INNER_TS_RE = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\]\s*"
)
# structlog 的 "{filename.py:801} " 前缀
_FILE_PREFIX_RE = re.compile(r"^\{[^}]+\}\s*")
# "LEVEL - " 或 "LEVEL: " 前缀
_LEVEL_PREFIX_RE = re.compile(
    r"^(INFO|WARNING|WARN|ERROR|DEBUG|CRITICAL)[\s\-:]+",
    re.IGNORECASE,
)


def _infer_level(text: str) -> str:
    """从一行日志里猜 level。"""
    upper = text.upper()
    if "CRITICAL" in upper or "FATAL" in upper:
        return "CRITICAL"
    if "ERROR" in upper or "EXCEPTION" in upper or "TRACEBACK" in upper:
        return "ERROR"
    if "WARNING" in upper or "WARN:" in upper or "[WARN" in upper:
        return "WARNING"
    if "DEBUG" in upper or "[DEBUG" in upper:
        return "DEBUG"
    if "INFO" in upper or "[INFO" in upper:
        return "INFO"
    return "INFO"


def _clean_msg(text: str) -> str:
    """清理常见 log prefix。"""
    text = _INNER_TS_RE.sub("", text)
    text = _FILE_PREFIX_RE.sub("", text)
    text = _LEVEL_PREFIX_RE.sub("", text)
    return text.strip()


def _parse_line(raw: str, container: str) -> dict | None:
    """解析 docker logs 一行 → LogEntry dict。

    docker logs --timestamps 输出格式: "2026-07-23T06:42:15.123456789Z <msg>"
    容器内可能输出额外 prefix, 都要剥掉。
    """
    line = raw.rstrip("\n")
    if not line.strip():
        return None

    # docker daemon 给的时间戳 (RFC3339Nano)
    ts = ""
    rest = line
    if line and line[0].isdigit() and "T" in line[:30]:
        # 找第一个空格 — 时间戳结束
        sp = line.find(" ")
        if sp > 0:
            ts = line[:sp]
            rest = line[sp + 1:]

    level = _infer_level(rest)
    msg = _clean_msg(rest)

    return {
        "ts": ts,
        "level": level,
        "msg": msg,
        "source": "docker",
        "raw": line,
        "container": container,
    }


def tail_container_logs(
    container: str,
    tail: int = 500,
    since: str | None = None,
    timeout_sec: float = 30.0,
) -> list[dict]:
    """读 docker 容器最近 N 行日志。

    Args:
        container: docker 容器名 (从 SERVICE_TO_CONTAINER 映射)
        tail: 最多返回多少行 (1-5000)
        since: RFC3339 时间, e.g. "2026-07-23T06:00:00"
        timeout_sec: HTTP 请求超时

    Returns:
        LogEntry 字典列表 (按时间倒序, 最新在前)
    """
    allowed = set(SERVICE_TO_CONTAINER.values())
    if container not in allowed:
        raise ValueError(
            f"container '{container}' not in whitelist. Allowed: {sorted(allowed)}"
        )

    client = _get_client()
    try:
        container_obj = client.containers.get(container)
    except Exception as e:
        raise RuntimeError(f"container {container} not found: {e}") from e

    kwargs: dict = {"timestamps": True, "tail": min(tail, 5000)}
    if since:
        kwargs["since"] = since

    try:
        raw_bytes = container_obj.logs(**kwargs)
    except Exception as e:
        raise RuntimeError(f"docker logs failed: {e}") from e

    # raw_bytes 是 generator/bytes, 逐行 split
    if isinstance(raw_bytes, bytes):
        text = raw_bytes.decode("utf-8", errors="replace")
    else:
        text = str(raw_bytes)

    entries: list[dict] = []
    for line in text.splitlines():
        e = _parse_line(line, container)
        if e:
            entries.append(e)

    entries.reverse()  # 最新在前
    return entries


def list_services() -> list[dict]:
    """列出可用的日志服务 (供前端下拉)。"""
    return [
        {"service": svc, "container": ctr, "label": _label_for(svc)}
        for svc, ctr in SERVICE_TO_CONTAINER.items()
    ]


def _label_for(service: str) -> str:
    LABELS = {
        "backend": "Backend (FastAPI + ETL)",
        "airflow-scheduler": "Airflow Scheduler (DAG 调度)",
        "airflow-webserver": "Airflow Webserver (UI/API)",
        "postgres": "PostgreSQL",
        "redis": "Redis",
        "airflow-db": "Airflow Metadata DB",
        "etl-cron": "ETL Cron",
    }
    return LABELS.get(service, service)


__all__ = [
    "SERVICE_TO_CONTAINER",
    "tail_container_logs",
    "list_services",
]