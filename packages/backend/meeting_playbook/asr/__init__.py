"""ASR (Automatic Speech Recognition) interface and implementations.

Per ADR-0005: ASR engines are pluggable behind the `ASRProvider` Protocol
defined in `base`. The session router accepts any object satisfying the
Protocol via dependency injection — concrete providers (Whisper, VibeVoice,
etc.) are NOT imported by the router.
"""
