from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import actions, grab, manual_grab, pipeline, qbittorrent, source_test, torznab

_DIST = pathlib.Path(__file__).parent.parent.parent / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Deceptarr", docs_url=None, redoc_url=None)

    # API routers — always active
    app.include_router(torznab.router)
    app.include_router(grab.router)
    app.include_router(qbittorrent.router)
    app.include_router(actions.router)
    app.include_router(source_test.router)
    app.include_router(manual_grab.router)
    app.include_router(pipeline.router)

    if _DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
    else:
        @app.get("/")
        def frontend_missing() -> JSONResponse:
            return JSONResponse(
                {
                    "service": "deceptarr",
                    "status": "ok",
                    "frontend": "missing dist build",
                    "hint": "Run npm run build in frontend/ or use the Vite dev server.",
                }
            )

    return app
