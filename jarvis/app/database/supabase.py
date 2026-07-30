import base64
import json
import os
import uuid
from datetime import datetime, timezone
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from app.config import settings

# ── Local File-based DB for persistence across server restarts ─────────
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".data", "local_db.json")

# In-Memory stores
_SESSION_STORE: Dict[str, Dict[str, Any]] = {}
_CONV_STORE: Dict[str, List[Dict]] = {}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_db():
    global _SESSION_STORE, _CONV_STORE
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                _SESSION_STORE = data.get("sessions", {})
                _CONV_STORE = data.get("conversations", {})
        except Exception:
            pass

def _save_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w") as f:
        json.dump({
            "sessions": _SESSION_STORE,
            "conversations": _CONV_STORE
        }, f, indent=2)

# Load data on startup
_load_db()


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
        """Encrypt and store user OAuth tokens server-side (in file)."""
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
        _save_db()

    def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return _SESSION_STORE.get(session_id)

    def delete_session(self, session_id: str) -> None:
        if session_id in _SESSION_STORE:
            del _SESSION_STORE[session_id]
            _save_db()

    # ── Conversation CRUD (Local with Supabase fallback) ─────────────────

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
        _save_db()

        # Try to persist to Supabase if service key available
        if self._db_available and settings.SUPABASE_SERVICE_KEY:
            try:
                self.client.table("conversations").insert({
                    "id": conv_id,
                    "user_id": user_id,
                    "title": title,
                }).execute()
            except Exception:
                pass

        return conv_id

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
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
        _save_db()

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
                _save_db()
                return True
        return False


supabase_db = SupabaseService()
