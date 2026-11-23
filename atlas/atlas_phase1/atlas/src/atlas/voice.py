"""Voice hook (phase 2). Implement VoiceIO with STT (Parakeet / faster-whisper) and TTS (Kokoro).

The CLI calls `get_voice(cfg)`; with voice disabled it returns NullVoice and nothing changes.
"""

from __future__ import annotations

from typing import Protocol


class VoiceIO(Protocol):
    def listen(self) -> str: ...            # block until an utterance is transcribed
    def speak(self, text: str) -> None: ...  # synthesize and play


class NullVoice:
    enabled = False

    def listen(self) -> str:
        raise NotImplementedError("Voice arrives in phase 2 (wake word + Parakeet STT + Kokoro TTS).")

    def speak(self, text: str) -> None:
        return None


def get_voice(cfg) -> VoiceIO:
    # Phase 2: if cfg.voice_enabled: return LocalVoice(cfg)
    return NullVoice()
