"""
Jarvis Multimodal Voice Agent — LiveKit Agents + Deepgram STT + Groq LLM + Cartesia TTS
======================================================================================
Architecture:
  User Microphone → LiveKit Room (WebRTC)
    → Deepgram STT (Speech-to-Text)
    → Groq LLM (llama-3.3-70b-versatile reasoning)
    → Cartesia TTS (Text-to-Speech synthesis)
    ← Audio streamed back via WebRTC

Environment Variables Required (.env):
  LIVEKIT_URL          - LiveKit server WebSocket URL
  LIVEKIT_API_KEY      - LiveKit API key
  LIVEKIT_API_SECRET   - LiveKit API secret
  DEEPGRAM_API_KEY     - Deepgram API key (STT)
  GROQ_API_KEY         - Groq API key (LLM)
  CARTESIA_API_KEY     - Cartesia API key (TTS)
"""

import logging
import os
import sys
import types
from dotenv import load_dotenv

# ── Windows Compatibility Patch for livekit.local_inference ──
class _DummyInference:
    def __init__(self, *args, **kwargs):
        pass
    def predict(self, *args, **kwargs):
        return 0.0
    def reset(self, *args, **kwargs):
        pass
    @classmethod
    def load(cls, *args, **kwargs):
        return cls()

_dummy_mod = types.ModuleType("livekit.local_inference")
for _attr in ["EOT", "VAD", "STT", "TTS", "LLM", "Whisper", "SileroVAD"]:
    setattr(_dummy_mod, _attr, _DummyInference)
_dummy_mod.VAD_WINDOW_SAMPLES = 512
sys.modules["livekit.local_inference"] = _dummy_mod

# Load .env before any LiveKit imports
load_dotenv(override=True)


from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import cartesia, deepgram, groq

from app.config import settings

logger = logging.getLogger("jarvis-voice-agent")
logger.setLevel(logging.INFO)

SYSTEM_INSTRUCTIONS = (
    "You are Jarvis, a highly intelligent and conversational AI voice assistant. "
    "You assist users naturally with any question they have. "
    "Speak clearly, concisely, and in a friendly tone. "
    "Keep responses brief — you are speaking out loud in real time."
)


class JarvisAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_INSTRUCTIONS)

    async def on_enter(self) -> None:
        logger.info("Jarvis Agent entered session — greeting user.")
        await self.session.generate_reply(
            instructions="Greet the user warmly and briefly introduce yourself as Jarvis, powered by Deepgram, Groq, and Cartesia."
        )


async def entrypoint(ctx: JobContext) -> None:
    logger.info(f"Jarvis Voice Agent connecting to room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        stt=deepgram.STT(api_key=settings.DEEPGRAM_API_KEY or os.getenv("DEEPGRAM_API_KEY")),
        llm=groq.LLM(
            api_key=settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY"),
            model=settings.LLM_PRIMARY_MODEL,
        ),
        tts=cartesia.TTS(
            api_key=settings.CARTESIA_API_KEY or os.getenv("CARTESIA_API_KEY"),
            voice="f786b574-daa5-4673-aa0c-cbe3e8534c02",
        ),
    )

    await session.start(
        agent=JarvisAgent(),
        room=ctx.room,
    )
    logger.info("Jarvis Voice Agent session started and ready.")


def main() -> None:
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.LIVEKIT_URL or os.getenv("LIVEKIT_URL"),
            api_key=settings.LIVEKIT_API_KEY or os.getenv("LIVEKIT_API_KEY"),
            api_secret=settings.LIVEKIT_API_SECRET or os.getenv("LIVEKIT_API_SECRET"),
        )
    )


if __name__ == "__main__":
    main()



