import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from typing import Any

from .routes_jobs import router as jobs_router
from .routes_rawprep import router as rawprep_router
from .routes_runpod import router as runpod_router
from .routes_studio import router as studio_router
from ..core.runpod_provider import resume_provider_lifecycle_on_boot
from ..core.studio_queue import external_worker_output_roots
from ..core.studio_queue import resume_known_queues
from ..raw_engine_v2.single_raw.runtime import build_single_raw_runtime_health


@asynccontextmanager
async def lifespan(_app: FastAPI):
    resumed_roots = resume_provider_lifecycle_on_boot()
    default_roots = external_worker_output_roots("outputs")
    remaining_roots = [root for root in default_roots if root not in resumed_roots]
    resume_known_queues(default_output_roots=remaining_roots)
    yield


app = FastAPI(title="DreamCatcher API", version="0.6.0", lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(rawprep_router)
app.include_router(runpod_router)
app.include_router(studio_router)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "single_raw_runtime": build_single_raw_runtime_health(),
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _mount_frontend_if_requested() -> None:
    if os.getenv("DC_SERVE_FRONTEND") != "1":
        return
    app_root = Path(__file__).resolve().parents[3]
    frontend_dist = app_root / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="studio-frontend")


_mount_frontend_if_requested()
