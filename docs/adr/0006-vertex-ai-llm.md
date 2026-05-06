# ADR-0006: Vertex AI as the LLM provider

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The reference article uses Claude Opus, made cost-effective by routing through a Claude.ai subscription. That route is closed: Claude API and Claude.ai subscriptions are billed independently. The same is true of Gemini Advanced vs the Google AI Studio / Vertex AI APIs.

The user explicitly chose Vertex AI over Google AI Studio Paid, accepting the higher setup cost (GCP project, IAM, billing) in exchange for enterprise-tier data handling and a path to commercial deploy if needed.

## Decision
Use Vertex AI via the official `google-genai` SDK.

Two model tiers:
- **Gemini Flash** family — for the in-meeting tactical advisor where latency matters more than quality.
- **Gemini 2.5 Pro** — for post-meeting summary and pre-meeting playbook generation where quality matters more than latency.

Concrete model versions are configurable; the SDK abstraction lets us swap model IDs without code changes.

## Consequences
- One-time GCP project + Vertex AI API enablement + IAM service account.
- Same GCP project hosts the OAuth client used by Better Auth (ADR-0021) and the Google Calendar OAuth used for pre-meeting (ADR-0015).
- Audio is transcribed locally and only text reaches Vertex AI; raw audio never leaves the device.

## Alternatives considered
- **Google AI Studio Paid** — simpler setup but weaker enterprise story for future deploy.
- **OpenAI / Claude API** — more cost lines, no Google ecosystem alignment.
- **Local LLM (Ollama gemma3:27b or similar)** — M3 Pro 18GB cannot comfortably run 27B+ models alongside ASR.
