# auth-gateway-contract Specification

## Purpose

The Bun.serve gateway is the single ingress for the meeting-playbook stack. It owns
the Better Auth session, decides whether each request is allowed past it, and — for
authenticated requests — injects an `X-User-Id` header so the FastAPI backend can
identify the user without re-validating the session itself. The backend is bound to
`127.0.0.1` and never exposed to the network; only the gateway ever calls it.

This contract underpins every subsequent slice: any new business endpoint added to
the backend automatically inherits user identity from the header, and any new
public-by-design endpoint can opt out of auth via the `PUBLIC_API_PATHS` allowlist
(currently just `/api/health`). WebSocket upgrades follow the same contract — the
upgrade request carries `X-User-Id`, then frames flow without re-authenticating.

## Requirements

### Requirement: Gateway routes auth-namespace requests to Better Auth handler

The Bun.serve gateway SHALL route any HTTP request whose path begins with `/api/auth/` directly to the Better Auth `handler` function. Such requests MUST NOT be proxied to the FastAPI backend.

#### Scenario: Login flow request

- **WHEN** a client sends a request to `POST /api/auth/sign-in/social` with provider `google`
- **THEN** the gateway invokes the Better Auth handler and returns its response unchanged to the client

#### Scenario: TOTP enrollment request

- **WHEN** a client sends a request to `POST /api/auth/two-factor/enable`
- **THEN** the gateway invokes the Better Auth handler and returns its response unchanged to the client


<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->

---
### Requirement: Gateway authenticates non-auth /api/* requests

For any request whose path begins with `/api/` but does not begin with `/api/auth/`, the gateway SHALL validate the Better Auth session before forwarding. Requests without a valid session MUST receive a 401 response from the gateway, and such requests MUST NOT be forwarded to the FastAPI backend.

#### Scenario: Authenticated request is forwarded

- **WHEN** a client with a valid Better Auth session cookie sends `GET /api/me`
- **THEN** the gateway proxies the request to FastAPI and returns FastAPI's response to the client

#### Scenario: Unauthenticated request is rejected

- **WHEN** a client without any session cookie sends `GET /api/me`
- **THEN** the gateway responds with HTTP 401 and FastAPI is not contacted

#### Scenario: Expired session is rejected

- **WHEN** a client with an expired session cookie sends `GET /api/me`
- **THEN** the gateway responds with HTTP 401 and FastAPI is not contacted


<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->

---
### Requirement: Gateway injects X-User-Id header on forwarded requests

When the gateway forwards an authenticated request to FastAPI, it SHALL set an `X-User-Id` request header whose value is the user identifier from the validated Better Auth session. The gateway MUST overwrite any `X-User-Id` header supplied by the client and MUST NOT honor a client-supplied value.

#### Scenario: Forwarded request carries injected user id

- **WHEN** the gateway forwards `GET /api/me` for a session belonging to user `usr_abc123`
- **THEN** the request reaching FastAPI includes the header `X-User-Id: usr_abc123`

#### Scenario: Client-supplied X-User-Id header is overwritten

- **GIVEN** a client with a valid Better Auth session for user `usr_legit`
- **WHEN** the client sends `GET /api/me` with header `X-User-Id: usr_attacker`
- **THEN** the request reaching FastAPI includes the header `X-User-Id: usr_legit`, never `usr_attacker`


<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->

---
### Requirement: FastAPI backend trusts X-User-Id without re-validation

The FastAPI backend SHALL treat the `X-User-Id` request header as the authenticated user identifier for the request. The backend MUST NOT independently validate the Better Auth session, because the gateway is the sole ingress in dev and production.

When `X-User-Id` is absent on a request that is otherwise valid, FastAPI SHALL respond with an unauthenticated error response, indicating that the request did not arrive through the gateway.

#### Scenario: Request via gateway succeeds

- **WHEN** FastAPI receives `GET /api/me` with header `X-User-Id: usr_abc123`
- **THEN** FastAPI responds with HTTP 200 and a body containing `user_id` equal to `usr_abc123`

#### Scenario: Direct request without header is rejected

- **WHEN** FastAPI receives `GET /api/me` without an `X-User-Id` header, for example via direct connection to its bound port
- **THEN** FastAPI responds with an error status code and a body whose `error_code` indicates the request bypassed the gateway


<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->

---
### Requirement: Forwarded requests preserve client request metadata

When proxying an authenticated request to FastAPI, the gateway SHALL preserve the original HTTP method, request body, query string, and request headers, with the following exceptions: the gateway MUST strip the Better Auth session cookie from the forwarded request, and the gateway MUST set the `X-User-Id` header as defined above.

#### Scenario: POST body is preserved

- **WHEN** a client sends `POST /api/meetings` with JSON body containing field `title`
- **THEN** the request body received by FastAPI contains the same JSON content byte-for-byte

#### Scenario: Query string is preserved

- **WHEN** a client sends `GET /api/meetings?limit=20`
- **THEN** the request received by FastAPI carries the same query string `?limit=20`

#### Scenario: Auth session cookie is stripped

- **WHEN** the gateway forwards a request that carries a Better Auth session cookie
- **THEN** the request reaching FastAPI does not contain that session cookie


<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->

---
### Requirement: WebSocket upgrades carry X-User-Id

When a non-auth `/api/*` request is a WebSocket upgrade and the client has a valid Better Auth session, the gateway SHALL proxy the upgrade to FastAPI with the `X-User-Id` header attached to the upgrade request. Subsequent WebSocket message frames are not required to carry the header, since the upgrade established the user identity for the connection lifetime.

#### Scenario: Authenticated WebSocket upgrade is proxied

- **WHEN** a client with a valid session opens a WebSocket to a path like `/api/meetings/{id}/session`
- **THEN** FastAPI receives the upgrade request with the `X-User-Id` header set and accepts the connection

#### Scenario: Unauthenticated WebSocket upgrade is rejected

- **WHEN** a client without a session attempts a WebSocket upgrade to a non-auth `/api/*` path
- **THEN** the gateway rejects the upgrade with HTTP 401 and FastAPI is not contacted

<!-- @trace
source: slice-01-auth-shell
updated: 2026-05-06
code:
  - packages/backend/meeting_playbook/preflight.py
  - packages/web/src/lib/auth-client.ts
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/server.py
  - packages/web/bunfig.toml
  - packages/backend/alembic/script.py.mako
  - docs/adr/0021-better-auth.md
  - packages/backend/meeting_playbook/logging.py
  - packages/web/src/routes/totp/enroll.tsx
  - better-auth_migrations/2026-05-06T10-14-40.015Z.sql
  - packages/web/src/components/ui/card.tsx
  - packages/web/src/routes/home.tsx
  - README.md
  - packages/auth/tsconfig.json
  - packages/backend/uv.lock
  - .env.example
  - packages/web/src/routes/login.tsx
  - packages/auth/package.json
  - packages/web/src/components/ui/badge.tsx
  - packages/web/tsconfig.json
  - packages/web/index.html
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/ui/label.tsx
  - packages/auth/auth.ts
  - packages/web/src/main.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/package.json
  - packages/web/src/components/ui/input.tsx
  - packages/web/vite.config.ts
  - packages/backend/alembic/env.py
  - packages/web/src/routes/signup.tsx
  - packages/web/src/test-setup.ts
  - packages/web/src/lib/utils.ts
  - packages/web/src/components/ui/separator.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/ui/avatar.tsx
  - packages/web/src/routes/totp/verify.tsx
  - bun.lock
  - packages/web/src/components/ui/alert.tsx
  - package.json
  - packages/auth/src/auth.ts
  - packages/web/src/components/auth-shell.tsx
tests:
  - packages/backend/tests/test_config.py
  - packages/web/src/App.test.tsx
  - packages/auth/src/__tests__/auth.test.ts
  - packages/backend/tests/test_integration_round_trip.py
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/auth/src/__tests__/gateway.test.ts
  - packages/web/src/routes/signup.test.tsx
  - packages/backend/tests/test_preflight.py
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/login.test.tsx
  - packages/backend/tests/test_alembic_baseline.py
  - packages/backend/tests/test_logging.py
  - packages/backend/tests/test_api_me.py
-->