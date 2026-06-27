"""Serves the built frontend static files alongside the API.
To use: python -m app.static_serve
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.main import app

import os

# 加载 API Key 环境变量
_SECRETS = Path(__file__).resolve().parents[4] / ".env.secrets"
if _SECRETS.exists():
    for line in _SECRETS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


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
    @app.get("/icon-192.svg", include_in_schema=False)
    @app.get("/icon-512.svg", include_in_schema=False)
    @app.get("/manifest.webmanifest", include_in_schema=False)
    @app.get("/registerSW.js", include_in_schema=False)
    @app.get("/sw.js", include_in_schema=False)
    @app.get("/offline.html", include_in_schema=False)
    async def spa_static_root():
        return FileResponse(index_path, media_type="text/html")

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
