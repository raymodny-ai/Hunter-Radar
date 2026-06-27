"""m19t5 V1.6.0 P2 Docker 部署自测(25 测点)。

Section 1: Dockerfile 结构 (5)
Section 2: docker-compose 服务定义 (5)
Section 3: 健康检查 + 网络 (5)
Section 4: control.sh 命令 (5)
Section 5: 环境变量 + volumes (5)

静态分析为主。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
INFRA = ROOT / "infra"
DOCKER_DIR = ROOT / "docker"

PASS = "[PASS]"
FAIL = "[FAIL]"
_passed = 0
_total = 0


def t(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _total
    _total += 1
    if ok:
        _passed += 1
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)


# ============================================================
# Section 1: Dockerfile 结构 (5)
# ============================================================
def test_dockerfile() -> None:
    print("\n=== Section 1: Dockerfile 结构 (5) ===", flush=True)
    fp = BACKEND / "Dockerfile"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: Dockerfile 存在
    t("docker_file_exists", fp.exists(), str(fp))

    # t2: 多阶段构建(FROM ... AS)
    t("docker_multi_stage", "FROM" in src and "AS" in src)

    # t3: python:3.14-slim 基础镜像
    t("docker_base_image", "python:3.14-slim" in src or "python:3" in src)

    # t4: 非 root 用户(USER)
    t("docker_non_root", "USER" in src and ("hunter" in src or "nonroot" in src or "app" in src))

    # t5: HEALTHCHECK
    t("docker_healthcheck", "HEALTHCHECK" in src)


# ============================================================
# Section 2: docker-compose 服务定义 (5)
# ============================================================
def test_compose() -> None:
    print("\n=== Section 2: docker-compose 服务定义 (5) ===", flush=True)
    fp = INFRA / "docker-compose.yml"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: compose 文件存在
    t("compose_exists", fp.exists(), str(fp))

    # t2: backend 服务
    t("compose_backend", "backend:" in src and "container_name" in src)

    # t3: postgres 服务
    t("compose_postgres", "postgres:" in src and "postgres:16" in src)

    # t4: redis 服务
    t("compose_redis", "redis:" in src and "redis:7" in src)

    # t5: etl-cron 服务
    t("compose_etl_cron", "etl-cron:" in src or "etl_cron:" in src)


# ============================================================
# Section 3: 健康检查 + 网络 (5)
# ============================================================
def test_health_network() -> None:
    print("\n=== Section 3: 健康检查 + 网络 (5) ===", flush=True)
    fp = INFRA / "docker-compose.yml"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: hunter-net 网络
    t("net_hunter_net", "hunter-net" in src)

    # t2: 健康检查
    t("net_healthcheck", "healthcheck:" in src)

    # t3: backend 健康检查路径
    t("net_backend_health", "/health" in src)

    # t4: depends_on
    t("net_depends_on", "depends_on:" in src and "condition: service_healthy" in src)

    # t5: 端口映射
    t("net_port_mapping", "8000:8000" in src)


# ============================================================
# Section 4: control.sh 命令 (5)
# ============================================================
def test_control_script() -> None:
    print("\n=== Section 4: control.sh 命令 (5) ===", flush=True)
    fp = DOCKER_DIR / "control.sh"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: control.sh 存在
    t("ctrl_exists", fp.exists(), str(fp))

    # t2: start 命令
    t("ctrl_start", "start)" in src)

    # t3: stop 命令
    t("ctrl_stop", "stop)" in src)

    # t4: migrate 命令
    t("ctrl_migrate", "migrate)" in src)

    # t5: logs 命令
    t("ctrl_logs", "logs)" in src)


# ============================================================
# Section 5: 环境变量 + volumes (5)
# ============================================================
def test_env_volumes() -> None:
    print("\n=== Section 5: 环境变量 + volumes (5) ===", flush=True)
    compose_fp = INFRA / "docker-compose.yml"
    compose_src = compose_fp.read_text(encoding="utf-8") if compose_fp.exists() else ""

    # t1: DATABASE_URL 环境变量
    t("env_database_url", "DATABASE_URL" in compose_src)

    # t2: REDIS_URL 环境变量
    t("env_redis_url", "REDIS_URL" in compose_src)

    # t3: volumes 定义
    t("env_volumes", "volumes:" in compose_src and "hunter_pg_data" in compose_src)

    # t4: Redis 数据持久化
    t("env_redis_persist", "redis_data" in compose_src or "appendonly" in compose_src)

    # t5: .dockerignore 存在
    dockerignore = BACKEND / ".dockerignore"
    t("env_dockerignore", dockerignore.exists(), str(dockerignore))


# ============================================================
# main
# ============================================================
def main() -> int:
    test_dockerfile()
    test_compose()
    test_health_network()
    test_control_script()
    test_env_volumes()

    print(flush=True)
    ok = _passed == _total
    if ok:
        print(f"[m19t5] {_passed}/{_total} ALL PASSED")
    else:
        print(f"[m19t5] {_passed}/{_total} ({_total - _passed} FAILED)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
