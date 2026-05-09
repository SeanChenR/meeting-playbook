"""Playbook draft generation — Vertex AI Gemini 2.5 Pro deep module.

See docs/agents/playbook-generation.md for invariants. The generator
output shape is identical to PlaybookUpsertPayload so callers can pass it
straight to PlaybookRepository.upsert_for_meeting without remapping.
"""
