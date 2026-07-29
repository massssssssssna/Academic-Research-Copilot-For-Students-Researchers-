import os
import base64
import hashlib
import json
import urllib.parse
import urllib.request
from typing import Dict, Any

from app.config import settings

# In-memory store: state_id -> code_verifier
# In production, use Redis or Supabase for this
_PKCE_STORE: Dict[str, str] = {}


class MicrosoftOAuthService:
    """
    Handles OAuth via Supabase Azure provider using PKCE (server-side).
    Flow:
      1. /auth/login     -> generates PKCE pair, redirects user to Supabase authorize URL
      2. Supabase+Azure  -> user logs in, Supabase redirects to /auth/callback?code=<pkce_code>
      3. /auth/callback  -> exchanges code+verifier for Supabase session (includes provider_token = MS Graph token)
    """

    SUPABASE_URL: str = settings.SUPABASE_URL
    SUPABASE_KEY: str = settings.SUPABASE_KEY

    def get_authorization_url(self, state: str) -> str:
        """
        Build the Supabase Azure OAuth URL with PKCE.
        The redirect_to param tells Supabase where to send the user after Microsoft login.
        """
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        _PKCE_STORE[state] = code_verifier

        params = {
            "provider": "azure",
            "redirect_to": settings.MICROSOFT_REDIRECT_URI,  # http://localhost:8000/auth/callback
            "code_challenge": code_challenge,
            "code_challenge_method": "s256",
            "scopes": "User.Read Mail.ReadWrite Calendars.ReadWrite Tasks.ReadWrite offline_access",
        }
        return f"{self.SUPABASE_URL}/auth/v1/authorize?" + urllib.parse.urlencode(params)

    def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange Supabase PKCE auth code for session tokens.
        Returns dict with access_token (MS Graph), refresh_token, email, name.
        """
        code_verifier = _PKCE_STORE.pop(state, None)
        if not code_verifier:
            raise ValueError("PKCE session expired or invalid state. Please try logging in again.")

        token_url = f"{self.SUPABASE_URL}/auth/v1/token?grant_type=pkce"
        payload = json.dumps({
            "auth_code": code,
            "code_verifier": code_verifier,
        }).encode("utf-8")

        req = urllib.request.Request(
            token_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": self.SUPABASE_KEY,
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise ValueError(f"Token exchange failed ({e.code}): {body}")

        user = data.get("user") or {}
        user_meta = user.get("user_metadata") or {}

        # provider_token = Microsoft Graph access token
        ms_access_token = data.get("provider_token", "")
        ms_refresh_token = data.get("provider_refresh_token", "")

        return {
            "access_token": ms_access_token,
            "refresh_token": ms_refresh_token,
            "id_token": user.get("id", ""),
            "email": user.get("email", "") or user_meta.get("email", ""),
            "name": (
                user_meta.get("full_name")
                or user_meta.get("name")
                or user_meta.get("preferred_username")
                or user.get("email", "User")
            ),
        }


ms_oauth = MicrosoftOAuthService()
