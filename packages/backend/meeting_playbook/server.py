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

from meeting_playbook.meetings.router import router as meetings_router
from meeting_playbook.playbooks.router import router as playbooks_router


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
        # Endpoints can opt into a custom error_code by raising
        # HTTPException(detail={"error_code": "...", "message": "..."}).
        if isinstance(exc.detail, dict) and "error_code" in exc.detail:
            return _envelope(
                exc.status_code,
                str(exc.detail["error_code"]),
                str(exc.detail.get("message", "")),
            )
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "auth.unauthenticated"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "http.403"
        else:
            error_code = f"http.{exc.status_code}"
        return _envelope(exc.status_code, error_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        req: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "Request validation failed"}
        msg = str(first.get("msg") or "Request validation failed")
        loc = first.get("loc") or ()

        # Domain-aware mapping: meeting POST body field errors get a
        # structured `meeting.<field>.required` so the frontend can resolve
        # to a localized message (slice-03 spec — required-field matrix).
        if (
            req.url.path.startswith("/api/meetings")
            and len(loc) >= 2
            and loc[0] == "body"
            and loc[1] in {"title", "counterparty_display_name", "me_display_name"}
        ):
            error_code = f"meeting.{loc[1]}.required"
        else:
            error_code = "common.validation_error"

        return _envelope(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code,
            msg,
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

    app.include_router(meetings_router)
    app.include_router(playbooks_router)
    return app


app = create_app()
