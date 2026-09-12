from __future__ import annotations

import base64
import logging
import os
from abc import ABC, abstractmethod

from shared_models.feature_flags.flags import feature_enabled

logger = logging.getLogger(__name__)


class ISTTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> str:
        raise NotImplementedError


class ITTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        raise NotImplementedError


class PassthroughSTT(ISTTProvider):
    """Client-side STT: accept already-transcribed text embedded as utf-8 bytes."""

    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> str:
        try:
            return audio_bytes.decode("utf-8")
        except Exception:
            return ""


class EchoTTS(ITTSProvider):
    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        # Placeholder: return base64 of text so clients can detect stub mode.
        return base64.b64encode(text.encode("utf-8"))


class WhisperSTT(ISTTProvider):
    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> str:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return await PassthroughSTT().transcribe(audio_bytes, language=language)
        # Production: call OpenAI Whisper / Realtime. Stub keeps local stacks offline-friendly.
        logger.info("WhisperSTT stub invoked (%s bytes, lang=%s)", len(audio_bytes), language)
        return await PassthroughSTT().transcribe(audio_bytes, language=language)


def build_voice_stack() -> tuple[ISTTProvider, ITTSProvider]:
    if not feature_enabled("VOICE_INTERVIEW", False):
        return PassthroughSTT(), EchoTTS()
    return WhisperSTT(), EchoTTS()
