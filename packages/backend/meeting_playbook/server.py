"""FastAPI application — gateway-trusting backend.

Per ADR-0021 + spec `auth-gateway-contract`: this service is only ever called by the
Bun.serve gateway, which validates the Better Auth session and injects an
`X-User-Id` request header. The backend trusts that header without re-validation.

Direct requests that bypass the gateway (no `X-User-Id`) MUST receive a 401 with
`error_code: auth.gateway_bypass`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse


def create_app() -> FastAPI:
    """Construct and return the FastAPI app."""
    app = FastAPI(title="meeting-playbook backend", version="0.0.1")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    async def me(
        x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    ) -> JSONResponse:
        if not x_user_id:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error_code": "auth.gateway_bypass",
                    "message": (
                        "Missing X-User-Id header. This endpoint must be reached "
                        "through the auth gateway (default localhost:3001)."
                    ),
                },
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"user_id": x_user_id},
        )

    return app


app = create_app()
