import base64
import json
import httpx
from typing import Dict, Any, Optional, List
from app.config import settings
from app.database.supabase import supabase_db

class MicrosoftGraphError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        
    def __str__(self):
        return f"MicrosoftGraphError: {self.message} (Status: {self.status_code})"

class MicrosoftGraphClient:
    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, session_id: str):
        self.session_id = session_id
        
    def _get_access_token(self) -> str:
        """Retrieves and decrypts the access token from the session store."""
        session = supabase_db.get_user_session(self.session_id)
        if not session or not session.get("access_token_encrypted"):
            raise MicrosoftGraphError("No active session or access token missing", 401)
        
        try:
            token = base64.b64decode(session["access_token_encrypted"]).decode()
            return token
        except Exception:
            raise MicrosoftGraphError("Invalid encrypted access token format", 401)

    def _refresh_tokens(self) -> str:
        """Attempt to refresh tokens using Supabase Auth mechanism."""
        session = supabase_db.get_user_session(self.session_id)
        if not session or not session.get("refresh_token_encrypted"):
            raise MicrosoftGraphError("No refresh token available", 401)
            
        try:
            refresh_token = base64.b64decode(session["refresh_token_encrypted"]).decode()
        except Exception:
            raise MicrosoftGraphError("Invalid encrypted refresh token format", 401)
            
        refresh_url = f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=refresh_token"
        headers = {
            "Content-Type": "application/json",
            "apikey": settings.SUPABASE_KEY
        }
        payload = {"refresh_token": refresh_token}
        
        with httpx.Client() as client:
            resp = client.post(refresh_url, json=payload, headers=headers)
            if resp.status_code != 200:
                # If refresh fails, clear session as they need to re-login
                supabase_db.delete_session(self.session_id)
                raise MicrosoftGraphError("Session expired, please log in again.", 401)
                
            data = resp.json()
            
            # Formatted similarly to what the callback endpoint creates
            new_tokens = {
                "access_token": data.get("provider_token") or data.get("access_token", ""),
                "refresh_token": data.get("provider_refresh_token") or data.get("refresh_token", ""),
                "id_token": data.get("user", {}).get("id", session.get("user_id")),
                "email": data.get("user", {}).get("email", session.get("email")),
                "name": data.get("user", {}).get("user_metadata", {}).get("full_name", session.get("name"))
            }
            supabase_db.save_user_tokens(self.session_id, new_tokens)
            return new_tokens["access_token"]
        
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """General request executor that handles authentication and retries."""
        token = self._get_access_token()
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        
        with httpx.Client() as client:
            resp = client.request(method, url, headers=headers, **kwargs)
            
            # Handle token expiration
            if resp.status_code == 401:
                token = self._refresh_tokens()
                headers["Authorization"] = f"Bearer {token}"
                resp = client.request(method, url, headers=headers, **kwargs)
                
            if resp.status_code >= 400:
                self._handle_error(resp)
                
            # DELETE typically returns 204 No Content
            if resp.status_code == 204:
                return True
                
            return resp.json()

    def _handle_error(self, resp: httpx.Response):
        """Sanitized error handling without exposing raw tokens/headers."""
        status = resp.status_code
        message = "Microsoft Graph API Error"
        if status == 401:
            message = "Authentication failed (Unauthorized)"
        elif status == 403:
            message = "Permission denied (Forbidden)"
        elif status == 404:
            message = "Resource not found (Not Found)"
        elif status == 429:
            message = "Too many requests (Rate Limit)"
        elif status >= 500:
            message = "Microsoft Graph server error"
        
        raise MicrosoftGraphError(message, status)

    # ---------------------------------------------------------
    # API Methods
    # ---------------------------------------------------------
    
    def get_current_user(self):
        return self._request("GET", "/me")
        
    def get_messages(self, top: int = 10, skip: int = 0, search: Optional[str] = None):
        params = {"$top": top, "$skip": skip}
        if search:
            params["$search"] = f'"{search}"'
        return self._request("GET", "/me/messages", params=params)
        
    def get_message(self, message_id: str):
        return self._request("GET", f"/me/messages/{message_id}")
        
    def create_draft(self, subject: str, content: str, to_recipients: List[str]):
        """Creates an email draft. NO SENDING ALLOWED."""
        payload = {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": content
            },
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to_recipients]
        }
        return self._request("POST", "/me/messages", json=payload)
        
    def create_reply_draft(self, message_id: str, content: str):
        """Creates a reply draft for an existing message. NO SENDING ALLOWED."""
        payload = {
            "comment": content
        }
        return self._request("POST", f"/me/messages/{message_id}/createReply", json=payload)
        
    def get_events(
        self, 
        top: int = 10, 
        skip: int = 0, 
        start_datetime: Optional[str] = None, 
        end_datetime: Optional[str] = None
    ):
        params = {"$top": top, "$skip": skip}
        if start_datetime and end_datetime:
            params["startDateTime"] = start_datetime
            params["endDateTime"] = end_datetime
            return self._request("GET", "/me/calendarView", params=params)
        return self._request("GET", "/me/events", params=params)

    def get_event(self, event_id: str):
        return self._request("GET", f"/me/events/{event_id}")
        
    def create_event(
        self, 
        subject: str, 
        start_time: str, 
        end_time: str, 
        time_zone: str = "UTC",
        body: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        is_online_meeting: bool = False
    ):
        payload = {
            "subject": subject,
            "start": {"dateTime": start_time, "timeZone": time_zone},
            "end": {"dateTime": end_time, "timeZone": time_zone}
        }
        if body:
            payload["body"] = {"contentType": "Text", "content": body}
        if location:
            payload["location"] = {"displayName": location}
        if attendees:
            payload["attendees"] = [{"emailAddress": {"address": a}, "type": "required"} for a in attendees]
        if is_online_meeting:
            payload["isOnlineMeeting"] = True
            payload["onlineMeetingProvider"] = "teamsForBusiness"
            
        return self._request("POST", "/me/events", json=payload)
        
    def update_event(self, event_id: str, payload: dict):
        return self._request("PATCH", f"/me/events/{event_id}", json=payload)
        
    def delete_event(self, event_id: str):
        return self._request("DELETE", f"/me/events/{event_id}")
        
    def get_todo_lists(self):
        return self._request("GET", "/me/todo/lists")
        
    def get_todos(self, list_id: str):
        return self._request("GET", f"/me/todo/lists/{list_id}/tasks")
        
    def get_todo(self, list_id: str, task_id: str):
        return self._request("GET", f"/me/todo/lists/{list_id}/tasks/{task_id}")
        
    def create_todo(
        self, 
        list_id: str, 
        title: str, 
        body: str = "", 
        due_date: str = "", 
        due_time: str = "", 
        importance: str = ""
    ):
        payload = {"title": title}
        if body:
            payload["body"] = {"contentType": "text", "content": body}
        if due_date and due_time:
            # Microsoft Graph expects a DateTimeTimeZone object for dueDateTime
            payload["dueDateTime"] = {
                "dateTime": f"{due_date}T{due_time}",
                "timeZone": "UTC"
            }
        if importance:
            payload["importance"] = importance
            
        return self._request("POST", f"/me/todo/lists/{list_id}/tasks", json=payload)
        
    def update_todo(self, list_id: str, task_id: str, payload: dict):
        return self._request("PATCH", f"/me/todo/lists/{list_id}/tasks/{task_id}", json=payload)
        
    def delete_todo(self, list_id: str, task_id: str):
        return self._request("DELETE", f"/me/todo/lists/{list_id}/tasks/{task_id}")
