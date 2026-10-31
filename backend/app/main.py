from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router

from app.config import Settings, get_settings
from app.db import connect


def create_app() -> FastAPI:
    app = FastAPI(title="UK Wind Forecast Monitor")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET"])
    app.include_router(router)

    @app.get("/api/health")
    def health(settings: Annotated[Settings, Depends(get_settings)]):
        try:
            conn = connect(settings)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
        except Exception:
            return JSONResponse({"status": "error", "db": False}, status_code=503)
        return {"status": "ok", "db": True}

    return app


app = create_app()
