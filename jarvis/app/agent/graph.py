"""
Jarvis LangGraph Agent — Streamlined agentic workflow with robust multi-model failover.
"""
import os
from typing import Literal
from datetime import datetime, timedelta, timezone

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.agent.state import AgentState
from app.agent.tools import jarvis_tools

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Jarvis — an Agentic AI Assistant for Microsoft 365, RAG Document Search, and Web Search.

━━ ABSOLUTE RULES (never break these) ━━━━━━━━━━━━━━━━━━━━━━
1. NEVER introduce yourself. Do NOT say "I'm Jarvis", "I am Jarvis", "Hello, I'm Jarvis" or anything similar at the start of any response. Jump straight to the answer.
2. NEVER say "I don't have information" or "I'm unable to find" WITHOUT first calling a tool.
3. ALWAYS call a tool when the question is NOT a simple greeting.
4. Greetings ONLY (hi/hello/how are you) → answer directly without a tool.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ TOOL SELECTION GUIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• [PRE-ROUTER DECISION] messages in context → follow that instruction EXACTLY.
• Document / PDF / research guide / notes / "according to my..." / prototype / assignment / workflow / RAG → call search_documents(query=...)
• Latest / current / news / online / web / 2025 / 2026 / "what happened" → call web_search(query=...)
• Email / inbox / calendar / schedule / task / to-do / Outlook → call get_emails / get_events / get_todos
• Both document AND web needed → call BOTH tools sequentially.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ RESPONSE STYLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Be concise and direct. Lead with the answer, not pleasantries.
• For RAG answers: cite the source document name.
• For web answers: mention it is from online sources.
• For multi-tool: clearly label "From your documents:" and "From the web:".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ EMAIL / TASKS SAFETY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• NEVER send emails without explicit confirmation from user.
• NEVER put time/date phrases in a task title.
• Ask clarifying questions if draft/meeting/delete details are vague.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pakistan timezone (PKT, UTC+5) is the primary timezone. Speak time naturally."""


# ──────────────────────────────────────────────────────────────────────────────
# Date/Time Context
# ──────────────────────────────────────────────────────────────────────────────

def get_datetime_context() -> str:
    now_utc = datetime.now(timezone.utc)
    pkt = timezone(timedelta(hours=5))
    now = now_utc.astimezone(pkt)
    upcoming = [
        f"  {(now + timedelta(days=i)).strftime('%A')}: {(now + timedelta(days=i)).strftime('%Y-%m-%d')}"
        for i in range(1, 8)
    ]
    return (
        f"Pakistan Time (PKT): {now.strftime('%A %Y-%m-%d %I:%M %p')}\n"
        f"Upcoming days: " + ", ".join(upcoming[:4])
    )


# ──────────────────────────────────────────────────────────────────────────────
# Active Groq Models (no decommissioned ones)
# ──────────────────────────────────────────────────────────────────────────────

_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "compound-beta",
]


# ──────────────────────────────────────────────────────────────────────────────
# Graph Nodes
# ──────────────────────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    messages = state.get("messages", [])
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


def call_model(state: AgentState):
    """Invoke LLM with full multi-key / multi-model failover."""
    messages = state.get("messages", [])
    session_id = state.get("session_id", "")

    # Keep last 12 messages (excluding system) to stay within token limits
    non_sys = [m for m in messages if not isinstance(m, SystemMessage)][-12:]

    system_msgs = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=get_datetime_context()),
        SystemMessage(content=f"session_id for all tool calls: '{session_id}'"),
    ]
    full = system_msgs + non_sys

    keys = settings.get_groq_api_keys()
    last_error = None

    for api_key in keys:
        for model in _GROQ_MODELS:
            try:
                llm = ChatGroq(
                    groq_api_key=api_key,
                    model_name=model,
                    temperature=0.2,
                    max_tokens=2048,
                    max_retries=0,
                )
                llm_with_tools = llm.bind_tools(jarvis_tools)
                response = llm_with_tools.invoke(full)
                print(f"[Agent] Model={model} tool_calls={len(response.tool_calls if hasattr(response,'tool_calls') else [])}")
                return {"messages": [response]}
            except Exception as e:
                last_error = e
                err_str = str(e)
                # Skip immediately on decommissioned or bad request — no retry value
                if "decommissioned" in err_str or "invalid_request_error" in err_str:
                    break
                print(f"[Agent] Key={api_key[:8]}... Model={model}: {err_str[:120]}")
                continue

    # OpenAI fallback
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(openai_api_key=openai_key, model_name="gpt-4o-mini", temperature=0.2)
            llm_with_tools = llm.bind_tools(jarvis_tools)
            response = llm_with_tools.invoke(full)
            return {"messages": [response]}
        except Exception as e:
            print(f"[Agent] OpenAI fallback error: {e}")
            last_error = e

    print(f"[Agent] All models exhausted. Last error: {last_error}")
    return {"messages": [AIMessage(
        content="All AI models are currently busy. Please try again in a moment."
    )]}


def inject_session_id(state: AgentState):
    """Ensure session_id is injected into every tool call argument."""
    messages = state.get("messages", [])
    session_id = state.get("session_id", "")
    if not messages:
        return {}
    last = messages[-1]
    if not (hasattr(last, "tool_calls") and last.tool_calls):
        return {}

    new_tcs = []
    for tc in last.tool_calls:
        args = dict(tc["args"])
        args["session_id"] = session_id
        new_tcs.append({"name": tc["name"], "args": args, "id": tc["id"]})

    new_msg = AIMessage(content=last.content, tool_calls=new_tcs, id=last.id)
    return {"messages": [new_msg]}


# ──────────────────────────────────────────────────────────────────────────────
# Graph Construction
# ──────────────────────────────────────────────────────────────────────────────

def build_graph():
    wf = StateGraph(AgentState)
    wf.add_node("agent", call_model)
    wf.add_node("inject_session", inject_session_id)
    wf.add_node("tools", ToolNode(jarvis_tools))
    wf.set_entry_point("agent")
    wf.add_conditional_edges("agent", should_continue, {
        "tools": "inject_session",
        "__end__": END,
    })
    wf.add_edge("inject_session", "tools")
    wf.add_edge("tools", "agent")
    return wf.compile()


jarvis_agent = build_graph()
