from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from app.database.supabase import supabase_db

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

def get_session_user_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = supabase_db.get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    return session.get("user_id")

class ConversationCreate(BaseModel):
    title: str

@router.get("")
def list_conversations(user_id: str = Depends(get_session_user_id)):
    try:
        conversations = supabase_db.get_conversations(user_id)
        return conversations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
def create_conversation(payload: ConversationCreate, user_id: str = Depends(get_session_user_id)):
    try:
        conv_id = supabase_db.create_conversation(user_id, payload.title)
        return {"id": conv_id, "title": payload.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}")
def get_conversation_details(conversation_id: str, user_id: str = Depends(get_session_user_id)):
    try:
        conv = supabase_db.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = supabase_db.get_conversation_messages(user_id, conversation_id)
        return {"conversation": conv, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, user_id: str = Depends(get_session_user_id)):
    """Return only the messages list for a conversation (used by the dashboard frontend)."""
    try:
        messages = supabase_db.get_conversation_messages(user_id, conversation_id)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: str = Depends(get_session_user_id)):
    try:
        success = supabase_db.delete_conversation(user_id, conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found or unauthorized")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
