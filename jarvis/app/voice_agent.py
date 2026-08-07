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

# ── Windows Compatibility Patch for LiveKit C-extensions ──
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

# Patch blingfire native DLL requirement on Windows
def _dummy_text_to_sentences_with_offsets(text):
    return [text], [(0, len(text))]

def _dummy_text_to_words_with_offsets(text):
    words = text.split()
    offsets = []
    curr = 0
    for w in words:
        start = text.find(w, curr)
        offsets.append((start, start + len(w)))
        curr = start + len(w)
    return words, offsets

_dummy_blingfire = types.ModuleType("livekit.blingfire")
_dummy_blingfire.text_to_sentences = lambda text: [text]
_dummy_blingfire.text_to_words = lambda text: text.split()
_dummy_blingfire.text_to_sentences_with_offsets = _dummy_text_to_sentences_with_offsets
_dummy_blingfire.text_to_words_with_offsets = _dummy_text_to_words_with_offsets
sys.modules["livekit.blingfire"] = _dummy_blingfire


# Load .env before any LiveKit imports
load_dotenv(override=True)


from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import cartesia, deepgram, groq

from app.config import settings

logger = logging.getLogger("jarvis-voice-agent")
logger.setLevel(logging.INFO)

from datetime import datetime, timezone, timedelta

def get_system_instructions() -> str:
    now_utc = datetime.now(timezone.utc)
    pkt_tz = timezone(timedelta(hours=5))
    now_pkt = now_utc.astimezone(pkt_tz)
    
    date_str = now_pkt.strftime("%A, %B %d, %Y")
    time_str = now_pkt.strftime("%I:%M %p")
    utc_time_str = now_utc.strftime("%H:%M UTC")
    
    return (
        "You are Jarvis, an advanced AI Copilot for Microsoft 365. Speak naturally, directly, and clearly.\n\n"
        "LIVE ACCESS RULES:\n"
        "- YOU HAVE FULL LIVE API ACCESS to the user's Microsoft 365 account via your function tools!\n"
        "- NEVER say 'I don't have access', 'I cannot fetch', or 'I need permission'. You already have full access!\n"
        "- When asked to fetch emails, read emails, delete emails/drafts, delete all drafts, schedule or delete meetings, or manage To-Do tasks, ALWAYS invoke the appropriate function tool immediately.\n"
        "- STRICT PRIVACY RULE: NEVER send emails automatically (`create_draft` and `delete_email` are allowed, but sending emails is forbidden).\n\n"
        "REAL-TIME CLOCK CONTEXT (Pakistan Standard Time, PKT, UTC+5):\n"
        f"- Current Date: {date_str}\n"
        f"- Current Local Time in Pakistan: {time_str} PKT (UTC+5) / {utc_time_str}\n\n"
        "CONVERSATIONAL STYLE:\n"
        "1. Speak directly, naturally, and concisely (1-2 short plain sentences max).\n"
        "2. Do NOT use fake sweetness, over-polite filler, or lengthy introductions.\n"
        "3. Always perform the requested action using your tools immediately."
    )


class JarvisAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=get_system_instructions())

    async def on_enter(self) -> None:
        logger.info("Jarvis Agent entered session — waiting silently for user prompt.")
        # Jarvis remains completely silent on join and only responds when the user speaks!


from livekit.plugins import cartesia, deepgram, groq, openai
from app.edge_tts_provider import EdgeTTS

async def entrypoint(ctx: JobContext) -> None:
    logger.info(f"Jarvis Voice Agent connecting to room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    deepgram_key = settings.DEEPGRAM_API_KEY or os.getenv("DEEPGRAM_API_KEY")
    cartesia_key = settings.CARTESIA_API_KEY or os.getenv("CARTESIA_API_KEY")
    groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")

    if deepgram_key:
        stt_impl = deepgram.STT(api_key=deepgram_key)
    elif openai_key:
        stt_impl = openai.STT(api_key=openai_key)
    else:
        logger.info("Using Groq STT (Whisper) via GROQ_API_KEY.")
        stt_impl = groq.STT(api_key=groq_key)

    if deepgram_key:
        logger.info("Using Deepgram Aura TTS via DEEPGRAM_API_KEY.")
        tts_impl = deepgram.TTS(api_key=deepgram_key, model="aura-asteria-en")
    elif cartesia_key:
        logger.info("Using Cartesia TTS via CARTESIA_API_KEY.")
        tts_impl = cartesia.TTS(api_key=cartesia_key, voice="f786b574-daa5-4673-aa0c-cbe3e8534c02")
    elif openai_key:
        logger.info("Using OpenAI TTS via OPENAI_API_KEY.")
        tts_impl = openai.TTS(api_key=openai_key)
    else:
        logger.info("Using High-Quality Free Edge-TTS (Microsoft Ava Neural).")
        tts_impl = EdgeTTS(voice="en-US-AvaNeural")

    from livekit.agents.llm import FallbackAdapter
    groq_keys = settings.get_groq_api_keys()
    if not groq_keys:
        single_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        if single_key: groq_keys = [single_key]

    llm_pool = []
    models_pool = [settings.LLM_FAST_MODEL, settings.LLM_PRIMARY_MODEL, settings.LLM_FALLBACK_MODEL]
    for k in groq_keys:
        for m_name in models_pool:
            llm_pool.append(groq.LLM(api_key=k, model=m_name))

    if llm_pool:
        voice_llm = FallbackAdapter(llm=llm_pool, attempt_timeout=5.0, max_retry_per_llm=1)
    else:
        voice_llm = groq.LLM(api_key=settings.GROQ_API_KEY, model=settings.LLM_FAST_MODEL)

    logger.info(f"Configured Voice Agent FallbackAdapter with {len(llm_pool)} failover instances across {len(groq_keys)} Groq API key(s).")

    session = AgentSession(
        stt=stt_impl,
        llm=voice_llm,
        tts=tts_impl,
        tools=agent_tools,
        min_endpointing_delay=1.0,
        max_endpointing_delay=2.0,
        allow_interruptions=True,
        min_interruption_duration=0.1,
        min_interruption_words=1,
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
            agent_name="jarvis",
            ws_url=settings.LIVEKIT_URL or os.getenv("LIVEKIT_URL"),
            api_key=settings.LIVEKIT_API_KEY or os.getenv("LIVEKIT_API_KEY"),
            api_secret=settings.LIVEKIT_API_SECRET or os.getenv("LIVEKIT_API_SECRET"),
        )
    )



if __name__ == "__main__":
    main()



