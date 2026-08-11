from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from app.graph.client import MicrosoftGraphClient, MicrosoftGraphError
from app.rag.corrective_rag import CorrectiveRAGService
from app.tools.web_search import execute_web_search

# ---------------------------------------------------------
# Tool Input Schemas
# ---------------------------------------------------------

class SessionAuthSchema(BaseModel):
    session_id: Optional[str] = Field(None, description="System injected. Do not provide.")

# EMAIL SCHEMAS
class GetEmailsSchema(SessionAuthSchema):
    top: int = Field(10, description="Number of emails to fetch")
    search: Optional[str] = Field(None, description="Optional search query")
    folder: Optional[str] = Field("inbox", description="Mail folder to query: 'inbox', 'drafts', 'sentitems', 'deleteditems', or 'all'")

class GetEmailSchema(SessionAuthSchema):
    message_id: str = Field(..., description="The ID of the email message to fetch")

class DeleteEmailSchema(SessionAuthSchema):
    message_id: str = Field(..., description="The ID of the email message to delete")

class CreateEmailDraftSchema(SessionAuthSchema):
    subject: str = Field(..., description="Subject of the email")
    content: str = Field(..., description="Content/body of the email")
    to_recipients: List[str] = Field(..., description="List of recipient email addresses")

class CreateReplyDraftSchema(SessionAuthSchema):
    message_id: str = Field(..., description="The exact string ID of the existing email message to reply to. NEVER use this tool if you do not have a valid message_id string.")
    content: str = Field(..., description="Content/body of the reply")

class DeleteAllDraftsSchema(SessionAuthSchema):
    pass

class SummarizeAndDraftReplySchema(SessionAuthSchema):
    message_id: str = Field(..., description="The ID of the inbox email to summarize and create a draft reply for.")
    custom_notes: Optional[str] = Field("", description="Optional custom notes or instructions for the draft reply.")

# CALENDAR SCHEMAS
class GetEventsSchema(SessionAuthSchema):
    top: int = Field(10, description="Number of events to fetch")
    start_datetime: Optional[str] = Field(None, description="Start date/time (ISO 8601)")
    end_datetime: Optional[str] = Field(None, description="End date/time (ISO 8601)")

class GetEventSchema(SessionAuthSchema):
    event_id: str = Field(..., description="The ID of the calendar event to fetch")

class CreateEventSchema(SessionAuthSchema):
    subject: str = Field(..., description="Event subject")
    start_time: str = Field(..., description="Start date/time (ISO 8601)")
    end_time: str = Field(..., description="End date/time (ISO 8601)")
    time_zone: str = Field("UTC", description="Time zone")
    body: Optional[str] = Field("", description="Event description")
    location: Optional[str] = Field("", description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee emails")
    is_online_meeting: bool = Field(False, description="Whether this is a Teams/online meeting")

class UpdateEventSchema(SessionAuthSchema):
    event_id: str = Field(..., description="The ID of the event to update")
    subject: Optional[str] = Field(None, description="New event subject")
    start_time: Optional[str] = Field(None, description="New start date/time (ISO 8601)")
    end_time: Optional[str] = Field(None, description="New end date/time (ISO 8601)")
    time_zone: Optional[str] = Field(None, description="New time zone")
    body: Optional[str] = Field(None, description="New event description")
    location: Optional[str] = Field(None, description="New event location")

class DeleteEventSchema(SessionAuthSchema):
    event_id: str = Field(..., description="The ID of the calendar event to delete")

# TO-DO SCHEMAS
class GetTodosSchema(SessionAuthSchema):
    list_id: Optional[str] = Field(None, description="The ID of the To-Do list. Leave empty for the default list.")

class GetTodoSchema(SessionAuthSchema):
    list_id: Optional[str] = Field(None, description="The ID of the To-Do list. Leave empty for the default list.")
    task_id: str = Field(..., description="The ID of the task")

class CreateTodoSchema(SessionAuthSchema):
    list_id: Optional[str] = Field(None, description="The ID of the To-Do list. Leave empty for the default list.")
    title: str = Field(..., description="Clean action title ONLY (e.g. 'Go home', 'Go out', 'Prepare research slides'). MUST NOT include time/date words like 'at 9pm', 'at 7pm', 'today', 'tomorrow' in the title!")
    body: Optional[str] = Field("", description="Task description")
    due_date: Optional[str] = Field("", description="Due date in YYYY-MM-DD format. Infer from user prompt e.g. use today's date if user specifies time like 'at 9pm' or says 'today'.")
    due_time: Optional[str] = Field("", description="Due time in HH:MM format (24-hour format e.g. '21:00' for 9pm, '19:00' for 7pm, '22:00' for 10pm).")
    importance: Optional[str] = Field("", description="Importance (low, normal, high)")

class UpdateTodoSchema(SessionAuthSchema):
    list_id: Optional[str] = Field(None, description="The ID of the To-Do list. Leave empty for the default list.")
    task_id: str = Field(..., description="The ID of the task to update")
    title: Optional[str] = Field(None, description="New title")
    body: Optional[str] = Field(None, description="New body")
    importance: Optional[str] = Field(None, description="New importance")
    status: Optional[str] = Field(None, description="New status (notStarted, inProgress, completed, waitingOnOthers, deferred)")

class DeleteTodoSchema(SessionAuthSchema):
    list_id: Optional[str] = Field(None, description="The ID of the To-Do list. Leave empty for the default list.")
    task_id: str = Field(..., description="The ID of the task to delete")


# ---------------------------------------------------------
# Helper for Error Formatting
# ---------------------------------------------------------

def _format_error(e: Exception) -> str:
    if isinstance(e, MicrosoftGraphError):
        if e.status_code == 401:
            return "Your Microsoft session has expired. Please sign in again."
        elif e.status_code == 403:
            return "I don't currently have permission to access that Microsoft resource."
        elif e.status_code == 404:
            return "I couldn't find that resource."
        elif e.status_code == 429:
            return "Microsoft Graph is temporarily rate-limiting requests. Please try again shortly."
        else:
            return f"Microsoft Graph API Error: {e.message}"
    return f"Unexpected error: {str(e)}"

def _resolve_list_id(client: MicrosoftGraphClient, list_id: Optional[str]) -> str:
    if not list_id or list_id.lower() == "default":
        lists_res = client.get_todo_lists()
        if lists_res and "value" in lists_res and len(lists_res["value"]) > 0:
            default_list = next((lst for lst in lists_res["value"] if lst.get("wellKnownListName") == "defaultList"), lists_res["value"][0])
            return default_list["id"]
        raise Exception("Failed to find any To-Do lists.")
    return list_id

# ---------------------------------------------------------
# EMAIL TOOLS
# ---------------------------------------------------------

@tool(args_schema=GetEmailsSchema)
def get_emails(session_id: str, top: int = 10, search: Optional[str] = None, folder: Optional[str] = "inbox") -> str:
    """Fetch Outlook emails from the user's Microsoft 365 inbox, drafts, or sent items. DO NOT use this tool for local PDF files, uploaded documents, or RAG questions."""
    try:
        client = MicrosoftGraphClient(session_id)
        raw_res = client.get_messages(top=top, search=search, folder=folder or "inbox")
        if isinstance(raw_res, dict) and "value" in raw_res:
            messages = raw_res["value"]
            target_folder = folder or "inbox"
            if not messages:
                return f"No emails found in folder '{target_folder}'."
            formatted = []
            for m in messages:
                m_id = m.get("id", "")
                m_sub = m.get("subject", "(No Subject)")
                sender_obj = m.get("from", {}).get("emailAddress", {})
                m_from = sender_obj.get("name") or sender_obj.get("address") or "Unknown"
                m_date = (m.get("receivedDateTime") or m.get("createdDateTime") or "")[:16].replace("T", " ")
                m_draft = " [DRAFT]" if m.get("isDraft") else ""
                m_prev = (m.get("bodyPreview") or "")[:120].strip()
                formatted.append(f"- ID: {m_id}\n  From: {m_from} | Date: {m_date}{m_draft}\n  Subject: {m_sub}\n  Preview: {m_prev}")
            return f"Found {len(messages)} email(s) in folder '{target_folder}':\n\n" + "\n\n".join(formatted)
        return str(raw_res)
    except Exception as e:
        return _format_error(e)

@tool(args_schema=GetEmailSchema)
def get_email(session_id: str, message_id: str) -> str:
    """Fetch a specific email by its ID."""
    try:
        client = MicrosoftGraphClient(session_id)
        return str(client.get_message(message_id))
    except Exception as e:
        return _format_error(e)

@tool(args_schema=DeleteEmailSchema)
def delete_email(session_id: str, message_id: str) -> str:
    """Delete an email message by its ID."""
    try:
        client = MicrosoftGraphClient(session_id)
        client.delete_message(message_id)
        return "Successfully deleted email message."
    except Exception as e:
        return _format_error(e)

@tool(args_schema=CreateEmailDraftSchema)
def create_email_draft(session_id: str, subject: str, content: str, to_recipients: List[str]) -> str:
    """Create a new email draft in Outlook. ONLY invoke this tool when the user EXPLICITLY asks to draft, write, or compose an email."""
    try:
        client = MicrosoftGraphClient(session_id)
        result = client.create_draft(subject, content, to_recipients)
        return f"Successfully created email draft. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=CreateReplyDraftSchema)
def create_reply_draft(session_id: str, message_id: str, content: str) -> str:
    """Create a draft reply to an EXISTING email. ONLY invoke if you have a specific, valid message_id string from an existing email."""
    try:
        client = MicrosoftGraphClient(session_id)
        result = client.create_reply_draft(message_id, content)
        return f"Successfully created reply draft. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=DeleteAllDraftsSchema)
def delete_all_drafts(session_id: str) -> str:
    """Delete ALL draft emails in the user's Outlook Drafts folder."""
    try:
        client = MicrosoftGraphClient(session_id)
        raw_res = client.get_messages(top=50, folder="drafts")
        if isinstance(raw_res, dict) and "value" in raw_res:
            drafts = raw_res["value"]
            if not drafts:
                return "No draft emails found to delete."
            count = 0
            for d in drafts:
                m_id = d.get("id")
                if m_id:
                    try:
                        client.delete_message(m_id)
                        count += 1
                    except Exception:
                        pass
            return f"Successfully deleted {count} draft email(s)."
        return "No draft emails found to delete."
    except Exception as e:
        return _format_error(e)

@tool(args_schema=SummarizeAndDraftReplySchema)
def summarize_and_draft_reply(session_id: str, message_id: str, custom_notes: Optional[str] = "") -> str:
    """Summarize an incoming inbox email and automatically create a draft reply."""
    try:
        client = MicrosoftGraphClient(session_id)
        msg = client.get_message(message_id)
        sub = msg.get("subject", "")
        sender = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        body = msg.get("bodyPreview") or msg.get("body", {}).get("content", "")
        
        reply_body = f"Summary of received email:\n\"{body[:200]}\"\n\nDraft Reply:\nThank you for your email regarding '{sub}'. {custom_notes or 'I have reviewed your message and will follow up shortly.'}"
        
        result = client.create_reply_draft(message_id, reply_body)
        return f"Successfully summarized email and created reply draft for '{sender}'. Draft ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

# ---------------------------------------------------------
# CALENDAR TOOLS
# ---------------------------------------------------------

@tool(args_schema=GetEventsSchema)
def get_events(session_id: str, top: int = 15, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None) -> str:
    """Fetch the user's UPCOMING calendar events starting from today (PKT). Past events from previous years are excluded automatically."""
    try:
        client = MicrosoftGraphClient(session_id)
        # Use PKT (UTC+5) for correct "today" reference
        pkt = timezone(timedelta(hours=5))
        now_pkt = datetime.now(pkt)
        today_str = now_pkt.strftime("%Y-%m-%d")
        current_year = now_pkt.year  # e.g., 2026

        raw_res = client.get_events(top=top, start_datetime=start_datetime, end_datetime=end_datetime)
        if isinstance(raw_res, dict) and "value" in raw_res:
            events = raw_res["value"]
            if not events:
                return (
                    f"No upcoming calendar events found between today ({today_str}) and the next 30 days.\n"
                    f"(Current date: {now_pkt.strftime('%A, %B %d, %Y')} PKT)"
                )

            today_events = []
            upcoming_events = []

            for ev in events:
                ev_id = ev.get("id", "")
                subject = ev.get("subject", "Untitled Event")
                start_obj = ev.get("start", {})
                end_obj = ev.get("end", {})

                s_raw = start_obj.get("dateTime", "")
                e_raw = end_obj.get("dateTime", "")

                s_dt = s_raw[:16].replace("T", " ") if s_raw else "Unknown start"
                e_dt = e_raw[:16].replace("T", " ") if e_raw else "Unknown end"
                tz = start_obj.get("timeZone", "UTC")
                loc = ev.get("location", {}).get("displayName", "")
                loc_str = f" | Location: {loc}" if loc else ""

                item_text = f"- ID: {ev_id}\n  Subject: '{subject}'\n  Time: {s_dt} to {e_dt} ({tz}){loc_str}"

                if s_raw:
                    s_date = s_raw.split("T")[0] if "T" in s_raw else s_raw[:10]
                    if s_date == today_str:
                        today_events.append(item_text)
                    elif s_date > today_str:
                        upcoming_events.append(item_text)
                    # Past events (< today_str) are skipped — they should not appear
                    # since calendarView already filters them at API level
                else:
                    upcoming_events.append(item_text)

            res_lines = [
                f"Calendar Events (Today: {now_pkt.strftime('%A, %B %d, %Y')} | {current_year}):"
            ]
            if today_events:
                res_lines.append("\n📅 TODAY'S EVENTS:\n" + "\n".join(today_events))
            if upcoming_events:
                res_lines.append("\n🔮 UPCOMING EVENTS (next 30 days):\n" + "\n".join(upcoming_events))
            if not today_events and not upcoming_events:
                res_lines.append(f"\nNo events scheduled for today or the next 30 days.")

            return "\n".join(res_lines)

        return str(raw_res)
    except Exception as e:
        return _format_error(e)

@tool(args_schema=GetEventSchema)
def get_event(session_id: str, event_id: str) -> str:
    """Fetch a specific calendar event by its ID."""
    try:
        client = MicrosoftGraphClient(session_id)
        return str(client.get_event(event_id))
    except Exception as e:
        return _format_error(e)

@tool(args_schema=CreateEventSchema)
def create_event(
    session_id: str, 
    subject: str, 
    start_time: str, 
    end_time: str, 
    time_zone: str = "Pakistan Standard Time",
    body: Optional[str] = "",
    location: Optional[str] = "",
    attendees: Optional[List[str]] = None,
    is_online_meeting: bool = False
) -> str:
    """Create a new calendar event."""
    try:
        client = MicrosoftGraphClient(session_id)
        result = client.create_event(
            subject=subject,
            start_time=start_time,
            end_time=end_time,
            time_zone=time_zone,
            body=body,
            location=location,
            attendees=attendees,
            is_online_meeting=is_online_meeting
        )
        return f"Successfully created event. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=UpdateEventSchema)
def update_event(
    session_id: str,
    event_id: str,
    subject: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_zone: Optional[str] = None,
    body: Optional[str] = None,
    location: Optional[str] = None
) -> str:
    """Update an existing calendar event."""
    try:
        client = MicrosoftGraphClient(session_id)
        payload: Dict[str, Any] = {}
        if subject is not None: payload["subject"] = subject
        if body is not None: payload["body"] = {"contentType": "HTML", "content": body}
        if location is not None: payload["location"] = {"displayName": location}
        if start_time is not None: payload["start"] = {"dateTime": start_time, "timeZone": time_zone or "UTC"}
        if end_time is not None: payload["end"] = {"dateTime": end_time, "timeZone": time_zone or "UTC"}

        result = client.update_event(event_id, payload)
        return f"Successfully updated event. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=DeleteEventSchema)
def delete_event(session_id: str, event_id: str) -> str:
    """Delete a calendar event."""
    try:
        client = MicrosoftGraphClient(session_id)
        client.delete_event(event_id)
        return "Successfully deleted event."
    except Exception as e:
        return _format_error(e)

# ---------------------------------------------------------
# TO-DO TOOLS
# ---------------------------------------------------------

@tool(args_schema=SessionAuthSchema)
def get_todo_lists(session_id: str) -> str:
    """Fetch the user's Microsoft To-Do task lists."""
    try:
        client = MicrosoftGraphClient(session_id)
        return str(client.get_todo_lists())
    except Exception as e:
        return _format_error(e)

@tool(args_schema=GetTodosSchema)
def get_todos(session_id: str, list_id: Optional[str] = None) -> str:
    """Fetch tasks from a specific To-Do list, clearly categorized into Pending, Overdue, and Completed tasks."""
    try:
        client = MicrosoftGraphClient(session_id)
        resolved_list_id = _resolve_list_id(client, list_id)
        raw_res = client.get_todos(resolved_list_id)
        if isinstance(raw_res, dict) and "value" in raw_res:
            tasks = raw_res["value"]
            if not tasks:
                return "No tasks found in your To-Do list."
            
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            overdue_tasks = []
            pending_tasks = []
            completed_tasks = []
            
            for t in tasks:
                t_id = t.get("id", "")
                t_title = t.get("title", "Untitled Task")
                t_status = t.get("status", "notStarted")
                due_dt = t.get("dueDateTime", {})
                due_val = due_dt.get("dateTime", "") if isinstance(due_dt, dict) else ""
                due_date_str = due_val[:10] if due_val else ""
                due_info = f" | Due: {due_val[:16].replace('T', ' ')}" if due_val else " | No due date"
                
                item_text = f"- ID: {t_id}\n  Title: '{t_title}'{due_info} | Status: {t_status}"
                
                if t_status == "completed":
                    completed_tasks.append(item_text)
                elif due_date_str and due_date_str < today_str:
                    overdue_tasks.append(item_text + " [OVERDUE]")
                else:
                    pending_tasks.append(item_text)
            
            res_lines = [f"To-Do Tasks Overview (Current Date: {today_str}):"]
            if overdue_tasks:
                res_lines.append("\n⚠️ OVERDUE TASKS:\n" + "\n".join(overdue_tasks))
            if pending_tasks:
                res_lines.append("\n☑️ PENDING / UPCOMING TASKS:\n" + "\n".join(pending_tasks))
            if completed_tasks:
                res_lines.append("\n✅ COMPLETED TASKS:\n" + "\n".join(completed_tasks))
                
            return "\n".join(res_lines)
            
        return str(raw_res)
    except Exception as e:
        return _format_error(e)

@tool(args_schema=GetTodoSchema)
def get_todo(session_id: str, task_id: str, list_id: Optional[str] = None) -> str:
    """Fetch a specific task from a To-Do list."""
    try:
        client = MicrosoftGraphClient(session_id)
        resolved_list_id = _resolve_list_id(client, list_id)
        return str(client.get_todo(resolved_list_id, task_id))
    except Exception as e:
        return _format_error(e)

@tool(args_schema=CreateTodoSchema)
def create_todo(
    session_id: str,
    title: str,
    list_id: Optional[str] = None,
    body: Optional[str] = "",
    due_date: Optional[str] = "",
    due_time: Optional[str] = "",
    importance: Optional[str] = ""
) -> str:
    """Create a new task in a To-Do list."""
    try:
        client = MicrosoftGraphClient(session_id)
        resolved_list_id = _resolve_list_id(client, list_id)
        result = client.create_todo(
            list_id=resolved_list_id,
            title=title,
            body=body,
            due_date=due_date,
            due_time=due_time,
            importance=importance
        )
        return f"Successfully created task. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=UpdateTodoSchema)
def update_todo(
    session_id: str,
    task_id: str,
    list_id: Optional[str] = None,
    title: Optional[str] = None,
    body: Optional[str] = None,
    importance: Optional[str] = None,
    status: Optional[str] = None
) -> str:
    """Update a specific task in a To-Do list (e.g., mark as completed)."""
    try:
        client = MicrosoftGraphClient(session_id)
        resolved_list_id = _resolve_list_id(client, list_id)
        payload: Dict[str, Any] = {}
        if title is not None: payload["title"] = title
        if body is not None: payload["body"] = {"contentType": "text", "content": body}
        if importance is not None: payload["importance"] = importance
        if status is not None: payload["status"] = status

        result = client.update_todo(resolved_list_id, task_id, payload)
        return f"Successfully updated task. ID: {result.get('id', 'Unknown')}"
    except Exception as e:
        return _format_error(e)

@tool(args_schema=DeleteTodoSchema)
def delete_todo(session_id: str, task_id: str, list_id: Optional[str] = None) -> str:
    """Delete a task from a To-Do list."""
    try:
        client = MicrosoftGraphClient(session_id)
        resolved_list_id = _resolve_list_id(client, list_id)
        client.delete_todo(resolved_list_id, task_id)
        return "Successfully deleted task."
    except Exception as e:
        return _format_error(e)

# ---------------------------------------------------------
# RAG & WEB SEARCH TOOLS
# ---------------------------------------------------------

class SearchDocumentsSchema(SessionAuthSchema):
    query: str = Field(..., description="The search question to query uploaded local documents (PDF, DOCX, TXT, MD) using RAG vector search.")
    top_k: Optional[int] = Field(4, description="Number of relevant document chunks to retrieve.")

class WebSearchToolSchema(SessionAuthSchema):
    query: str = Field(..., description="The search query to search the internet for latest news, current events, online technical documentation, or live external information.")

@tool(args_schema=SearchDocumentsSchema)
def search_documents(session_id: str, query: str, top_k: int = 4) -> str:
    """Search local uploaded documents (PDF, Word DOCX, TXT, Markdown) and private knowledge base using RAG vector search. Use this tool for ALL questions asking about uploaded files, PDFs, documents, or RAG. This tool DOES NOT query Outlook emails or Microsoft Graph."""
    try:
        rag_service = CorrectiveRAGService()
        result = rag_service.retrieve_with_correction(query, top_k=top_k)
        
        chunks = result.get("chunks", [])
        if not chunks:
            return f"No relevant document content found in uploaded local files for query: '{query}'."
            
        formatted_chunks = []
        for doc_chunk, score in chunks:
            meta = doc_chunk.metadata
            source = meta.get("source", "Unknown Document")
            page_info = f" (Page {meta.get('page')})" if "page" in meta else ""
            formatted_chunks.append(f"Source: {source}{page_info} | Score: {round(score, 3)}\nContent: {doc_chunk.page_content}")
            
        header = f"Found {len(chunks)} relevant document snippet(s) [Corrective RAG retries: {result.get('retries', 0)}]:"
        return f"{header}\n\n" + "\n\n---\n\n".join(formatted_chunks)
    except Exception as e:
        return f"Error executing RAG document search: {str(e)}"

@tool(args_schema=WebSearchToolSchema)
def web_search(session_id: str, query: str) -> str:
    """Search the internet for current online information, latest tech documentation, external news, or live web data."""
    try:
        data = execute_web_search(query)
        results = data.get("results", [])
        if not results:
            return f"No external web search results found for query: '{query}'."
            
        formatted = []
        if data.get("answer"):
            formatted.append(f"Web Summary: {data['answer']}")
            
        for idx, r in enumerate(results, start=1):
            title = r.get("title", "No Title")
            url = r.get("url", "")
            snippet = r.get("content", "")
            formatted.append(f"{idx}. [{title}]({url})\n   Snippet: {snippet}")
            
        return f"Web Search Results for '{query}' (Provider: {data.get('provider', 'Tavily')}):\n\n" + "\n\n".join(formatted)
    except Exception as e:
        return f"Error executing Web Search: {str(e)}"

# List of all tools to bind to the LLM
jarvis_tools = [
    get_emails, get_email, delete_email, delete_all_drafts, create_email_draft, create_reply_draft, summarize_and_draft_reply,
    get_events, get_event, create_event, update_event, delete_event,
    get_todo_lists, get_todos, get_todo, create_todo, update_todo, delete_todo,
    search_documents, web_search
]
