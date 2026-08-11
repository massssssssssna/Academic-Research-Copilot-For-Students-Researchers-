"""
Jarvis Chat Route — Guaranteed Agentic RAG + Web Search Engine
===============================================================
Ensures 100% deterministic RAG and Web Search execution.
When a query requires document search (RAG), web search, or both,
this route executes the tool pipeline directly BEFORE calling the LLM,
guaranteeing that context is retrieved and synthesized without relying on
unpredictable tool-choice behavior from rate-limited LLMs.
"""

import re
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_groq import ChatGroq
import os

from app.config import settings
from app.agent.graph import jarvis_agent
from app.agent.state import AgentState
from app.agent.tools import search_documents, web_search
from app.database.supabase import supabase_db

router = APIRouter(prefix="/api", tags=["Chat"])


# ──────────────────────────────────────────────────────────────────────────────
# Classification Engine (deterministic, keyword & pattern based)
# ──────────────────────────────────────────────────────────────────────────────

_RAG_KEYWORDS = [
    r"\bdocument\b", r"\bpdf\b", r"\bdocx\b", r"\bfile\b", r"\bupload",
    r"\baccording to\b", r"\bbased on\b", r"\bmy research\b", r"\bmy notes\b",
    r"\bmy guide\b", r"\bknowledge base\b", r"\brag\b", r"\bmy paper\b",
    r"\bprototype\b", r"\bweek \d\b", r"\bproject review\b", r"\bmeeting schedule\b",
    r"\bassignment\b", r"\bworkflow\b", r"\bsource evaluation\b", r"\bliterature\b",
    r"\bresearch guide\b", r"\bacademic\b", r"\bmy uploaded\b", r"\bmy document\b",
    r"\bmy pdf\b", r"\bwhat does my\b", r"\bwhat is in my\b", r"\bsummariz",
]

_WEB_KEYWORDS = [
    r"\blatest\b", r"\bcurrent\b", r"\bnews\b", r"\bonline\b", r"\btoday\b",
    r"\brecently\b", r"\bthis year\b", r"\b2024\b", r"\b2025\b", r"\b2026\b",
    r"\binternet\b", r"\bweb search\b", r"\bsearch the web\b", r"\blive\b",
    r"\breal.?time\b", r"\blatest research\b", r"\bwhat is happening\b",
    r"\bwhat happened\b", r"\bupdate\b", r"\btrend\b", r"\bannounce\b",
    r"\brelease\b", r"\bbreaking\b", r"\bnew version\b", r"\bwiki\b",
]

_GRAPH_KEYWORDS = [
    r"\bemail\b", r"\bmail\b", r"\binbox\b", r"\boutlook\b", r"\bdraft\b",
    r"\bsent\b", r"\bcalendar\b", r"\bevent\b", r"\bmeeting\b", r"\bappointment\b",
    r"\bschedule\b", r"\btask\b", r"\btasks\b", r"\bto.?do\b", r"\breminder\b",
    r"\battachment\b", r"\bpending task\b", r"\bmy task\b", r"\bmy to.?do\b",
    r"\bshow my task\b", r"\blist task\b",
]

_GREETING_ONLY = [
    r"^(hi|hello|hey|howdy|yo|salam|assalam|hola)\b[.!?]*$",
    r"^how are you[.!?]*$",
    r"^what('s| is) up[.!?]*$",
    r"^good (morning|afternoon|evening|night)[.!?]*$",
]


def _matches(text: str, patterns: list[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def classify_message(message: str) -> str:
    """
    Classifies message into 'rag', 'web', 'rag+web', 'graph', or 'direct'.
    """
    msg = message.strip()

    if _matches(msg, _GREETING_ONLY):
        return "direct"

    graph_hit = _matches(msg, _GRAPH_KEYWORDS)
    rag_hit = _matches(msg, _RAG_KEYWORDS)
    web_hit = _matches(msg, _WEB_KEYWORDS)

    if graph_hit and not rag_hit:
        return "graph"

    if rag_hit and web_hit and not graph_hit:
        rag_keywords_strong = [
            r"\bdocument\b", r"\bpdf\b", r"\bdocx\b", r"\bfile\b", r"\bupload",
            r"\baccording to\b", r"\bbased on\b", r"\bmy notes\b", r"\bmy guide\b",
            r"\bprototype\b", r"\bweek \d\b", r"\bproject review\b", r"\bmy paper\b",
            r"\bassignment\b", r"\bworkflow\b", r"\bsource evaluation\b",
            r"\bresearch guide\b", r"\bmy uploaded\b", r"\bmy document\b",
            r"\bmy pdf\b", r"\bknowledge base\b", r"\bsummariz",
        ]
        if _matches(msg, rag_keywords_strong):
            return "rag+web"
        return "web"

    if rag_hit:
        return "rag"
    if web_hit:
        return "web"

    if "?" in msg or len(msg.split()) >= 5:
        return "web"

    return "direct"


# ──────────────────────────────────────────────────────────────────────────────
# Helper to Invoke LLM for Context Synthesis
# ──────────────────────────────────────────────────────────────────────────────

def synthesize_response(prompt_content: str, history: list) -> str:
    """Invokes LLM with failover to synthesize an answer from retrieved context."""
    keys = settings.get_groq_api_keys()
    models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ]

    system_msg = SystemMessage(content=(
        "You are Jarvis, an intelligent academic copilot.\n"
        "RULES:\n"
        "1. NEVER introduce yourself (do NOT say 'I am Jarvis', 'I\'m Jarvis', 'Hello, I\'m Jarvis').\n"
        "2. Answer the user's question directly, clearly, and concisely using the provided context.\n"
        "3. Cite document sources or web links when available."
    ))

    recent_history = [m for m in history if not isinstance(m, SystemMessage)][-6:]
    messages = [system_msg] + recent_history + [HumanMessage(content=prompt_content)]

    for key in keys:
        for model in models:
            try:
                llm = ChatGroq(
                    groq_api_key=key,
                    model_name=model,
                    temperature=0.2,
                    max_tokens=2048,
                    max_retries=0,
                )
                res = llm.invoke(messages)
                if res and res.content:
                    return res.content.strip()
            except Exception as e:
                err = str(e)
                if "decommissioned" in err:
                    break
                continue

    # OpenAI Fallback
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(openai_api_key=openai_key, model_name="gpt-4o-mini", temperature=0.2)
            res = llm.invoke(messages)
            if res and res.content:
                return res.content.strip()
        except Exception:
            pass

    return "Unable to process response at this moment due to high traffic."


def clean_intro(text: str) -> str:
    """Strips any unwanted self-intro prefixes from the response."""
    intro_patterns = [
        r"^I'm Jarvis, an AI assistant for Microsoft 365\.\s*",
        r"^I am Jarvis, an AI assistant for Microsoft 365\.\s*",
        r"^Hello! I'm Jarvis, an AI assistant for Microsoft 365\.\s*",
        r"^Hello! I am Jarvis, an AI assistant\.\s*",
        r"^I'm Jarvis, an AI assistant\.\s*",
    ]
    cleaned = text
    for p in intro_patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ──────────────────────────────────────────────────────────────────────────────
# Chat Payload & Auth
# ──────────────────────────────────────────────────────────────────────────────

class ChatPayload(BaseModel):
    message: str
    conversation_id: Optional[str] = None


def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        return "default_jarvis_session"
    return session_id


# ──────────────────────────────────────────────────────────────────────────────
# Chat Endpoint
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(payload: ChatPayload, session_id: str = Depends(get_session_id)):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session = supabase_db.get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    user_id = session.get("user_id")

    conversation_id = payload.conversation_id
    messages_history = []

    if not conversation_id:
        title = payload.message[:50] + "..." if len(payload.message) > 50 else payload.message
        conversation_id = supabase_db.create_conversation(user_id, title)
    else:
        conv = supabase_db.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found or unauthorized")

        raw_messages = supabase_db.get_conversation_messages(user_id, conversation_id)
        for msg in raw_messages:
            if msg["role"] == "user":
                messages_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages_history.append(AIMessage(content=msg["content"]))

    # Add user message to DB
    supabase_db.add_message(user_id, conversation_id, "user", payload.message)

    # Classify request
    route = classify_message(payload.message)
    print(f"[ChatRoute] User message: '{payload.message[:60]}' -> Class: {route}")

    final_reply = ""
    tools_used = []
    tools_label = "Direct Answer"

    # ── PATH A: RAG (Document Search) ─────────────────────────────────────────
    if route == "rag":
        tools_used = ["search_documents"]
        tools_label = "RAG"
        rag_data = search_documents.invoke({"session_id": session_id, "query": payload.message})

        prompt = (
            f"Retrieved Document Context:\n{rag_data}\n\n"
            f"User Question: {payload.message}\n\n"
            f"Please answer the user question based strictly on the retrieved document context above. "
            f"Mention the source document name."
        )
        final_reply = synthesize_response(prompt, messages_history)

    # ── PATH B: WEB SEARCH ───────────────────────────────────────────────────
    elif route == "web":
        tools_used = ["web_search"]
        tools_label = "Web Search"
        web_data = web_search.invoke({"session_id": session_id, "query": payload.message})

        prompt = (
            f"Live Web Search Results:\n{web_data}\n\n"
            f"User Question: {payload.message}\n\n"
            f"Please answer the user question using the live web search results above. Include markdown links if available."
        )
        final_reply = synthesize_response(prompt, messages_history)

    # ── PATH C: MULTI-TOOL (RAG + WEB SEARCH) ─────────────────────────────────
    elif route == "rag+web":
        tools_used = ["search_documents", "web_search"]
        tools_label = "RAG + Web Search"

        rag_data = search_documents.invoke({"session_id": session_id, "query": payload.message})
        web_data = web_search.invoke({"session_id": session_id, "query": payload.message})

        prompt = (
            f"1. LOCAL DOCUMENT RAG CONTEXT:\n{rag_data}\n\n"
            f"2. LIVE WEB SEARCH RESULTS:\n{web_data}\n\n"
            f"User Question: {payload.message}\n\n"
            f"Synthesize both sources into a structured response.\n"
            f"Clearly format your response with two sections:\n"
            f"📄 **From Your Uploaded Documents:**\n"
            f"🌐 **From Live Web Search:**"
        )
        final_reply = synthesize_response(prompt, messages_history)

    # ── PATH D: MICROSOFT GRAPH (Emails / Calendar / Tasks) ───────────────────
    elif route == "graph":
        state: AgentState = {
            "session_id": session_id,
            "messages": messages_history + [HumanMessage(content=payload.message)],
            "error": None,
        }
        result_state = jarvis_agent.invoke(state)
        final_reply = result_state["messages"][-1].content

        tools_called = set()
        for msg in result_state.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if name:
                        tools_called.add(name)
        tools_used = list(tools_called)
        tools_label = "Microsoft Graph"

    # ── PATH E: DIRECT ANSWER (Casual Greeting) ───────────────────────────────
    else:
        prompt = f"The user says: '{payload.message}'. Give a brief, helpful greeting or response without self-introductions."
        final_reply = synthesize_response(prompt, messages_history)

    # Clean any unwanted intro phrases
    final_reply = clean_intro(final_reply)

    # Save assistant message to DB
    supabase_db.add_message(user_id, conversation_id, "assistant", final_reply)

    return {
        "conversation_id": conversation_id,
        "reply": final_reply,
        "tools_used": tools_used,
        "tools_label": tools_label,
        "route": route,
        "engine": "Deterministic Agentic RAG Pipeline",
    }
