## ADDED Requirements

### Requirement: Regenerate endpoint persists via snapshot-then-upsert

`POST /api/meetings/{meeting_id}/playbook/regenerate` SHALL call
`PlaybookRepository.snapshot_then_upsert` instead of
`upsert_for_meeting`. The snapshot step SHALL atomically copy the
current `free_form_markdown`, `updated_at`, and
`attachment_hash_snapshot` values into the corresponding `previous_*`
columns before writing the freshly generated payload.

The generator itself (`PlaybookGenerator.generate`) SHALL NOT change —
the slice-20c multimodal contract is preserved. Only the persistence
step that follows the LLM call switches paths.

The response SHALL be HTTP 200 with a `PlaybookRead` payload that
includes the new `previous_*` fields populated from the just-snapshotted
state.

If the playbook row does not exist yet (first-ever generation for a
meeting), the snapshot step SHALL be a no-op (nothing to snapshot) and
the regenerate SHALL fall through to a plain insert. In that case the
response's `previous_*` fields SHALL be NULL and `has_previous_version`
SHALL be `false`.

#### Scenario: Regenerate against existing playbook snapshots the prior version

- **GIVEN** a row with `free_form_markdown = "draft v1"`,
  `attachment_hash_snapshot = "hash-A"`, all `previous_*` NULL
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/regenerate` is
  called and the generator returns a new draft `"draft v2"` against
  attachments hashed to `"hash-B"`
- **THEN** the response is HTTP 200 with body
  `{"free_form_markdown": "draft v2", "attachment_hash_snapshot": "hash-B",
  "previous_free_form_markdown": "draft v1",
  "previous_attachment_hash_snapshot": "hash-A",
  "has_previous_version": true, ...}`

#### Scenario: First-ever regenerate has no snapshot to capture

- **GIVEN** no `playbook` row exists for the meeting yet
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/regenerate` is
  called and the generator produces a draft
- **THEN** the response is HTTP 200 with body where
  `previous_free_form_markdown` is `null` and `has_previous_version` is
  `false`

#### Scenario: Generator failure does not advance the snapshot

- **GIVEN** a row with `free_form_markdown = "v1"`,
  `previous_free_form_markdown = "v0"`
- **WHEN** the generator raises `PlaybookGenerationFailed` and the
  endpoint returns HTTP 502
- **THEN** the row is unchanged: `free_form_markdown` is still `"v1"`
  and `previous_free_form_markdown` is still `"v0"` (no snapshot
  rotation happens before a successful LLM round-trip)
