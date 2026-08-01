"""Serves the built frontend static files alongside the API.
To use: python -m app.static_serve
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.main import app

import os

# 加载 API Key 环境变量
# 2026-07-23 patch: 容器化后路径只有 3 级，parents[4] IndexError。
# 改为按可用层数降级（3, 2, 1）推断仓库根。
def _infer_repo_root_secrets() -> Path | None:
    p = Path(__file__).resolve()
    for depth in (3, 2, 1):
        try:
            candidate = p.parents[depth] / ".env.secrets"
        except IndexError:
            continue
        return candidate
    return None

_SECRETS = _infer_repo_root_secrets()
if _SECRETS and _SECRETS.exists():
    for line in _SECRETS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# 优先读环境变量（容器化部署用，源文件不在 parents[2] 期望位置时设这个）
_env_dist = os.environ.get("FRONTEND_DIST")
if _env_dist:
    FRONTEND_DIST = Path(_env_dist)
else:
    # 源码布局: ../../frontend/dist（parents[2]）。fallback 同样试一下
    # parents[1]（仅为容器内的情况：app/ 在 /app/ 下，dist 也在 /app/frontend/dist/）
    _resolved = Path(__file__).resolve()
    FRONTEND_DIST = _resolved.parents[2] / "frontend" / "dist"
    if not FRONTEND_DIST.is_dir() and (_resolved.parents[1] / "frontend" / "dist").is_dir():
        FRONTEND_DIST = _resolved.parents[1] / "frontend" / "dist"


def _setup_static() -> None:
    if not FRONTEND_DIST.is_dir():
        import warnings

        warnings.warn(
            f"Frontend dist not found at {FRONTEND_DIST}. "
            "Run 'npm run build' in frontend/ first."
        )
        return

    # Serve static assets
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend_assets",
    )

    index_path = str(FRONTEND_DIST / "index.html")

    # Override FastAPI's default root with frontend SPA
    # FastAPI auto-generates a GET / route; register ours after to win
    @app.get("/", include_in_schema=False)
    async def spa_root():
        return FileResponse(index_path, media_type="text/html")

    @app.get("/favicon.svg", include_in_schema=False)
    async def _favicon_svg():
        return FileResponse(str(FRONTEND_DIST / "favicon.svg"), media_type="image/svg+xml")

    @app.get("/icon-192.svg", include_in_schema=False)
    async def _icon_192_svg():
        return FileResponse(str(FRONTEND_DIST / "icon-192.svg"), media_type="image/svg+xml")

    @app.get("/icon-512.svg", include_in_schema=False)
    async def _icon_512_svg():
        return FileResponse(str(FRONTEND_DIST / "icon-512.svg"), media_type="image/svg+xml")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    async def _manifest():
        return FileResponse(str(FRONTEND_DIST / "manifest.webmanifest"), media_type="application/manifest+json")

    @app.get("/registerSW.js", include_in_schema=False)
    async def _register_sw():
        return FileResponse(str(FRONTEND_DIST / "registerSW.js"), media_type="application/javascript")

    @app.get("/sw.js", include_in_schema=False)
    async def _sw_js():
        return FileResponse(str(FRONTEND_DIST / "sw.js"), media_type="application/javascript")

    @app.get("/offline.html", include_in_schema=False)
    async def _offline_html():
        return FileResponse(str(FRONTEND_DIST / "offline.html"), media_type="text/html")

    # SPA fallback: any non-API path -> index.html
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(index_path, media_type="text/html")


_setup_static()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.static_serve:app", host="0.0.0.0", port=8000, reload=False)
