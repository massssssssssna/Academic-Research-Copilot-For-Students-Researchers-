from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.graph import jarvis_agent
from app.agent.state import AgentState
from app.database.supabase import supabase_db

router = APIRouter(prefix="/api", tags=["Chat"])

class ChatPayload(BaseModel):
    message: str
    conversation_id: Optional[str] = None

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

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
        # Create a new conversation
        # Title can be derived from the first message
        title = payload.message[:50] + "..." if len(payload.message) > 50 else payload.message
        conversation_id = supabase_db.create_conversation(user_id, title)
    else:
        # Verify conversation belongs to user and load history
        conv = supabase_db.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found or unauthorized")
        
        raw_messages = supabase_db.get_conversation_messages(user_id, conversation_id)
        for msg in raw_messages:
            if msg["role"] == "user":
                messages_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages_history.append(AIMessage(content=msg["content"]))

    # Add the new user message to DB and state
    supabase_db.add_message(user_id, conversation_id, "user", payload.message)
    messages_history.append(HumanMessage(content=payload.message))

    state: AgentState = {
        "session_id": session_id,
        "messages": messages_history,
        "error": None
    }
    
    try:
        # LangGraph invoke returns the final state
        result_state = jarvis_agent.invoke(state)
        # The last message is the AI's response
        final_message = result_state["messages"][-1].content
        
        # Save assistant message to DB
        supabase_db.add_message(user_id, conversation_id, "assistant", final_message)
        
        return {
            "conversation_id": conversation_id,
            "reply": final_message, 
            "engine": "LangGraph (Groq)"
        }
    except Exception as e:
        # Avoid exposing raw stack traces directly, but return a helpful error
        raise HTTPException(status_code=500, detail=str(e))
