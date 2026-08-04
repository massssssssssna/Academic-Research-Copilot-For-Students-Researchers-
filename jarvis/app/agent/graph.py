from typing import Annotated, Literal
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.agent.state import AgentState
from app.agent.tools import jarvis_tools

SYSTEM_PROMPT = """You are Jarvis, an intelligent AI Copilot and conversational assistant integrated with Microsoft 365.

CRITICAL BEHAVIOR AND TOOL USAGE RULES:

1. GENERAL ASSISTANT & CONVERSATIONAL CHAT (NO TOOLS):
   - For greetings (e.g., "hi", "hello", "hey"), casual questions (e.g., "can you fly?", "who are you?", "how are you?"), explanations, coding, brainstorming, or general conversation, RESPOND DIRECTLY as a smart, friendly AI assistant.
   - DO NOT invoke any tools for general conversation or questions.

2. EXPLICIT TASK EXECUTION ONLY:
   - ONLY use Microsoft 365 tools (emails, calendar, to-do tasks) when the user EXPLICITLY asks you to perform a specific task (e.g., "fetch my emails", "create a meeting", "add a task", "draft an email to john@example.com").
   - NEVER create email drafts, calendar events, or tasks automatically or without the user's explicit command.

3. EMAIL DRAFTING SAFETY:
   - You CANNOT send emails directly.
   - If the user explicitly asks you to draft or send an email, create an email draft using `create_email_draft` or `create_reply_draft`.
   - Never draft an email unless requested!

5. RELATIVE DATE & DAY RESOLUTION RULES (TASKS & CALENDAR):
   - Always refer to the REAL-TIME DATE & DAY CONTEXT MAP for resolving relative days ("today", "tomorrow", "yesterday", "on Friday", "this Monday", etc.).
   - When user specifies a day like "on Friday" or "tomorrow":
     * Look up the exact YYYY-MM-DD date from the UPCOMING DAYS LOOKUP MAP.
     * For To-Do tasks: set `due_date` to that YYYY-MM-DD date.
     * For Calendar events: set `start_time` and `end_time` to that YYYY-MM-DD date with ISO time.
   - When user says "add a task i want to go home on Friday at 9pm":
     * Title MUST be clean action ONLY: `title="Go home"`.
     * NEVER put day/time words like "on Friday", "at 9pm", "today" in the title!
     * `due_date` = exact Friday YYYY-MM-DD date.
     * `due_time` = "21:00".
   - When user says "today task list show me":
     * Fetch tasks and filter/highlight tasks due today (TODAY's YYYY-MM-DD date) or overdue.

Maintain a sleek, helpful, professional, and natural Jarvis persona. Be concise and smart.
"""

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Determine whether to continue to tools or end the conversation."""
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # If the LLM makes a tool call, we transition to the tools node
    if last_message.tool_calls:
        return "tools"
    
    # Otherwise, we end and return the final text
    return "__end__"

from datetime import datetime, timedelta, timezone

def get_datetime_context() -> str:
    """Generates an accurate real-time relative date & day lookup map."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    today_day = now.strftime("%A")
    
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)
    
    upcoming = []
    for i in range(1, 8):
        dt = now + timedelta(days=i)
        upcoming.append(f"  - {dt.strftime('%A')} ({dt.strftime('%b %d')}): {dt.strftime('%Y-%m-%d')}")
        
    return (
        f"REAL-TIME DATE & DAY CONTEXT MAP:\n"
        f"- TODAY is {today_day}, {today_str}\n"
        f"- YESTERDAY was {yesterday.strftime('%A')}, {yesterday.strftime('%Y-%m-%d')}\n"
        f"- TOMORROW will be {tomorrow.strftime('%A')}, {tomorrow.strftime('%Y-%m-%d')}\n"
        f"UPCOMING DAYS LOOKUP MAP (Use to convert 'on Friday', 'this Monday', etc. into exact YYYY-MM-DD dates):\n"
        + "\n".join(upcoming) + "\n"
        f"Default timezone is Asia/Karachi (PKT, UTC+5) or UTC."
    )

def call_model(state: AgentState):
    """Invoke the Groq LLM to reason and decide the next action."""
    messages = state.get("messages", [])
    session_id = state.get("session_id", "")
    
    # Separate system messages from user/assistant chat history
    non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    
    system_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=get_datetime_context()),
        SystemMessage(content=f"IMPORTANT: Always pass this exact session_id to your tools: '{session_id}'")
    ]
    
    full_messages = system_messages + non_system_messages
    
    # Models to try with automatic fallback using Tuning Knobs from config
    models_to_try = [
        settings.LLM_PRIMARY_MODEL,
        settings.LLM_FAST_MODEL,
        settings.LLM_FALLBACK_MODEL
    ]
    
    last_exception = None
    for model_name in models_to_try:
        try:
            llm = ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=model_name,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS
            )
            llm_with_tools = llm.bind_tools(jarvis_tools)
            response = llm_with_tools.invoke(full_messages)
            return {"messages": [response]}
        except Exception as e:
            last_exception = e
            err_str = str(e).lower()
            if "ratelimit" in err_str or "429" in err_str or "badrequest" in err_str or "400" in err_str or "tool_use_failed" in err_str:
                continue
            raise e
            
    if last_exception:
        raise last_exception

def inject_session_id(state: AgentState):
    """Injects the session_id into the tool calls generated by the LLM."""
    messages = state.get("messages", [])
    session_id = state.get("session_id", "")
    if not messages:
        return {}
        
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        new_tool_calls = []
        for tc in last_message.tool_calls:
            tc_args = dict(tc["args"])
            tc_args["session_id"] = session_id
            new_tool_calls.append({
                "name": tc["name"],
                "args": tc_args,
                "id": tc["id"]
            })
        
        new_message = AIMessage(
            content=last_message.content,
            tool_calls=new_tool_calls,
            id=last_message.id
        )
        return {"messages": [new_message]}
    
    return {}



def build_graph():
    """Constructs the LangGraph state graph for Jarvis."""
    workflow = StateGraph(AgentState)
    
    # Define the nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("inject_session", inject_session_id)
    
    # We use LangGraph's prebuilt ToolNode to automatically execute the selected tools
    tool_node = ToolNode(jarvis_tools)
    workflow.add_node("tools", tool_node)
    
    # Set the entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges from the agent node
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "inject_session",
            "__end__": END
        }
    )
    
    workflow.add_edge("inject_session", "tools")
    
    # Once tools are done executing, loop back to the agent to interpret the result
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    return workflow.compile()

# Global compiled graph instance
jarvis_agent = build_graph()
