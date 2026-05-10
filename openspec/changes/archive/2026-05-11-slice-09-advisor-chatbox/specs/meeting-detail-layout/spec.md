## ADDED Requirements

### Requirement: AdvisorPane integrates chat history hydration via React Query

The detail page's right column SHALL mount `<AdvisorPane session={session} />` with the session hook providing chat-history-aware state. The page SHALL use React Query to fetch `GET /api/meetings/{id}/chat_messages` via `chat-api.ts`'s `chatMessagesQueryOptions(meetingId)` on detail page mount. When the query resolves, the response SHALL be passed into the `useMeetingSession` hook (or hydrated into its reducer via a `HISTORY_LOADED` action) so that the rendered AdvisorPane has the persisted history before the user takes any action.

After every successful advise stream (signalled by an `advice_done` frame), the hook SHALL invalidate the React Query cache key `["chat_messages", meetingId]` so the history list re-fetches and reflects the newly persisted pair. The cache SHALL stay valid across the entire detail page lifetime; navigating away and back SHALL show cached data immediately while a background refetch verifies freshness.

#### Scenario: Detail page mount triggers chat_messages GET

- **GIVEN** a navigation to `/meetings/{m_id}` for a meeting with persisted chat history
- **WHEN** the detail page mounts and React Query bootstraps
- **THEN** the network SHALL contain a GET `/api/meetings/{m_id}/chat_messages` request; on success, the AdvisorPane SHALL render the persisted message bubbles before any WS interaction

#### Scenario: Successful advice stream invalidates chat_messages cache

- **GIVEN** an `in_progress` meeting and an active session with no in-flight advice
- **WHEN** the user sends a chatbox message that completes successfully (`advice_done` received)
- **THEN** the React Query cache key `["chat_messages", m_id]` SHALL be invalidated; a fresh GET `/api/meetings/{m_id}/chat_messages` SHALL fire; the new history list SHALL include the just-persisted user + advisor pair
