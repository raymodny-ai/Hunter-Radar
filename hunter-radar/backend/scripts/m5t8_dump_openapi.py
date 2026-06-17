"""M5-t8 沙箱静态 dump 脚本:扫 app/api/*.py → 生成 v1.4.1 OpenAPI freeze JSON。

不动 main.py / runtime,只静态扫:
- @router.{get,post,put,delete,patch} 装饰的路径
- 关联的 response_model / DTO 名称
- 关联的 Request Body / Query 参数(从类型注解 + 函数签名)

沙箱 fallback(无 fastapi / sqlalchemy / sentry_sdk 仍可跑):
- 不 import app.main,纯 ast 扫描
- 输出 `docs/openapi-frozen-v1.4.1.json`(机器可读)
- v1.4.1.md 由人手基于 v1.4.md 增补(本脚本不生成)
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP_API = ROOT / "backend" / "app" / "api"
DOC_JSON = ROOT / "docs" / "openapi-frozen-v1.4.1.json"

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}


def _walk_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str, ast.expr | None]]:
    """提取函数上每个 @router.<method>(path, ...) 的 (method, path, response_model_kwarg_or_None)."""
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
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for method, path, rm_kw in _walk_decorators(node):
                full_path = path if path.startswith("/") else f"/{path}"
                rm_name = _name_of(rm_kw) or _function_returns_model(node)
                # 健康 / 根描述特殊:无 prefix
                if py.name in ("health.py",) and path in ("/health", "/"):
                    full = path
                else:
                    full = f"/api/v1{full_path}"
                paths.setdefault(full, {}).setdefault(method, {
                    "summary": ast.get_docstring(node) or "",
                    "response_model": rm_name or "unknown",
                    "source": f"app/api/{py.name}:{node.name}",
                })
                # tag = 文件名去 .py
                tags_set.add(py.stem)
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Hunter Radar V1.4.1 OpenAPI Freeze",
            "version": "1.4.1",
            "description": (
                "M5 接力期补 freeze:在 v1.4 基础上新增 push(m5t4) / data-status(m5t6) / auth-quota(m5t8) "
                "6 端点;生产环境务必用 `uv run` 覆盖一次。"
            ),
        },
        "tags": [{"name": t} for t in sorted(tags_set)],
        "paths": paths,
    }


def main() -> int:
    spec = scan()
    n_paths = len(spec["paths"])
    n_endpoints = sum(len([m for m in p if m in HTTP_METHODS]) for p in spec["paths"].values())
    print(f"[ok] v1.4.1 freeze dump 静态扫到 {n_paths} paths, {n_endpoints} endpoints, {len(spec['tags'])} tags")
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
