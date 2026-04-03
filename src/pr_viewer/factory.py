from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pr_viewer.api.compare import router as compare_router
from pr_viewer.config import load_config


def create_app() -> FastAPI:
    config = load_config()

    app = FastAPI(title="PR Viewer")
    app.include_router(compare_router)

    app.state.config = config

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
