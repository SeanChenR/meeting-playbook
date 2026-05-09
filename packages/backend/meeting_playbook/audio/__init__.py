"""Audio capture — `sounddevice` wrapper + WAV writer + silence detector.

Per slice-06 design (`AudioCaptureService shape`): single async-context-manager
that yields `AudioChunk` and `SilenceWarning` events to the session
orchestrator. WAV file is finalized atomically on context exit.
"""
