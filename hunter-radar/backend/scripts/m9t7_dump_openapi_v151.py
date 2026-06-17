"""M9-t7 dump 脚本:扫 app/api/*.py → 生成 v1.5.1 OpenAPI freeze JSON。

不动 main.py / runtime,只静态扫:
- @router.{get,post,put,delete,patch} 装饰的路径
- 关联的 response_model / DTO 名称
- 关联的 Request Body / Query 参数(从类型注解 + 函数签名)

沙箱 fallback(无 fastapi / sqlalchemy / sentry_sdk 仍可跑):
- 不 import app.main,纯 ast 扫描
- 输出 `docs/openapi-frozen-v1.5.1.json`(机器可读)
- v1.5.1.md 由人手基于 v1.5.md 增补(本脚本不生成)

V1.5.1 增量(v1.5 → v1.5.1):
- /api/v1/edgar/search            GET   m9t4
- /api/v1/edgar/categories        GET   m9t4
- /api/v1/etf/basket              GET   m9t5
- /api/v1/etf/orders              POST  m9t5
- /api/v1/etf/premium-discount    GET   m9t5
- /api/v1/analytics/events        GET   m9t6
- /api/v1/analytics/funnel        GET   m9t6
- /api/v1/analytics/event-names   GET   m9t6
- 共 48 → 56 endpoints

新增 tags:edgar / etf / analytics(13 → 16 tags)
新增 routers:edgar / etf / analytics(13 → 16 routers)

V1.5.1 兼容性:
- 既有 v1.5 freeze(48 endpoints)全保留
- 沙箱 fallback 显式标注:sandbox_stub / sandbox_stub_v15_prep
- 严禁 mock 200 伪装(M5 锁定)
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP_API = ROOT / "backend" / "app" / "api"
DOC_JSON = ROOT / "docs" / "openapi-frozen-v1.5.1.json"

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

# 已知的 router 前缀映射(main.py 注册时的 prefix,无 prefix=空)
# 用于 dump 时正确拼出完整路径
ROUTER_PREFIX = {
    "health": "",  # /health, /
    "symbols": "/api/v1",
    "regime": "/api/v1",
    "screener": "/api/v1",
    "alerts": "/api/v1",
    "basket": "/api/v1",
    "push": "/api/v1",
    "data_status": "/api/v1",
    "quota": "/api/v1",
    "subscriptions": "/api/v1",
    "feature_flags": "/api/v1",
    "eight_k": "/api/v1",
    "admin": "/api/v1",
    "edgar": "/api/v1/edgar",
    "etf": "/api/v1/etf",
    "analytics": "/api/v1/analytics",
}


def _walk_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str, ast.expr | None]]:
    """提取函数上每个 @router.<method>(path, ...) 的 (method, path, response_model_kwarg_or_None)。"""
    out: list[tuple[str, str, ast.expr | None]] = []
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id != "router":
            continue
        if func.attr.lower() not in HTTP_METHODS:
            continue
        # 第 1 个位置参数 = path
        if not dec.args or not isinstance(dec.args[0], ast.Constant):
            continue
        path = str(dec.args[0].value)
        # response_model 关键字
        rm: ast.expr | None = None
        for kw in dec.keywords:
            if kw.arg == "response_model":
                rm = kw.value
        out.append((func.attr.lower(), path, rm))
    return out


def _name_of(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _function_returns_model(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """从函数返回注解 -> 'list[X]' / 'X' / 'dict' / None。"""
    if fn.returns is None:
        return None
    if isinstance(fn.returns, ast.Name):
        return fn.returns.id
    if isinstance(fn.returns, ast.Subscript):
        v = fn.returns.value
        sl = fn.returns.slice
        if isinstance(v, ast.Name) and v.id == "list" and isinstance(sl, ast.Name):
            return f"list[{sl.id}]"
        if isinstance(v, ast.Name) and v.id == "dict":
            return "dict"
    if isinstance(fn.returns, ast.Constant) and fn.returns.value is None:
        return None
    return None


def scan() -> dict[str, Any]:
    paths: dict[str, dict[str, dict[str, Any]]] = {}
    tags_set: set[str] = set()
    for py in sorted(BACKEND_APP_API.glob("*.py")):
        if py.name == "__init__.py":
            continue
        src = py.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(py))
        except SyntaxError as e:
            print(f"[WARN] {py.name} parse fail: {e}", file=sys.stderr)
            continue
        router_name = py.stem
        prefix = ROUTER_PREFIX.get(router_name, "/api/v1")
        tags_set.add(router_name)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for method, path, rm_kw in _walk_decorators(node):
                full_path = path if path.startswith("/") else f"/{path}"
                rm_name = _name_of(rm_kw) or _function_returns_model(node)
                # health / 根描述特殊:无 prefix
                if py.name == "health.py" and path in ("/health", "/"):
                    full = path
                else:
                    full = f"{prefix}{full_path}"
                paths.setdefault(full, {}).setdefault(method, {
                    "summary": ast.get_docstring(node) or "",
                    "response_model": rm_name or "unknown",
                    "source": f"app/api/{py.name}:{node.name}",
                })
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Hunter Radar V1.5.1 OpenAPI Freeze",
            "version": "1.5.1",
            "description": (
                "M9 接力期 freeze:在 v1.5 基础上新增 8 端点 — "
                "EDGAR 2(m9t4)+ ETF 3(m9t5)+ Analytics 3(m9t6);"
                "admin 4 端点(m7t7)在 v1.5 已 freeze;"
                "EDGAR fulltext search 真实 API 路径留作 v1.5.2。"
            ),
        },
        "tags": [{"name": t} for t in sorted(tags_set)],
        "paths": paths,
    }


def main() -> int:
    spec = scan()
    n_paths = len(spec["paths"])
    n_endpoints = sum(len([m for m in p if m in HTTP_METHODS]) for p in spec["paths"].values())
    print(f"[ok] v1.5.1 freeze dump 静态扫到 {n_paths} paths, {n_endpoints} endpoints, {len(spec['tags'])} tags")
    DOC_JSON.parent.mkdir(parents=True, exist_ok=True)
    DOC_JSON.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] 写入 {DOC_JSON}")
    # 列端点
    for path, methods in sorted(spec["paths"].items()):
        for m, meta in methods.items():
            print(f"     {m.upper():6s} {path:55s} -> {meta['response_model']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())