from typing import Annotated, Literal
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.agent.state import AgentState
from app.agent.tools import jarvis_tools

SYSTEM_PROMPT = """You are Jarvis, an AI Academic Research Copilot integrated with Microsoft 365.
Your primary role is to assist researchers in scheduling focus blocks, drafting emails (saved to Outlook Drafts), and organizing MS To-Do tasks.
Maintain a professional, concise, academic sci-fi vibe.

CRITICAL SAFETY RULE:
- You CANNOT send emails.
- If the user asks you to send an email, explain that you can only draft it for their review.
- Always use the `create_email_draft` or `create_reply_draft` tools instead.

When you perform an action (e.g., deleting a task or creating an event), inform the user about what was done.
You will be provided with a session_id in your state. Always pass this session_id into your tools.
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

def call_model(state: AgentState):
    """Invoke the Groq LLM to reason and decide the next action."""
    messages = state.get("messages", [])
    session_id = state.get("session_id", "")
    
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        max_tokens=500
    )
    
    # Bind our tools
    llm_with_tools = llm.bind_tools(jarvis_tools)
    
    # Inject system prompt dynamically if not present
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        
    # Since tools require session_id, we need a way to pass it.
    # We can rely on LangChain's partial binding or simply inject it into the prompt.
    # However, to ensure the LLM ALWAYS passes the correct session_id to the tools without making a mistake,
    # the best way is to instruct the LLM to pass the session_id exactly as provided.
    session_instruction = SystemMessage(
        content=f"IMPORTANT: Always pass this exact session_id to your tools: '{session_id}'"
    )
    
    # Run the model
    response = llm_with_tools.invoke(messages + [session_instruction])
    return {"messages": [response]}


def build_graph():
    """Constructs the LangGraph state graph for Jarvis."""
    workflow = StateGraph(AgentState)
    
    # Define the nodes
    workflow.add_node("agent", call_model)
    
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
            "tools": "tools",
            "__end__": END
        }
    )
    
    # Once tools are done executing, loop back to the agent to interpret the result
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    return workflow.compile()

# Global compiled graph instance
jarvis_agent = build_graph()
