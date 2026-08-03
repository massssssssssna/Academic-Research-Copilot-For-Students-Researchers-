"""
Jarvis Voice Agent - Powered by LiveKit Agents Framework
Real-time Multimodal Voice Agent (STT -> LLM/Tools -> TTS)
"""

import asyncio
import logging
from typing import Annotated
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, silero

from app.agent.tools import jarvis_tools
from app.config import settings

# Configure logger
logger = logging.getLogger("jarvis-livekit-voice-agent")
logger.setLevel(logging.INFO)

SYSTEM_PROMPT = """You are Jarvis, an AI Copilot integrated with Microsoft 365.
Your primary role is to assist users in managing emails (drafting only), scheduling calendar events, and organizing tasks.

Rules:
1. Speak naturally, clearly, and concisely.
2. For casual questions or greetings, respond as a friendly AI assistant without using tools.
3. Only use Microsoft 365 tools when explicitly asked to perform a task.
4. You cannot send emails directly; only create drafts for user review.
"""

async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent Entrypoint.
    Establishes real-time WebRTC audio connection and runs VoicePipelineAgent.
    """
    logger.info(f"Connecting Jarvis Voice Agent to room: {ctx.room.name}")
    
    # Connect to room with audio subscription enabled
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize LiveKit Chat Context with System Prompt
    chat_context = llm.ChatContext().append(
        role="system",
        text=SYSTEM_PROMPT,
    )

    # Initialize LiveKit VoicePipelineAgent (STT -> LLM/Tools -> TTS)
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=openai.STT(),
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.7,
        ),
        tts=openai.TTS(
            voice="alloy",
            speed=1.0,
        ),
        chat_ctx=chat_context,
    )

    # Start the Voice Agent in the LiveKit room
    agent.start(ctx.room)
    
    # Greet user upon joining room
    await agent.say("Hello! I am Jarvis, your AI Copilot. How can I assist you with your Microsoft 365 tasks today?", allow_interruptions=True)

def main():
    """Run LiveKit Worker process."""
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

if __name__ == "__main__":
    main()
