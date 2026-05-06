## ADDED Requirements

### Requirement: Gateway routes auth-namespace requests to Better Auth handler

The Bun.serve gateway SHALL route any HTTP request whose path begins with `/api/auth/` directly to the Better Auth `handler` function. Such requests MUST NOT be proxied to the FastAPI backend.

#### Scenario: Login flow request

- **WHEN** a client sends a request to `POST /api/auth/sign-in/social` with provider `google`
- **THEN** the gateway invokes the Better Auth handler and returns its response unchanged to the client

#### Scenario: TOTP enrollment request

- **WHEN** a client sends a request to `POST /api/auth/two-factor/enable`
- **THEN** the gateway invokes the Better Auth handler and returns its response unchanged to the client

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

### Requirement: Gateway injects X-User-Id header on forwarded requests

When the gateway forwards an authenticated request to FastAPI, it SHALL set an `X-User-Id` request header whose value is the user identifier from the validated Better Auth session. The gateway MUST overwrite any `X-User-Id` header supplied by the client and MUST NOT honor a client-supplied value.

#### Scenario: Forwarded request carries injected user id

- **WHEN** the gateway forwards `GET /api/me` for a session belonging to user `usr_abc123`
- **THEN** the request reaching FastAPI includes the header `X-User-Id: usr_abc123`

#### Scenario: Client-supplied X-User-Id header is overwritten

- **GIVEN** a client with a valid Better Auth session for user `usr_legit`
- **WHEN** the client sends `GET /api/me` with header `X-User-Id: usr_attacker`
- **THEN** the request reaching FastAPI includes the header `X-User-Id: usr_legit`, never `usr_attacker`

### Requirement: FastAPI backend trusts X-User-Id without re-validation

The FastAPI backend SHALL treat the `X-User-Id` request header as the authenticated user identifier for the request. The backend MUST NOT independently validate the Better Auth session, because the gateway is the sole ingress in dev and production.

When `X-User-Id` is absent on a request that is otherwise valid, FastAPI SHALL respond with an unauthenticated error response, indicating that the request did not arrive through the gateway.

#### Scenario: Request via gateway succeeds

- **WHEN** FastAPI receives `GET /api/me` with header `X-User-Id: usr_abc123`
- **THEN** FastAPI responds with HTTP 200 and a body containing `user_id` equal to `usr_abc123`

#### Scenario: Direct request without header is rejected

- **WHEN** FastAPI receives `GET /api/me` without an `X-User-Id` header, for example via direct connection to its bound port
- **THEN** FastAPI responds with an error status code and a body whose `error_code` indicates the request bypassed the gateway

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

### Requirement: WebSocket upgrades carry X-User-Id

When a non-auth `/api/*` request is a WebSocket upgrade and the client has a valid Better Auth session, the gateway SHALL proxy the upgrade to FastAPI with the `X-User-Id` header attached to the upgrade request. Subsequent WebSocket message frames are not required to carry the header, since the upgrade established the user identity for the connection lifetime.

#### Scenario: Authenticated WebSocket upgrade is proxied

- **WHEN** a client with a valid session opens a WebSocket to a path like `/api/meetings/{id}/session`
- **THEN** FastAPI receives the upgrade request with the `X-User-Id` header set and accepts the connection

#### Scenario: Unauthenticated WebSocket upgrade is rejected

- **WHEN** a client without a session attempts a WebSocket upgrade to a non-auth `/api/*` path
- **THEN** the gateway rejects the upgrade with HTTP 401 and FastAPI is not contacted
