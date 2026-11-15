from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .db import get_engine
from .deps import get_market
from .routers import auth, market, scans, watchlists

log = logging.getLogger("legion.api")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = FastAPI(title="Legion Quant Terminal API", version="0.1.0",
                  docs_url=None if settings.env == "prod" else "/docs", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["authorization", "content-type"])

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception(json.dumps({"event": "unhandled_error", "request_id": request_id,
                                      "method": request.method, "path": request.url.path}))
            response = JSONResponse({"detail": "Internal server error", "request_id": request_id}, status_code=500)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["cache-control"] = "no-store"
        log.info(json.dumps({"event": "request", "request_id": request_id, "method": request.method,
                             "path": request.url.path, "status": response.status_code,
                             "ms": round((time.perf_counter() - started) * 1000, 1)}))
        return response

    @app.get("/health", tags=["meta"])
    def health() -> JSONResponse:
        """Liveness plus dependency checks. 503 if the database is unreachable."""
        checks = {"database": "ok", "provider": settings.data_provider}
        try:
            with get_engine().connect() as conn:
                conn.execute(text("select 1"))
        except Exception as e:  # noqa: BLE001
            checks["database"] = f"error: {type(e).__name__}"
        ok = checks["database"] == "ok"
        return JSONResponse({"status": "ok" if ok else "degraded", "version": app.version, **checks},
                            status_code=200 if ok else 503)

    get_market()  # fail at startup if the configured provider is missing credentials
    for r in (auth.router, market.router, watchlists.router, scans.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
