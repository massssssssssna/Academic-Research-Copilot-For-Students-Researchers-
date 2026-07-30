# Jarvis Architecture Overview

This document explains exactly how Jarvis operates behind the scenes, specifically focusing on how it manages To-Do tasks, Calendar events, and Email drafting.

## 1. High-Level Flow
Whenever you send a message in the Jarvis UI:
1. The frontend (`dashboard.html` + `static/main.js`) sends a `POST` request to `/api/chat`.
2. The `chat.py` router validates your session using Supabase.
3. The prompt is passed to the **LangGraph Agent** (`app/agent/graph.py`).
4. The Agent uses **Groq LLM (Llama 3.3 70b)** as its "brain".
5. The LLM determines if it needs to trigger any "Tools" to accomplish your request.

## 2. How the AI "Tools" Work (`app/agent/tools.py`)
The LLM cannot directly connect to the internet. Instead, we give it a specific list of Python functions (tools). If you ask: *"What are my emails?"*, the LLM says *"Ah, I need to use the `get_emails` tool."*

All tools eventually talk to the **MicrosoftGraphClient** (`app/graph/client.py`), which uses the secure OAuth token from Supabase to fetch your real data.

### 📅 Calendar Events
- **Tools**: `get_events`, `create_event`, `update_event`, `delete_event`
- **How it works**: The AI asks the Graph Client to call `/me/events`. It translates natural language (e.g., "Tomorrow at 5 PM") into strict ISO 8601 timestamps and creates the event on your actual Outlook calendar.

### ✅ To-Do Tasks
- **Tools**: `get_todos`, `create_todo`, `update_todo`, `delete_todo`
- **How it works**: The AI fetches your MS To-Do lists, finds the "Default" list (or a specific one), and calls `/me/todo/lists/{id}/tasks`. It can mark tasks as completed or change their importance.

### 📧 Email Management (Reading & Drafting)
- **Reading Emails**: The `get_emails` tool calls `/me/messages` (or `/me/mailFolders/drafts/messages` for drafts). It fetches the latest emails and their preview text so the AI can summarize them for you.
- **Drafting Replies**: The `create_email_draft` and `create_reply_draft` tools call the Microsoft Graph API. **Important:** The `/sendMail` endpoint is completely removed for safety. The API instead calls `/createReply` or `POST /me/messages`, which strictly saves the polished email to your **Outlook Drafts folder**. The AI takes your rough instructions, turns them into a highly professional response based on its System Prompt, and drafts it.

## 3. Storage and Security (`app/database/supabase.py`)
- **No Local Fallbacks**: The system strictly uses Supabase. If Supabase is down or blocked by RLS, the app throws a 500 error rather than silently failing.
- **User Sessions**: Microsoft access and refresh tokens are encrypted and saved in the `user_sessions` table.
- **Conversations & Messages**: Every message you send to the bot is securely persisted in the `conversations` and `messages` tables, allowing chat history to survive server restarts.

## Summary
When you say: *"Draft a professional reply to the last email saying I am busy"*
1. LLM uses `get_emails` to find the last email ID.
2. LLM formulates a highly professional response.
3. LLM uses `create_reply_draft` passing the ID and the new content.
4. Microsoft Graph API saves it in your Drafts folder.
5. LLM responds to you in the chat saying the draft is ready!
