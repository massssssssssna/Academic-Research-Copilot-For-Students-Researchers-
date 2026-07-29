import base64
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from app.config import settings

# In-Memory Session Store for OAuth tokens (secure server-side)
_SESSION_STORE: Dict[str, Dict[str, Any]] = {}

# In-Memory Conversation Store (avoids Supabase RLS issues with anon key)
# Structure: { user_id: [ {id, title, updated_at, messages: [...]} ] }
_CONV_STORE: Dict[str, List[Dict]] = {}

import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseService:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        # Use service role key for DB ops if available (bypasses RLS),
        # otherwise fall back to anon/publishable key
        db_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
        self.key = settings.SUPABASE_KEY
        try:
            self.client: Client = create_client(self.url, db_key)
            self._db_available = True
        except Exception:
            self._db_available = False

    # ── OAuth Token Store ────────────────────────────────────────────────────

    def save_user_tokens(self, session_id: str, tokens: dict) -> None:
        """Encrypt and store user OAuth tokens server-side (in memory)."""
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")

        _SESSION_STORE[session_id] = {
            "user_id": tokens.get("id_token") or str(uuid.uuid4()),
            "email": tokens.get("email", ""),
            "name": tokens.get("name", "User"),
            "access_token_encrypted": base64.b64encode(access_token.encode()).decode() if access_token else "",
            "refresh_token_encrypted": base64.b64encode(refresh_token.encode()).decode() if refresh_token else "",
            "provider": "microsoft_azure",
        }

    def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return _SESSION_STORE.get(session_id)

    def delete_session(self, session_id: str) -> None:
        _SESSION_STORE.pop(session_id, None)

    # ── Conversation CRUD (In-Memory with Supabase fallback) ─────────────────

    def create_conversation(self, user_id: str, title: str) -> str:
        conv_id = str(uuid.uuid4())
        conv = {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "created_at": _now(),
            "updated_at": _now(),
            "messages": [],
        }
        _CONV_STORE.setdefault(user_id, []).insert(0, conv)

        # Try to persist to Supabase if service key available
        if self._db_available and settings.SUPABASE_SERVICE_KEY:
            try:
                self.client.table("conversations").insert({
                    "id": conv_id,
                    "user_id": user_id,
                    "title": title,
                }).execute()
            except Exception:
                pass  # fall back to memory

        return conv_id

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        # Return from memory first (always up-to-date)
        convs = _CONV_STORE.get(user_id, [])
        if convs:
            return [{"id": c["id"], "title": c["title"], "updated_at": c["updated_at"]} for c in convs]

        # Fallback: try Supabase
        if self._db_available:
            try:
                resp = self.client.table("conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
                return resp.data or []
            except Exception:
                pass
        return []

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        for conv in _CONV_STORE.get(user_id, []):
            if conv["id"] == conversation_id:
                return conv
        return None

    def get_conversation_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        conv = self.get_conversation(user_id, conversation_id)
        if conv:
            return conv.get("messages", [])
        return []

    def add_message(self, user_id: str, conversation_id: str, role: str, content: str) -> Dict[str, Any]:
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            raise ValueError("Conversation not found or unauthorized")

        msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": _now(),
        }
        conv["messages"].append(msg)
        conv["updated_at"] = _now()

        # Try Supabase if service key available
        if self._db_available and settings.SUPABASE_SERVICE_KEY:
            try:
                self.client.table("messages").insert({
                    "conversation_id": conversation_id,
                    "role": role,
                    "content": content,
                }).execute()
            except Exception:
                pass

        return msg

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        convs = _CONV_STORE.get(user_id, [])
        for i, conv in enumerate(convs):
            if conv["id"] == conversation_id:
                convs.pop(i)
                return True
        return False


supabase_db = SupabaseService()
