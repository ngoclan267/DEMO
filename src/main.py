"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _ensure_project_root_on_path() -> None:
    """Ensure the repository root is importable when running this file directly."""
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_path()

from src.config import get_settings
from src.api.routes import router
from src.db.repository import init_and_seed
from src.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Tao SQLite schema, seed cac Topic that (app_id da xac minh) neu DB con rong,
    va bat scheduler tu dong crawl dinh ky (co the tat qua ENABLE_SCHEDULER=false)."""
    init_and_seed()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="Multi-Agent Social Listening platform - phat hien som phan hoi tieu cuc cho doanh nghiep.",
    version="1.0.0-mvp",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}


if __name__ == "__main__":
    import os
    import socket

    import uvicorn

    def _get_server_port(default_port: int = 8000) -> int:
        requested_port = int(os.getenv("PORT", str(default_port)))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("0.0.0.0", requested_port))
                return requested_port
            except OSError:
                sock.bind(("0.0.0.0", 0))
                return sock.getsockname()[1]

    uvicorn.run("src.main:app", host="0.0.0.0", port=_get_server_port(), reload=False)
