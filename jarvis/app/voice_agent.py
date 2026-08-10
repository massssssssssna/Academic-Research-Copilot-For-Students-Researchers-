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
from livekit.agents.voice.turn import TurnHandlingOptions
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
        "You are Jarvis — a smart, friendly personal assistant. "
        "You sound like a helpful, warm human friend, not a machine, copilot, or computer program.\n\n"

        "UNCLEAR INPUT & FAILURE RULE (CRITICAL):\n"
        "- If you did not clearly understand the user, or if the user's speech was partial, quiet, or confusing (e.g. 'tell me', 'uhh', background noise): "
        "DO NOT explain who you are, DO NOT list your capabilities, and DO NOT mention any tools!\n"
        "- Straight up say naturally: 'Sorry, I didn't catch that. Could you say that again?' or 'Samajh nahi aaya, dobara bolenge?'\n\n"

        "CALENDAR & UPCOMING EVENTS FILTERING (CRITICAL):\n"
        "- When asked for 'upcoming events', 'next meetings', 'what's next', or 'future events': ONLY mention events under UPCOMING or TODAY. NEVER confuse or list past events as upcoming!\n"
        "- If asked for 'past events', list only past meetings.\n"
        "- If asked 'what's on my calendar', summarize Today's events first, then Upcoming events.\n\n"

        "TO-DO & TASK FILTERING (CRITICAL):\n"
        "- Distinguish clearly between OVERDUE, PENDING (upcoming), and COMPLETED tasks.\n"
        "- When asked for 'pending tasks' or 'to-do list', talk about overdue and pending tasks. Do not describe completed tasks as active.\n\n"

        "PERSONALITY & TONE:\n"
        "- Be natural, casual, and conversational — like ChatGPT or a smart friend talking on the phone.\n"
        "- Keep replies SHORT: 1-2 sentences max when talking out loud.\n"
        "- Never use bullet points, numbered lists, markdown, or formatting in speech.\n"
        "- React naturally to what the user says, don't repeat the same opener every time.\n\n"

        "STRICT IDENTITY BANS — NEVER SAY THESE:\n"
        "- NEVER say 'I am a Microsoft 365 copilot', 'I am an assistant for Microsoft 365', 'I am a computer program', 'I am an AI', 'I am a language model', or any variation.\n"
        "- NEVER say 'As an AI, I...', 'As a language model...', 'I don't have feelings'.\n"
        "- If asked 'who are you?', say: 'I'm Jarvis! What do you need?'\n"
        "- If asked 'what can you do?', keep it simple: 'I can read your emails, check your calendar, or manage your to-dos. What's on your mind?'\n"
        "- NEVER start replies with 'Hello!' or 'Hi!' after the initial greeting — just respond naturally.\n\n"

        "CASUAL GREETINGS:\n"
        "- If the user says 'Hi', 'Hello', or 'Hey' — reply warmly and briefly, e.g.: 'Hey! What's up?' or 'Hey there! What can I do for you?'\n"
        "- Never mention the date or time unless the user explicitly asks.\n\n"

        "CONVERSATIONAL MEMORY & MULTI-TURN CONTEXT (CRITICAL):\n"
        "- REMEMBER EVERYTHING SAID PREVIOUSLY in this ongoing call session!\n"
        "- If the user previously said 'Make a draft email', and then in the next turn provides 'to massna@gmail.com' or 'subject Project Update', ALWAYS connect these details to the draft request!\n"
        "- Never forget or lose context of what topic, email, meeting, or task was discussed in the previous turns.\n"
        "- Accumulate email recipient, subject, and content across multiple turns before calling create_draft_email.\n\n"

        "INTERACTIVE STYLE (ChatGPT-like):\n"
        "- EMAIL DRAFTS: If recipient, subject, or body is missing, ask naturally: 'Who's this email going to, and what should it say?'\n"
        "- TASKS & MEETINGS: If date/time is missing, ask: 'What time works for you?' or 'When's the deadline?'\n"
        "- Confirm details interactively before performing actions.\n\n"

        "TOOLS & BACKEND:\n"
        "- You have function tools for Outlook emails, Calendar, and To-Do. Use them when requested.\n"
        "- NEVER say you lack access. Just run the tool silently and answer in 1 sentence.\n"
        "- PRIVACY: You can draft or delete emails, but NEVER send emails automatically.\n\n"

        "ZERO HALLUCINATION RULE:\n"
        "- NEVER claim a task is done without executing the function tool first.\n"
        "- Wait for the tool result, then report it in one natural sentence.\n\n"

        "SPEECH FORMATTING:\n"
        "- NEVER speak raw code, '.function=', 'function=', JSON, or schema names out loud.\n\n"

        f"CURRENT TIME CONTEXT (use only if asked):\n"
        f"- Date: {date_str}\n"
        f"- Time: {time_str}\n"
        "- Speak time naturally ('4:30 PM'). Never say 'PKT' or 'UTC'.\n"
    )


class JarvisAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=get_system_instructions())

    async def on_enter(self) -> None:
        """Say a short greeting immediately when the user connects."""
        logger.info("Jarvis Agent entered session — sending greeting.")
        await self.session.say(
            "Hi! I'm Jarvis. How can I help you?",
            allow_interruptions=True,
        )


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
        logger.info("Using Deepgram STT (nova-2-conversationalai) with smart formatting.")
        stt_impl = deepgram.STT(
            api_key=deepgram_key,
            model="nova-2-conversationalai",
            smart_format=True
        )
    elif groq_key:
        logger.info("Using Groq Whisper STT (whisper-large-v3).")
        stt_impl = groq.STT(api_key=groq_key, model="whisper-large-v3")
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
        try:
            from app.database.supabase import supabase_db
            active_s = supabase_db.get_user_session("")
            if active_s:
                session_id = active_s.get("session_id", "")
        except Exception:
            pass

    logger.info(f"LiveKit Agent session user authenticated session_id: {session_id[:8] if session_id else 'Auto-Resolved'}...")

    # Define LiveKit function tools bound to current session_id
    @llm.function_tool(description="Fetch latest emails from user inbox or drafts folder ('inbox' or 'drafts').")
    async def get_user_emails(folder: str = "inbox") -> str:
        from app.agent.tools import get_emails
        return get_emails.invoke({"session_id": session_id or "", "folder": folder, "top": 5})

    @llm.function_tool(description="Read full content of a specific email by message_id.")
    async def read_user_email(message_id: str) -> str:
        from app.agent.tools import get_email
        return get_email.invoke({"session_id": session_id or "", "message_id": message_id})

    @llm.function_tool(description="Create a draft email in Microsoft Outlook.")
    async def create_draft_email(subject: str, content: str, to_recipients: str) -> str:
        from app.agent.tools import create_email_draft
        recipients = [r.strip() for r in to_recipients.split(",") if r.strip()]
        return create_email_draft.invoke({"session_id": session_id or "", "subject": subject, "content": content, "to_recipients": recipients})

    @llm.function_tool(description="Delete a specific email or draft email by message_id.")
    async def delete_user_email(message_id: str) -> str:
        from app.agent.tools import delete_email
        return delete_email.invoke({"session_id": session_id or "", "message_id": message_id})

    @llm.function_tool(description="Delete ALL draft emails in the user's Outlook Drafts folder.")
    async def delete_all_user_drafts() -> str:
        from app.agent.tools import delete_all_drafts
        return delete_all_drafts.invoke({"session_id": session_id or ""})

    @llm.function_tool(description="Summarize an incoming inbox email and create a draft reply.")
    async def summarize_and_draft(message_id: str, custom_notes: str = "") -> str:
        from app.agent.tools import summarize_and_draft_reply
        return summarize_and_draft_reply.invoke({"session_id": session_id or "", "message_id": message_id, "custom_notes": custom_notes})

    @llm.function_tool(description="Fetch calendar events for the user.")
    async def get_calendar_events() -> str:
        from app.agent.tools import get_events
        return get_events.invoke({"session_id": session_id or "", "top": 5})

    @llm.function_tool(description="Create a calendar event/meeting in Pakistan Standard Time (PKT, UTC+5).")
    async def create_calendar_event(subject: str, start_time: str, end_time: str, time_zone: str = "Pakistan Standard Time") -> str:
        from app.agent.tools import create_event
        return create_event.invoke({"session_id": session_id or "", "subject": subject, "start_time": start_time, "end_time": end_time, "time_zone": time_zone})

    @llm.function_tool(description="Delete a calendar event/meeting by event_id.")
    async def delete_calendar_event(event_id: str) -> str:
        from app.agent.tools import delete_event
        return delete_event.invoke({"session_id": session_id or "", "event_id": event_id})

    @llm.function_tool(description="Fetch user To-Do task list.")
    async def get_todo_tasks() -> str:
        from app.agent.tools import get_todos
        return get_todos.invoke({"session_id": session_id or ""})

    @llm.function_tool(description="Create a new To-Do task.")
    async def create_todo_task(title: str, due_date: str = "", due_time: str = "") -> str:
        from app.agent.tools import create_todo
        return create_todo.invoke({"session_id": session_id or "", "title": title, "due_date": due_date, "due_time": due_time})

    @llm.function_tool(description="Mark a To-Do task as completed by task_id.")
    async def complete_todo_task(task_id: str) -> str:
        from app.agent.tools import update_todo
        return update_todo.invoke({"session_id": session_id or "", "task_id": task_id, "status": "completed"})

    @llm.function_tool(description="Delete a task from To-Do list by task_id.")
    async def delete_todo_task(task_id: str) -> str:
        from app.agent.tools import delete_todo
        return delete_todo.invoke({"session_id": session_id or "", "task_id": task_id})

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
    models_pool = [settings.LLM_PRIMARY_MODEL, settings.LLM_FAST_MODEL]
    for k in groq_keys:
        for m_name in models_pool:
            llm_pool.append(groq.LLM(api_key=k, model=m_name))

    if llm_pool:
        voice_llm = FallbackAdapter(llm=llm_pool, attempt_timeout=5.0, max_retry_per_llm=1)
    else:
        voice_llm = groq.LLM(api_key=settings.GROQ_API_KEY, model=settings.LLM_FAST_MODEL)

    logger.info(f"Configured Voice Agent FallbackAdapter with {len(llm_pool)} failover instances across {len(groq_keys)} Groq API key(s).")

    turn_opts = TurnHandlingOptions(
        min_endpointing_delay=0.6,
        max_endpointing_delay=1.8,
        allow_interruptions=True,
        min_interruption_duration=0.15,
        min_interruption_words=1,
    )
    session = AgentSession(
        stt=stt_impl,
        llm=voice_llm,
        tts=tts_impl,
        tools=agent_tools,
        turn_handling=turn_opts,
        preemptive_generation=False,  # CRITICAL: disables premature generation while user is still speaking!
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



