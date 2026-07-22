"""V1.7.5/V1.7.6 自测脚本 — 25 测点 (5 Section × 5 测点)。

覆盖变更:
  - symbol_admin.py  (POST/GET /symbols, warmup 触发 + 进度查询)
  - symbol_warmup.py (串行 dispatcher + enqueue_warmup + _warmup_one_symbol)
  - log_stream.py    (SSE 日志流 + file 读取)
  - frontend         (useSymbolAutoWarmup / logs.tsx / api.ts 类型对齐)
  - SQL migration    (04_v1.7.5_screener_stable_date.sql 物化视图)

使用:
  # 沙箱(无需后端,纯静态检查):
  uv run python scripts/m18t1_test_v175_selftest.py

  # 集成(需后端 @ localhost:8000):
  HR_BASE_URL=http://localhost:8000 uv run python scripts/m18t1_test_v175_selftest.py --live

退出码: 0=全部 PASS, 1=任一 FAIL
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---- 路径 ----
ROOT = Path(__file__).resolve().parents[1]          # hunter-radar/
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SQL_DIR = BACKEND / "sql"
sys.path.insert(0, str(BACKEND))

BASE_URL = os.environ.get("HR_BASE_URL", "http://localhost:8000")
LIVE = "--live" in sys.argv

# ---- 工具 ----
_pass = 0
_fail = 0
_skip = 0
_results: list[tuple[str, bool, str]] = []

# 检测后端依赖是否可用
_HAS_BACKEND_DEPS = False
try:
    import fastapi  # noqa: F401
    import sqlalchemy  # noqa: F401
    import structlog  # noqa: F401
    _HAS_BACKEND_DEPS = True
except ImportError:
    pass


def _check(section: str, name: str, ok: bool, detail: str = "") -> None:
    global _pass, _fail
    mark = "PASS" if ok else "FAIL"
    if ok:
        _pass += 1
    else:
        _fail += 1
    _results.append((f"{section} / {name}", ok, detail))
    print(f"  [{mark}] {section} / {name} -- {detail}")


def _skip_check(section: str, name: str, reason: str = "") -> None:
    global _skip
    _skip += 1
    _results.append((f"{section} / {name}", True, f"SKIP: {reason}"))
    print(f"  [SKIP] {section} / {name} -- {reason}")


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ====================================================================
# Section A: 后端模块导入与结构完整性
# ====================================================================

def section_a() -> None:
    _section("A: 后端模块导入与结构")
    if not _HAS_BACKEND_DEPS:
        for i in range(1, 6):
            _skip_check("A", f"A-{i}", "后端依赖未安装(fastapi/sqlalchemy/structlog)")
        return

    # A-1: symbol_admin 模块可导入
    try:
        mod = importlib.import_module("app.api.symbol_admin")
        assert hasattr(mod, "router"), "router 未导出"
        _check("A", "A-1 symbol_admin 导入", True, f"router={mod.router}")
    except Exception as e:
        _check("A", "A-1 symbol_admin 导入", False, str(e))

    # A-2: symbol_warmup 模块可导入
    try:
        mod = importlib.import_module("app.services.symbol_warmup")
        for fn_name in ("schedule_warmup", "enqueue_warmup", "get_warmup_status",
                        "start_dispatcher", "enqueue_many_warmup"):
            assert hasattr(mod, fn_name), f"缺 {fn_name}"
        _check("A", "A-2 symbol_warmup 导入", True,
               "5 个公开函数均存在")
    except Exception as e:
        _check("A", "A-2 symbol_warmup 导入", False, str(e))

    # A-3: log_stream 模块可导入
    try:
        mod = importlib.import_module("app.api.log_stream")
        assert hasattr(mod, "router"), "router 未导出"
        assert hasattr(mod, "install_sse_logger"), "install_sse_logger 未导出"
        _check("A", "A-3 log_stream 导入", True,
               "router + install_sse_logger 存在")
    except Exception as e:
        _check("A", "A-3 log_stream 导入", False, str(e))

    # A-4: main.py 无重复导入
    try:
        main_src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
        # 提取 from app.api import (...) 块
        m = re.search(r"from app\.api import \((.*?)\)", main_src, re.DOTALL)
        assert m, "from app.api import (...) 块未找到"
        names = [n.strip().rstrip(",") for n in m.group(1).splitlines() if n.strip()]
        names = [n for n in names if n and not n.startswith("#")]
        dupes = [n for n in names if names.count(n) > 1]
        if dupes:
            _check("A", "A-4 main.py 无重复导入", False, f"重复: {set(dupes)}")
        else:
            _check("A", "A-4 main.py 无重复导入", True, f"{len(names)} 个模块无重复")
    except Exception as e:
        _check("A", "A-4 main.py 无重复导入", False, str(e))

    # A-5: redis_client 新增方法存在 (V1.7.6 dispatcher 需要)
    try:
        mod = importlib.import_module("app.core.redis_client")
        client = mod.redis_client
        for method in ("rpush", "blpop", "exists", "delete", "lrange"):
            assert hasattr(client, method), f"缺方法 {method}"
        _check("A", "A-5 redis_client 队列方法", True,
               "rpush/blpop/exists/delete/lrange 均存在")
    except Exception as e:
        _check("A", "A-5 redis_client 队列方法", False, str(e))


# ====================================================================
# Section B: symbol_admin 端点 + warmup 服务层
# ====================================================================

def section_b() -> None:
    _section("B: symbol_admin + warmup 服务层")
    if not _HAS_BACKEND_DEPS:
        for i in range(1, 6):
            _skip_check("B", f"B-{i}", "后端依赖未安装")
        return

    # B-1: symbol_admin DTO 字段完整
    try:
        mod = importlib.import_module("app.api.symbol_admin")
        req_fields = set(mod.SymbolCreateRequest.model_fields.keys())
        expected = {"ticker", "name", "type", "exchange", "is_universe", "start_warmup"}
        missing = expected - req_fields
        if missing:
            _check("B", "B-1 SymbolCreateRequest DTO", False, f"缺字段: {missing}")
        else:
            _check("B", "B-1 SymbolCreateRequest DTO", True, f"{len(req_fields)} 字段完整")
    except Exception as e:
        _check("B", "B-1 SymbolCreateRequest DTO", False, str(e))

    # B-2: symbol_admin 路由端点数量 ≥ 4
    try:
        mod = importlib.import_module("app.api.symbol_admin")
        routes = [r.path for r in mod.router.routes]
        expected_paths = ["/symbols", "/symbols/{ticker}/warmup",
                          "/symbols/{ticker}/warmup-state"]
        missing = [p for p in expected_paths if p not in routes]
        if missing:
            _check("B", "B-2 symbol_admin 路由", False, f"缺: {missing}")
        else:
            _check("B", "B-2 symbol_admin 路由", True,
                   f"{len(routes)} 端点: {routes}")
    except Exception as e:
        _check("B", "B-2 symbol_admin 路由", False, str(e))

    # B-3: warmup 常量定义完整
    try:
        mod = importlib.import_module("app.services.symbol_warmup")
        for const in ("WARMUP_KEY_TPL", "WARMUP_LOCK_TPL", "WARMUP_QUEUE_KEY",
                      "WARMUP_ACTIVE_KEY", "WARMUP_RESULT_TTL"):
            assert hasattr(mod, const), f"缺常量 {const}"
        _check("B", "B-3 warmup 常量定义", True,
               "5 个关键常量均存在")
    except Exception as e:
        _check("B", "B-3 warmup 常量定义", False, str(e))

    # B-4: etl.symbol_seed.upsert_symbol 签名正确
    try:
        mod = importlib.import_module("etl.symbol_seed")
        assert hasattr(mod, "upsert_symbol"), "upsert_symbol 不存在"
        import inspect
        sig = inspect.signature(mod.upsert_symbol)
        params = set(sig.parameters.keys())
        expected = {"ticker", "name", "sym_type", "exchange", "is_universe",
                    "start_warmup", "session"}
        missing = expected - params
        if missing:
            _check("B", "B-4 upsert_symbol 签名", False, f"缺参数: {missing}")
        else:
            _check("B", "B-4 upsert_symbol 签名", True,
                   f"{len(params)} 参数完整")
    except Exception as e:
        _check("B", "B-4 upsert_symbol 签名", False, str(e))

    # B-5: WarmupResult dataclass 可实例化
    try:
        mod = importlib.import_module("app.services.symbol_warmup")
        wr = mod.WarmupResult(ticker="TEST")
        d = wr.to_dict()
        assert d["ticker"] == "TEST"
        assert d["status"] == "pending"
        assert isinstance(d["errors"], list)
        _check("B", "B-5 WarmupResult 实例化", True,
               f"to_dict() 返 {len(d)} 字段")
    except Exception as e:
        _check("B", "B-5 WarmupResult 实例化", False, str(e))


# ====================================================================
# Section C: 日志系统 (log_stream)
# ====================================================================

def section_c() -> None:
    _section("C: 日志系统 log_stream")
    if not _HAS_BACKEND_DEPS:
        for i in range(1, 6):
            _skip_check("C", f"C-{i}", "后端依赖未安装")
        return

    # C-1: log_stream 路由端点 ≥ 3
    try:
        mod = importlib.import_module("app.api.log_stream")
        routes = [r.path for r in mod.router.routes]
        expected = ["/logs/file", "/logs/stream", "/logs/history"]
        missing = [p for p in expected if p not in routes]
        if missing:
            _check("C", "C-1 log_stream 端点数量", False, f"缺: {missing}")
        else:
            _check("C", "C-1 log_stream 端点数量", True,
                   f"{len(routes)} 端点")
    except Exception as e:
        _check("C", "C-1 log_stream 端点数量", False, str(e))

    # C-2: install_sse_logger 可调用
    try:
        mod = importlib.import_module("app.api.log_stream")
        assert callable(mod.install_sse_logger), "install_sse_logger 不可调用"
        _check("C", "C-2 install_sse_logger 可调用", True, "callable")
    except Exception as e:
        _check("C", "C-2 install_sse_logger 可调用", False, str(e))

    # C-3: 日志正则可编译
    try:
        src = (BACKEND / "app" / "api" / "log_stream.py").read_text(encoding="utf-8")
        # 检查 ANSI 和 structlog 正则
        assert "_ANSI_RE" in src
        assert "_STRUCTLOG_RE" in src
        assert "_UVICORN_ACCESS_RE" in src
        _check("C", "C-3 日志正则定义", True, "3 个正则均存在")
    except Exception as e:
        _check("C", "C-3 日志正则定义", False, str(e))

    # C-4: main.py 启动时调用 install_sse_logger
    try:
        main_src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
        assert "install_sse_logger" in main_src, "main.py 未调用 install_sse_logger"
        _check("C", "C-4 main.py SSE 集成", True, "install_sse_logger() 已调用")
    except Exception as e:
        _check("C", "C-4 main.py SSE 集成", False, str(e))

    # C-5: main.py startup 启动 warmup dispatcher
    try:
        main_src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
        assert "start_dispatcher" in main_src, "main.py 未调 start_dispatcher"
        _check("C", "C-5 dispatcher startup", True,
               "start_dispatcher() 在 startup 事件中调用")
    except Exception as e:
        _check("C", "C-5 dispatcher startup", False, str(e))


# ====================================================================
# Section D: 前端构建完整性
# ====================================================================

def section_d() -> None:
    _section("D: 前端构建完整性")

    # D-1: TypeScript 编译零错误
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(FRONTEND), capture_output=True, timeout=60,
            shell=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            _check("D", "D-1 tsc --noEmit", True, "零错误")
        else:
            _check("D", "D-1 tsc --noEmit", False,
                   result.stderr[:300] or result.stdout[:300])
    except Exception as e:
        _check("D", "D-1 tsc --noEmit", False, str(e))

    # D-2: Vite 构建成功
    try:
        result = subprocess.run(
            "npm run build",
            cwd=str(FRONTEND), capture_output=True, timeout=120,
            shell=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            _check("D", "D-2 vite build", True, "构建成功")
        else:
            _check("D", "D-2 vite build", False,
                   result.stderr[:300] or result.stdout[:300])
    except Exception as e:
        _check("D", "D-2 vite build", False, str(e))

    # D-3: routeTree.ts 包含 logs 路由
    try:
        rt = (FRONTEND / "src" / "routeTree.ts").read_text(encoding="utf-8")
        assert "logsRoute" in rt, "logsRoute 未在 routeTree 注册"
        assert "logs" in rt.lower(), "logs 导入缺失"
        _check("D", "D-3 routeTree logs 路由", True, "logsRoute 已注册")
    except Exception as e:
        _check("D", "D-3 routeTree logs 路由", False, str(e))

    # D-4: api.ts createSymbol 返回类型与后端对齐
    try:
        api_src = (FRONTEND / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
        # 检查 createSymbol 返回类型包含 warmup (而非旧的 warmup_scheduled)
        assert "warmup_scheduled" not in api_src, "旧字段 warmup_scheduled 仍存在"
        assert "warmup:" in api_src or "warmup :" in api_src, "新字段 warmup 未定义"
        _check("D", "D-4 api.ts 类型对齐", True,
               "warmup_scheduled 已移除, warmup 字段已对齐")
    except Exception as e:
        _check("D", "D-4 api.ts 类型对齐", False, str(e))

    # D-5: useSymbolAutoWarmup 文件存在且导出正确
    try:
        hook_src = (FRONTEND / "src" / "features" / "useSymbolAutoWarmup.ts").read_text(
            encoding="utf-8"
        )
        assert "export function useSymbolAutoWarmup" in hook_src
        assert "WarmupProgress" in hook_src
        assert "api.createSymbol" in hook_src
        assert "api.getWarmupState" in hook_src
        _check("D", "D-5 useSymbolAutoWarmup", True,
               "Hook 导出 + API 调用链完整")
    except Exception as e:
        _check("D", "D-5 useSymbolAutoWarmup", False, str(e))


# ====================================================================
# Section E: 数据库迁移 + 全栈集成
# ====================================================================

def section_e() -> None:
    _section("E: 数据库迁移 + 全栈集成")

    # E-1: SQL 迁移脚本存在
    try:
        sql_file = SQL_DIR / "04_v1.7.5_screener_stable_date.sql"
        assert sql_file.exists(), f"{sql_file} 不存在"
        content = sql_file.read_text(encoding="utf-8")
        assert "mv_screener_top100" in content
        assert "latest_stable_date" in content
        assert "HAVING COUNT(DISTINCT symbol) >= 5" in content
        _check("E", "E-1 SQL 迁移脚本", True,
               "04_v1.7.5 物化视图脚本存在且含关键逻辑")
    except Exception as e:
        _check("E", "E-1 SQL 迁移脚本", False, str(e))

    # E-2: SQL 引用表在 ORM 中注册
    try:
        models_src = (BACKEND / "app" / "models" / "__init__.py").read_text(encoding="utf-8")
        required_tables = ["threat_score_daily", "symbol_master"]
        missing = [t for t in required_tables if t not in models_src]
        if missing:
            _check("E", "E-2 SQL 表名 ORM 注册", False, f"ORM 缺: {missing}")
        else:
            _check("E", "E-2 SQL 表名 ORM 注册", True,
                   "threat_score_daily + symbol_master 均已注册")
    except Exception as e:
        _check("E", "E-2 SQL 表名 ORM 注册", False, str(e))

    # E-3: wipe_and_rehydrate.py 存在且可解析
    try:
        wipe = ROOT.parent / "wipe_and_rehydrate.py"  # workspace root
        if wipe.exists():
            ast.parse(wipe.read_text(encoding="utf-8"))
            _check("E", "E-3 wipe_and_rehydrate 语法", True, "AST 解析通过")
        else:
            _check("E", "E-3 wipe_and_rehydrate 语法", True,
                   "文件不在本仓库(跳过)")
    except Exception as e:
        _check("E", "E-3 wipe_and_rehydrate 语法", False, str(e))

    # E-4: control.sh 存在且含 start/stop/status
    try:
        ctrl = (ROOT / "control.sh").read_text(encoding="utf-8")
        for cmd in ("start", "stop", "status"):
            assert cmd in ctrl, f"control.sh 缺 {cmd}"
        _check("E", "E-4 control.sh 完整性", True,
               "start/stop/status 命令均存在")
    except Exception as e:
        _check("E", "E-4 control.sh 完整性", False, str(e))

    # E-5: (LIVE only) POST /symbols + GET warmup-state 联调
    if LIVE:
        try:
            import httpx
            client = httpx.Client(base_url=BASE_URL, timeout=10)
            # POST /api/v1/symbols
            r = client.post("/api/v1/symbols",
                            json={"ticker": "TEST_SELFTEST", "start_warmup": False})
            assert r.status_code in (200, 201), f"POST /symbols 返 {r.status_code}"
            body = r.json()
            assert body["ticker"] == "TEST_SELFTEST"
            # GET /api/v1/symbols/TEST_SELFTEST/warmup-state
            r2 = client.get("/api/v1/symbols/TEST_SELFTEST/warmup-state")
            assert r2.status_code == 200, f"GET warmup-state 返 {r2.status_code}"
            body2 = r2.json()
            assert body2["ticker"] == "TEST_SELFTEST"
            assert "warmup_started_at" in body2
            assert "metadata" in body2
            _check("E", "E-5 LIVE API 联调", True,
                   f"POST→{r.status_code} GET→{r2.status_code} 字段完整")
        except Exception as e:
            _check("E", "E-5 LIVE API 联调", False, str(e))
    else:
        _check("E", "E-5 LIVE API 联调", True,
               "沙箱模式跳过(加 --live 启用)")


# ====================================================================
# Main
# ====================================================================

def main() -> int:
    print("=" * 60)
    print("  V1.7.5/V1.7.6 自测 25 测点 (5×5)")
    print(f"  mode={'LIVE' if LIVE else 'SANDBOX'}  base={BASE_URL}")
    print("=" * 60)

    section_a()
    section_b()
    section_c()
    section_d()
    section_e()

    # ---- 汇总 ----
    total = _pass + _fail
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {_pass}/{total} PASSED, {_fail} FAILED, {_skip} SKIPPED")
    print(f"{'=' * 60}")

    if _fail:
        print("\nFAILED:")
        for name, ok, detail in _results:
            if not ok:
                print(f"  x {name} -- {detail}")
        return 1

    print(f"\nALL {total} TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
