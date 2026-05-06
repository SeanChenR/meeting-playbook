/**
 * Better Auth singleton — used by:
 *   1. The Better Auth CLI for schema generation / migration:
 *        bunx @better-auth/cli generate --config packages/auth/auth.ts -y
 *        bunx @better-auth/cli migrate  --config packages/auth/auth.ts -y
 *   2. The Bun.serve gateway entrypoint (src/server.ts).
 *
 * Tests should import `createAuth` from `./src/auth` directly so they can
 * inject a fake database / secret and avoid triggering the singleton.
 */

import { createAuth } from "./src/auth";

export const auth = createAuth();
