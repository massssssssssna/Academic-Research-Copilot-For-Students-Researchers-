import os
import base64
import json
import urllib.parse
import urllib.request
from typing import Dict, Any

from app.config import settings

class MicrosoftOAuthService:
    """
    Handles OAuth directly with Microsoft Azure AD (bypassing Supabase OAuth).
    Flow:
      1. /auth/login     -> generates state, redirects user to Microsoft authorize URL
      2. Microsoft       -> user logs in, redirects to /auth/callback?code=<auth_code>&state=<state>
      3. /auth/callback  -> exchanges code for session tokens directly from Microsoft
    """

    def get_authorization_url(self, state: str) -> str:
        """
        Build the Microsoft OAuth URL.
        """
        tenant_id = settings.MICROSOFT_TENANT_ID or "common"
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": "User.Read Mail.ReadWrite Calendars.ReadWrite Tasks.ReadWrite offline_access",
            "state": state,
        }
        return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)

    def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange Microsoft auth code for session tokens.
        Returns dict with access_token, refresh_token, email, name.
        """
        tenant_id = settings.MICROSOFT_TENANT_ID or "common"
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        
        payload = urllib.parse.urlencode({
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "scope": "User.Read Mail.ReadWrite Calendars.ReadWrite Tasks.ReadWrite offline_access",
            "code": code,
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "grant_type": "authorization_code",
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        }).encode("utf-8")

        req = urllib.request.Request(
            token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise ValueError(f"Token exchange failed ({e.code}): {body}")
            
        ms_access_token = data.get("access_token", "")
        ms_refresh_token = data.get("refresh_token", "")
        
        # We also need to get the user's email/name to save in session.
        # We can call Graph API /me with the new access_token
        req_me = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {ms_access_token}"},
        )
        try:
            with urllib.request.urlopen(req_me, timeout=10) as resp_me:
                me_data = json.loads(resp_me.read().decode())
        except Exception:
            me_data = {}
            
        return {
            "access_token": ms_access_token,
            "refresh_token": ms_refresh_token,
            "id_token": me_data.get("id", ""),
            "email": me_data.get("mail") or me_data.get("userPrincipalName", ""),
            "name": me_data.get("displayName", "User"),
        }


ms_oauth = MicrosoftOAuthService()
