"""In-meeting session — WS endpoint, audio capture orchestration, transcript persistence.

Per slice-06 design: this module owns the lifecycle of an active meeting
session (start → capture → transcribe → persist → end). Concrete ASR
providers and AudioCaptureService instances are injected; this module
imports only the contracts.
"""
