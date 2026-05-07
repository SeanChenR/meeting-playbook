"""FastAPI application — gateway-trusting backend.

Per ADR-0021 + spec `auth-gateway-contract`: this service is only ever called by the
Bun.serve gateway, which validates the Better Auth session and injects an
`X-User-Id` request header. The backend trusts that header without re-validation.

Direct requests that bypass the gateway (no `X-User-Id`) MUST receive a 401 with
`error_code: auth.gateway_bypass`.

Slice 2 adds an error-envelope contract: every error response is shaped
`{"error_code": <snake.dot.code>, "message": <str>}`. The frontend looks up
`error_code` in its `errors.*` locale group to render a localized message.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _envelope(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Build a JSONResponse carrying the standard error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


def create_app() -> FastAPI:
    """Construct and return the FastAPI app."""
    app = FastAPI(title="meeting-playbook backend", version="0.0.1")

    # ─── Error envelope handlers ────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "auth.unauthenticated"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "http.403"
        else:
            error_code = f"http.{exc.status_code}"
        return _envelope(exc.status_code, error_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        _req: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "Request validation failed"}
        return _envelope(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "common.validation_error",
            str(first.get("msg") or "Request validation failed"),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_req: Request, _exc: Exception) -> JSONResponse:
        # Hide internal details — clients get a stable error_code only.
        return _envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "common.internal_error",
            "An unexpected error occurred",
        )

    # ─── Routes ─────────────────────────────────────────────────────────
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    async def me(
        x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    ) -> Any:
        if not x_user_id:
            return _envelope(
                status.HTTP_401_UNAUTHORIZED,
                "auth.gateway_bypass",
                "Missing X-User-Id header. This endpoint must be reached "
                "through the auth gateway (default localhost:3001).",
            )
        return {"user_id": x_user_id}

    return app


app = create_app()
