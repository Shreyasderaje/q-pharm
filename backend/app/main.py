"""Q-Pharm API server entrypoint.

Run with:  uvicorn app.main:app --reload --port 8000   (from backend/)
If the frontend has been built (frontend/dist), it is served at "/" so the
whole platform runs from a single process.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .core.config import APP_VERSION, FRONTEND_DIST

app = FastAPI(
    title="Q-Pharm API",
    description="Quantum-accelerated drug repurposing engine — "
                "VQE-refined docking + ADMET re-ranking over a curated FDA drug library.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return HTMLResponse("<h1>404 — not found</h1>", status_code=404)
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
