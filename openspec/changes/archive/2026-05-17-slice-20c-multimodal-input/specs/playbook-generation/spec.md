## ADDED Requirements

### Requirement: PlaybookGenerator accepts an optional sequence of meeting attachments

The `PlaybookGenerator.generate` method SHALL accept an optional positional or keyword argument `attachment_refs` typed as a `Sequence[AttachmentRef]` defaulting to an empty tuple. `AttachmentRef` is the existing `meeting-attachment` value object whose fields include at least `id`, `file_path`, `kind`, and `original_name`. When `attachment_refs` is empty, the generator SHALL behave exactly as before this change (single text prompt, no `parts` array).

When `attachment_refs` is non-empty, the generator SHALL delegate prompt assembly to `MultimodalContextBuilder.build(text_context, attachments)` from `packages/backend/meeting_playbook/attachments/multimodal_context.py`. The builder's returned `parts` SHALL be passed verbatim to the `google-genai` `client.models.generate_content(contents=parts, ...)` call. Image attachments SHALL be encoded as `types.Part.from_bytes(data=raw_bytes, mime_type=...)` and SHALL appear before all text parts; document attachments (PDF, docx, txt, md) SHALL have their extracted text inlined into a single combined text part that follows the image parts and precedes the original Calendar-derived system context.

#### Scenario: Empty attachment_refs preserves the legacy single-text prompt path

- **GIVEN** a Calendar event input and `attachment_refs = []`
- **WHEN** `PlaybookGenerator.generate(event, attachment_refs=[])` runs
- **THEN** the `contents` argument passed to the Vertex AI call SHALL be exactly one text string (no `Part` list), preserving identical behaviour to the pre-S20c implementation

#### Scenario: Single PNG attachment becomes the first part in a parts array

- **GIVEN** a Calendar event input and one `AttachmentRef` of `kind="image/png"` pointing at a valid 100KB PNG
- **WHEN** `PlaybookGenerator.generate(event, attachment_refs=[png_ref])` runs
- **THEN** the `contents` argument SHALL be a list whose first element is a `Part` constructed via `Part.from_bytes(data=<png bytes>, mime_type="image/png")` and whose last element is a `Part.from_text(text=<calendar context>)`

#### Scenario: PDF attachment's extracted text is inlined after image parts

- **GIVEN** a Calendar event input and one `AttachmentRef` of `kind="application/pdf"` whose `pypdf` extraction yields the string `"Q3 briefing"`
- **WHEN** `PlaybookGenerator.generate(event, attachment_refs=[pdf_ref])` runs
- **THEN** the `contents` argument SHALL be a list whose only element is a single `Part.from_text(...)` whose text contains the literal substring `"Q3 briefing"` AND the literal Calendar-derived system context AND a header line that names the attachment (e.g. `[Attachment: foo.pdf]`)

##### Example: mixed PNG + PDF + docx ordering

- **GIVEN** `attachment_refs = [png_ref, pdf_ref, docx_ref]`
- **WHEN** the generator builds `contents`
- **THEN** `contents[0]` SHALL be the image `Part.from_bytes`, and `contents[1]` SHALL be a single `Part.from_text` whose body contains the PDF-extracted text, then the docx-extracted text, then the Calendar-derived system context — in that order


### Requirement: PlaybookGenerator returns an attachment_hash_snapshot alongside the seven-field draft

The generator's return value SHALL include, in addition to the existing seven content-field keys, a key `attachment_hash_snapshot` whose value is the hex SHA-256 string produced by `MultimodalContextBuilder.build(...).snapshot_hash`. When `attachment_refs` is empty, `attachment_hash_snapshot` SHALL be the hex SHA-256 of the empty byte string (`"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`), representing the canonical empty-attachment set.

The snapshot hash SHALL be deterministic for a fixed attachment set regardless of `attachment_refs` ordering: callers passing the same set of attachments in different orders SHALL receive the same `attachment_hash_snapshot` value.

Callers MUST forward this key to `PlaybookRepository.upsert_for_meeting(meeting_id, payload)` so the value is persisted into the new `playbook.attachment_hash_snapshot` column.

#### Scenario: Empty attachments returns the canonical empty-set hash

- **WHEN** `generator.generate(event, attachment_refs=[])` runs
- **THEN** the returned draft's `attachment_hash_snapshot` SHALL equal the literal string `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`

#### Scenario: Identical attachment set in different order yields the same hash

- **GIVEN** two attachment lists `[a, b, c]` and `[c, a, b]` referencing the same three files on disk
- **WHEN** `generator.generate(event, attachment_refs=...)` runs once per ordering
- **THEN** both invocations SHALL return the same `attachment_hash_snapshot` value

#### Scenario: Changing one byte in any attachment changes the hash

- **GIVEN** two attachment lists differing only in that one PDF in the second list has been re-saved with a single edited word
- **WHEN** `generator.generate(...)` runs once per list
- **THEN** the two `attachment_hash_snapshot` values SHALL differ


### Requirement: PlaybookGenerator skips unprocessable attachments instead of failing the whole call

When `MultimodalContextBuilder.build(...)` encounters an `AttachmentProcessingError` for a specific attachment (corrupt PDF, encrypted PDF, malformed docx, IO failure, or extraction timeout `ATTACHMENT_TEXT_EXTRACTION_TIMEOUT_SECONDS`), the builder SHALL log a structured warning containing the `attachment_id` and `error_code`, append the `attachment_id` to `MultimodalContext.skipped_attachment_ids`, and proceed with the remaining attachments. The skipped attachment's bytes / text SHALL NOT contribute to the `parts` array nor to `snapshot_hash`.

`PlaybookGenerator.generate` SHALL succeed as long as at least the text Calendar context is produced; if every attachment fails AND `attachment_refs` was originally non-empty, the generator SHALL still call Vertex AI with the text-only context (equivalent to the empty-attachment path) and SHALL still return a valid draft.

#### Scenario: One corrupt PDF among three good attachments is skipped

- **GIVEN** `attachment_refs = [good_png, corrupt_pdf, good_docx]` where `corrupt_pdf` raises during `pypdf.PdfReader(...)`
- **WHEN** `generator.generate(event, attachment_refs=...)` runs
- **THEN** the Vertex AI call SHALL succeed with a `parts` list containing the good PNG bytes and the docx-extracted text plus Calendar context, AND a structured warning log SHALL name `corrupt_pdf.id` and `error_code = "attachment.extraction_failed"`

#### Scenario: All attachments fail — generator still produces a draft from text context

- **GIVEN** `attachment_refs = [corrupt_pdf_a, corrupt_pdf_b]` where both raise during extraction
- **WHEN** `generator.generate(event, attachment_refs=...)` runs
- **THEN** the generator SHALL invoke Vertex AI with text-only `contents` and SHALL return a draft whose `attachment_hash_snapshot` equals the canonical empty-set hash


## MODIFIED Requirements

### Requirement: Generator uses Vertex AI Gemini 2.5 Pro through the official SDK

The generator SHALL invoke the Gemini 2.5 Pro model on Vertex AI through the `google-genai` SDK with structured-output mode (response schema enforcing the seven string fields). When `attachment_refs` is empty, the SDK call SHALL use a single text `contents` argument. When `attachment_refs` is non-empty, the SDK call SHALL use a list of `types.Part` objects assembled by `MultimodalContextBuilder`. The generator SHALL NOT call any non-Vertex-AI provider, and SHALL NOT bypass the SDK by issuing raw HTTP requests. Authentication MUST flow through Application Default Credentials so deployments can swap service accounts without code changes.

#### Scenario: Non-Vertex provider is forbidden

- **WHEN** the generator code is reviewed
- **THEN** there MUST be no import of, nor HTTP call to, providers other than Vertex AI's Gemini family

##### Example: forbidden imports and HTTP calls that MUST fail review

```python
# FORBIDDEN — direct OpenAI SDK import
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
client.chat.completions.create(model="gpt-4o", messages=[...])

# FORBIDDEN — Anthropic SDK import
from anthropic import Anthropic
Anthropic().messages.create(model="claude-3-5-sonnet", messages=[...])

# FORBIDDEN — raw HTTP to a non-Vertex endpoint
httpx.post("https://api.openai.com/v1/chat/completions", json={...})

# FORBIDDEN — raw HTTP that bypasses the SDK even if the host is Vertex
httpx.post(
    "https://us-central1-aiplatform.googleapis.com/v1/projects/.../models/gemini-2.5-pro:generateContent",
    json={...},
)

# ALLOWED — the official google-genai SDK against Vertex AI
from google import genai
client = genai.Client(vertexai=True, project=..., location=...)
client.models.generate_content(model="gemini-2.5-pro", contents=parts)
```

#### Scenario: Structured-output schema is enforced

- **WHEN** the generator builds its request to Gemini 2.5 Pro
- **THEN** the request SHALL include a JSON response schema with exactly the seven string keys defined by `playbook-management`

#### Scenario: Multimodal call uses Part objects rather than raw strings

- **GIVEN** a non-empty `attachment_refs`
- **WHEN** the generator invokes `client.models.generate_content(...)`
- **THEN** the `contents` keyword argument SHALL be a list of `google.genai.types.Part` instances, not a single string


### Requirement: Generator output is suitable for direct upsert through the existing playbook repository

The generator SHALL emit a draft whose shape exactly matches the upsert payload accepted by `PlaybookRepository.upsert_for_meeting` defined in `playbook-management`: a dictionary with the seven existing string keys (`free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`) AND the new key `attachment_hash_snapshot` (string, hex SHA-256). Callers MUST be able to pass the draft straight to the repository without remapping or filtering.

The `PlaybookRepository.upsert_for_meeting` method SHALL accept the new `attachment_hash_snapshot` key and persist it into the `playbook.attachment_hash_snapshot` column. Existing rows whose column value is `NULL` SHALL continue to be readable and editable; the repository SHALL treat `NULL` as "snapshot unknown" rather than as an error.

#### Scenario: Draft is shape-compatible with the upsert payload

- **WHEN** the generator returns a draft for any input event
- **THEN** the draft's keys SHALL be exactly the seven content-field names defined by `playbook-management` plus `attachment_hash_snapshot`, and each value SHALL be a string

#### Scenario: Repository upsert succeeds without intermediate transformation

- **GIVEN** a generator output `draft` and a meeting `m_target`
- **WHEN** `PlaybookRepository.upsert_for_meeting(meeting_id="m_target", payload=draft)` is invoked
- **THEN** the upsert SHALL succeed and persist all seven content fields verbatim AND SHALL persist `attachment_hash_snapshot` into the new column

#### Scenario: Legacy rows with NULL attachment_hash_snapshot remain readable

- **GIVEN** a `playbook` row written before this migration with `attachment_hash_snapshot IS NULL`
- **WHEN** `PlaybookRepository.get_or_create_for_meeting(meeting_id)` runs
- **THEN** the call SHALL succeed and the returned playbook object's `attachment_hash_snapshot` attribute SHALL be `None`


## ADDED Requirements

### Requirement: Playbook is_stale flag reacts to attachment set changes

The backend SHALL expose `PlaybookRepository.get_with_stale_flag(meeting_id) -> PlaybookWithStale | None` returning the persisted playbook row plus a computed `is_stale: bool`. The `is_stale` value SHALL be `True` when any of the following hold:

1. (Existing conditions covered by other capabilities — if any pre-S20c stale conditions apply, those still trigger `True`.)
2. The current attachment-set hash for the meeting differs from `playbook.attachment_hash_snapshot`. The current attachment-set hash is computed as `sha256(sorted(sha256(open(att.file_path,'rb').read()) for att in MeetingAttachmentRepository.list_for_meeting(meeting_id) if att.deleted_at IS NULL))`, expressed as a lowercase hex string. The empty-attachment set SHALL hash to the canonical empty-set hash `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`.

Legacy rows where `attachment_hash_snapshot IS NULL` SHALL be treated as if they recorded the empty-set hash — so a meeting with zero attachments and a NULL snapshot is NOT stale, but a meeting with one attachment and a NULL snapshot IS stale (the row was written before attachment tracking existed; the new attachment is real new context).

#### Scenario: Playbook stays fresh when attachment set is unchanged

- **GIVEN** a meeting with a playbook generated at T0 whose `attachment_hash_snapshot` matches the current attachment-set hash
- **WHEN** `PlaybookRepository.get_with_stale_flag(meeting_id)` runs at T0 + 1 hour
- **THEN** the returned object's `is_stale` SHALL be `False`

#### Scenario: Adding a new attachment marks the playbook stale

- **GIVEN** a meeting with one PDF whose playbook was generated and the row's `attachment_hash_snapshot` matches the one-PDF current hash
- **WHEN** a second PNG attachment is uploaded for that meeting AND `PlaybookRepository.get_with_stale_flag(meeting_id)` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Deleting an attachment marks the playbook stale

- **GIVEN** a meeting whose playbook was generated with two attachments and `attachment_hash_snapshot` matches that two-attachment hash
- **WHEN** one attachment is soft-deleted (`deleted_at = now()`) and `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Replacing an attachment with identical content does NOT mark stale

- **GIVEN** a meeting whose playbook was generated with one PDF whose bytes hash to `h_pdf`
- **WHEN** the user deletes that attachment and uploads a different `AttachmentRef` row whose file bytes are byte-identical (hash to the same `h_pdf`)
- **THEN** the current attachment-set hash SHALL still equal `attachment_hash_snapshot` AND `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with no current attachments is NOT stale

- **GIVEN** a playbook row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has zero non-deleted attachments
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with new attachment IS stale

- **GIVEN** a playbook row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting now has one PDF attachment
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`
