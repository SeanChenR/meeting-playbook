## ADDED Requirements

### Requirement: Gateway authenticates and proxies WebSocket upgrades with identity headers preserved

The gateway SHALL handle HTTP requests carrying `Upgrade: websocket` against `/api/*` paths by performing the same authentication check used for non-WebSocket requests BEFORE allowing the upgrade to complete. Upon successful auth, the gateway SHALL forward the upgraded request to the FastAPI backend WITH the `X-User-Id`, `X-User-Name`, and `X-User-Email` headers set from the active session — overwriting any client-supplied values for those headers. Public API paths (`/api/health`) MUST NOT be upgradeable; the gateway SHALL reject WebSocket upgrades on public paths.

The upstream connection's lifecycle SHALL mirror the downstream: when the browser closes the WebSocket, the gateway SHALL close its upstream connection to FastAPI; when FastAPI closes upstream, the gateway SHALL close downstream. Half-open connections SHALL NOT linger.

#### Scenario: Authenticated WebSocket upgrade carries X-User-Id and friends

- **GIVEN** an authenticated user with session `usr_abc`, name `Sean`, email `sean@example.com`
- **WHEN** the user opens a WebSocket to `/api/meetings/m_abc/session` through the gateway
- **THEN** the upgrade request reaching the FastAPI backend SHALL carry `X-User-Id: usr_abc`, `X-User-Name: Sean` (URL-encoded), and `X-User-Email: sean@example.com` (URL-encoded), and any client-supplied values for those headers MUST have been overwritten

#### Scenario: Unauthenticated WebSocket upgrade is rejected

- **WHEN** an unauthenticated client (no Better Auth session cookie) attempts to upgrade a WebSocket to `/api/meetings/m_abc/session`
- **THEN** the gateway SHALL reject the upgrade with HTTP 401 and the standard error envelope; the upstream FastAPI backend MUST NOT receive the upgrade attempt

#### Scenario: Downstream close propagates to upstream

- **GIVEN** an active proxied WebSocket connection
- **WHEN** the browser-side WebSocket closes
- **THEN** the gateway SHALL close the upstream connection to FastAPI within a bounded delay; the upstream connection MUST NOT remain open longer than 5 seconds after the downstream close
