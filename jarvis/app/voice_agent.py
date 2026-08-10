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
    time_str = now_pkt.strftime("%I:%M %p").lstrip("0")
    
    return (
        "You are Jarvis, an advanced AI Copilot for Microsoft 365. Speak naturally, directly, and clearly.\n\n"
        "LIVE ACCESS RULES:\n"
        "- YOU HAVE FULL LIVE API ACCESS to the user's Microsoft 365 account via your function tools!\n"
        "- NEVER say 'I don't have access', 'I cannot fetch', or 'I need permission'. You already have full access!\n"
        "- When asked to fetch emails, read emails, delete emails/drafts, delete all drafts, schedule or delete meetings, or manage To-Do tasks, ALWAYS invoke the appropriate function tool immediately.\n"
        "- STRICT PRIVACY RULE: NEVER send emails automatically (`create_draft` and `delete_email` are allowed, but sending emails is forbidden).\n\n"
        "STRICT TOOL EXECUTION MANDATE (ZERO HALLUCINATIONS):\n"
        "- NEVER lie, fake, or claim that an action (creating calendar meeting, deleting email/draft, creating draft, creating/completing task, summarizing email) is done without actually calling the function tool first!\n"
        "- Whenever the user asks to perform an action, you MUST ALWAYS execute the tool call FIRST, wait for the response, and report the true execution result.\n"
        "- If a tool call has not been executed, NEVER claim that the task or meeting was created or deleted!\n\n"
        "REAL-TIME CLOCK CONTEXT:\n"
        f"- Current Date: {date_str}\n"
        f"- Current Time: {time_str}\n\n"
        "NATURAL TIME SPEAKING RULE:\n"
        "- When asked for the time, speak it cleanly and naturally like '10:45 AM' or '4:55 PM'.\n"
        "- NEVER speak technical jargon or acronyms like 'PKT', 'UTC', or 'Pakistan Standard Time' out loud when answering time questions!\n\n"
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

    import json
    session_id = ""
    if ctx.room.metadata:
        try:
            m_data = json.loads(ctx.room.metadata)
            session_id = m_data.get("session_id", "")
        except Exception:
            pass

    if not session_id:
        for p in ctx.room.remote_participants.values():
            if p.metadata:
                try:
                    m_data = json.loads(p.metadata)
                    session_id = m_data.get("session_id", "")
                    if session_id: break
                except Exception:
                    pass

    logger.info(f"LiveKit Agent session user authenticated session_id: {session_id[:8] if session_id else 'None'}...")

    # Define LiveKit function tools bound to current session_id
    @llm.function_tool(description="Fetch latest emails from user inbox or drafts folder ('inbox' or 'drafts').")
    async def get_user_emails(folder: str = "inbox") -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import get_emails
        return get_emails.invoke({"session_id": session_id, "folder": folder, "top": 5})

    @llm.function_tool(description="Read full content of a specific email by message_id.")
    async def read_user_email(message_id: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import get_email
        return get_email.invoke({"session_id": session_id, "message_id": message_id})

    @llm.function_tool(description="Create a draft email in Microsoft Outlook.")
    async def create_draft_email(subject: str, content: str, to_recipients: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import create_email_draft
        recipients = [r.strip() for r in to_recipients.split(",") if r.strip()]
        return create_email_draft.invoke({"session_id": session_id, "subject": subject, "content": content, "to_recipients": recipients})

    @llm.function_tool(description="Delete a specific email or draft email by message_id.")
    async def delete_user_email(message_id: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import delete_email
        return delete_email.invoke({"session_id": session_id, "message_id": message_id})

    @llm.function_tool(description="Delete ALL draft emails in the user's Outlook Drafts folder.")
    async def delete_all_user_drafts() -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import delete_all_drafts
        return delete_all_drafts.invoke({"session_id": session_id})

    @llm.function_tool(description="Summarize an incoming inbox email and create a draft reply.")
    async def summarize_and_draft(message_id: str, custom_notes: str = "") -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import summarize_and_draft_reply
        return summarize_and_draft_reply.invoke({"session_id": session_id, "message_id": message_id, "custom_notes": custom_notes})

    @llm.function_tool(description="Fetch calendar events for the user.")
    async def get_calendar_events() -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import get_events
        return get_events.invoke({"session_id": session_id, "top": 5})

    @llm.function_tool(description="Create a calendar event/meeting in Pakistan Standard Time (PKT, UTC+5).")
    async def create_calendar_event(subject: str, start_time: str, end_time: str, time_zone: str = "Pakistan Standard Time") -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import create_event
        return create_event.invoke({"session_id": session_id, "subject": subject, "start_time": start_time, "end_time": end_time, "time_zone": time_zone})

    @llm.function_tool(description="Delete a calendar event/meeting by event_id.")
    async def delete_calendar_event(event_id: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import delete_event
        return delete_event.invoke({"session_id": session_id, "event_id": event_id})

    @llm.function_tool(description="Fetch user To-Do task list.")
    async def get_todo_tasks() -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import get_todos
        return get_todos.invoke({"session_id": session_id})

    @llm.function_tool(description="Create a new To-Do task.")
    async def create_todo_task(title: str, due_date: str = "", due_time: str = "") -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import create_todo
        return create_todo.invoke({"session_id": session_id, "title": title, "due_date": due_date, "due_time": due_time})

    @llm.function_tool(description="Mark a To-Do task as completed by task_id.")
    async def complete_todo_task(task_id: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import update_todo
        return update_todo.invoke({"session_id": session_id, "task_id": task_id, "status": "completed"})

    @llm.function_tool(description="Delete a task from To-Do list by task_id.")
    async def delete_todo_task(task_id: str) -> str:
        if not session_id: return "No active user session."
        from app.agent.tools import delete_todo
        return delete_todo.invoke({"session_id": session_id, "task_id": task_id})

    agent_tools = [
        get_user_emails,
        read_user_email,
        create_draft_email,
        delete_user_email,
        delete_all_user_drafts,
        summarize_and_draft,
        get_calendar_events,
        create_calendar_event,
        delete_calendar_event,
        get_todo_tasks,
        create_todo_task,
        complete_todo_task,
        delete_todo_task
    ]

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



