from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    LangGraph state for the Jarvis Agent.
    """
    # The session_id of the currently authenticated user
    session_id: str
    
    # Message history
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Optional error message if a tool fails
    error: Optional[str]
