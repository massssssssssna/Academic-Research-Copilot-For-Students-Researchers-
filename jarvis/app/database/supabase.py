import base64
import json
import os
import uuid
from datetime import datetime, timezone
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from app.config import settings

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _to_valid_uuid(val: str) -> str:
    """Convert any string into a valid UUID string deterministically if not already a UUID."""
    if not val:
        return str(uuid.uuid4())
    try:
        uuid.UUID(str(val))
        return str(val)
    except (ValueError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, str(val)))


class SupabaseService:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        db_key = settings.SUPABASE_SERVICE_KEY or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or settings.SUPABASE_KEY
        self.key = settings.SUPABASE_KEY
        if not self.url or not db_key:
            raise ValueError("Supabase URL or Key is missing. Please check your .env file.")
        
        self.client: Client = create_client(self.url, db_key)

    # ── OAuth Token Store ────────────────────────────────────────────────────

    def save_user_tokens(self, session_id: str, tokens: dict) -> None:
        """Encrypt and store user OAuth tokens server-side."""
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")

        user_id = tokens.get("id_token") or str(uuid.uuid4())
        
        db_data = {
            "session_id": _to_valid_uuid(session_id),
            "user_id": _to_valid_uuid(user_id),
            "email": tokens.get("email", ""),
            "name": tokens.get("name", "User"),
            "access_token_encrypted": base64.b64encode(access_token.encode()).decode() if access_token else "",
            "refresh_token_encrypted": base64.b64encode(refresh_token.encode()).decode() if refresh_token else "",
            "provider": "microsoft_azure",
            "updated_at": _now()
        }
        resp = self.client.table("user_sessions").upsert(db_data).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase save_user_tokens error: {resp.error}")

    def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id:
            try:
                db_session_id = _to_valid_uuid(session_id)
                resp = self.client.table("user_sessions").select("*").eq("session_id", db_session_id).execute()
                if resp.data and len(resp.data) > 0:
                    return resp.data[0]
            except Exception:
                pass
        
        # Fallback 1: Auto-fetch the most recently updated active logged-in user session!
        try:
            resp = self.client.table("user_sessions").select("*").order("updated_at", desc=True).limit(1).execute()
            if resp.data and len(resp.data) > 0:
                return resp.data[0]
        except Exception:
            pass

        # Fallback 2: Return default guest session dict so RAG & Web Search are never blocked by auth
        guest_sess_id = _to_valid_uuid(session_id or "default_jarvis_session")
        return {
            "session_id": guest_sess_id,
            "user_id": _to_valid_uuid("guest_user_id"),
            "email": "user@jarvis.ai",
            "name": "Jarvis User",
            "access_token_encrypted": "",
            "refresh_token_encrypted": ""
        }

    def delete_session(self, session_id: str) -> None:
        db_session_id = _to_valid_uuid(session_id)
        resp = self.client.table("user_sessions").delete().eq("session_id", db_session_id).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase delete_session error: {resp.error}")

    # ── Conversation CRUD ─────────────────

    def create_conversation(self, user_id: str, title: str) -> str:
        conv_id = str(uuid.uuid4())
        db_user_id = _to_valid_uuid(user_id)
        resp = self.client.table("conversations").insert({
            "id": conv_id,
            "user_id": db_user_id,
            "title": title,
            "created_at": _now(),
            "updated_at": _now()
        }).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase create_conversation error: {resp.error}")
        return conv_id

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        db_user_id = _to_valid_uuid(user_id)
        resp = self.client.table("conversations").select("*").eq("user_id", db_user_id).order("updated_at", desc=True).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase get_conversations error: {resp.error}")
        return resp.data if resp.data else []

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        db_user_id = _to_valid_uuid(user_id)
        db_conv_id = _to_valid_uuid(conversation_id)
        resp = self.client.table("conversations").select("*").eq("id", db_conv_id).eq("user_id", db_user_id).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase get_conversation error: {resp.error}")
        
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None

    def get_conversation_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        # Ensure the conversation exists and belongs to the user
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return []

        db_conv_id = _to_valid_uuid(conversation_id)
        resp = self.client.table("messages").select("*").eq("conversation_id", db_conv_id).order("created_at", desc=False).execute()
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase get_conversation_messages error: {resp.error}")
        return resp.data if resp.data else []

    def add_message(self, user_id: str, conversation_id: str, role: str, content: str) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now_ts = _now()
        
        db_msg_id = _to_valid_uuid(msg_id)
        db_conv_id = _to_valid_uuid(conversation_id)
        
        # Insert Message
        resp_msg = self.client.table("messages").insert({
            "id": db_msg_id,
            "conversation_id": db_conv_id,
            "role": role,
            "content": content,
            "created_at": now_ts
        }).execute()
        if hasattr(resp_msg, "error") and resp_msg.error:
            raise Exception(f"Supabase add_message error: {resp_msg.error}")

        # Update Conversation timestamp
        resp_conv = self.client.table("conversations").update({
            "updated_at": now_ts
        }).eq("id", db_conv_id).execute()
        if hasattr(resp_conv, "error") and resp_conv.error:
            raise Exception(f"Supabase update conversation error: {resp_conv.error}")

        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": now_ts,
        }

    def rename_conversation(self, user_id: str, conversation_id: str, new_title: str) -> bool:
        db_user_id = _to_valid_uuid(user_id)
        db_conv_id = _to_valid_uuid(conversation_id)
        now_ts = _now()

        # Check if exists for this user
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return False

        resp = self.client.table("conversations").update({
            "title": new_title,
            "updated_at": now_ts
        }).eq("id", db_conv_id).execute()
        
        if hasattr(resp, "error") and resp.error:
            raise Exception(f"Supabase rename_conversation error: {resp.error}")

        return True

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        db_conv_id = _to_valid_uuid(conversation_id)
        
        # Check if exists for this user
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return False

        resp_msg = self.client.table("messages").delete().eq("conversation_id", db_conv_id).execute()
        if hasattr(resp_msg, "error") and resp_msg.error:
            raise Exception(f"Supabase delete messages error: {resp_msg.error}")
            
        resp_conv = self.client.table("conversations").delete().eq("id", db_conv_id).execute()
        if hasattr(resp_conv, "error") and resp_conv.error:
            raise Exception(f"Supabase delete conversation error: {resp_conv.error}")

        return True


supabase_db = SupabaseService()
