from __future__ import annotations

from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from app.api.routes_mobile_running_music import router as mobile_router
    from app.api.routes_mobile_mix import router as mix_router
    from app.api.routes_debug import router as debug_router
    from app.api.routes_admin_tuning import router as admin_tuning_router
    from app.paths import preferred_audio_dir
except Exception:  # pragma: no cover
    FastAPI = None
    StaticFiles = None
    mobile_router = None
    mix_router = None
    debug_router = None
    admin_tuning_router = None
    preferred_audio_dir = None


if FastAPI is not None:
    app = FastAPI(title="Mobile Running Music API", version="1.0.0")
    root_dir = Path(__file__).resolve().parents[1]
    audio_dir = preferred_audio_dir() if preferred_audio_dir is not None else root_dir.parent / "edm_sample"

    if StaticFiles is not None and audio_dir.exists():
        app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

    if mobile_router is not None:
        app.include_router(mobile_router)
    if mix_router is not None:
        app.include_router(mix_router)
    if debug_router is not None:
        app.include_router(debug_router)
    if admin_tuning_router is not None:
        app.include_router(admin_tuning_router)

    @app.get("/")
    def root():
        return {
            "service": "mobile-running-music-api",
            "version": "1.0.0",
            "health": "/health",
            "openapi": "/openapi.json",
            "docs": "/docs",
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}
else:
    app = None
