# Jarvis: AI Academic Research Copilot

Jarvis is a modular FastAPI application acting as an AI Academic Copilot. It integrates deeply with Microsoft 365, uses Groq as its core LLM reasoning engine, and ensures secure, server-side OAuth token management via Supabase.

## 🌟 Project Overview
Jarvis is designed to act as an autonomous assistant for academic researchers, managing their inbox, calendar, and task lists. Through natural language interactions, researchers can ask Jarvis to organize their schedules, read recent emails, draft replies, and add to-dos. The system enforces strict security and permissions (no automatic email sending allowed).

## 🏗️ Architecture
The backend is structured to isolate responsibilities:
- **FastAPI**: Serves the REST API and static HTML frontend.
- **Supabase**: Handles the initial Microsoft Azure OAuth flow and securely stores user conversations, messages, and encrypted Microsoft tokens.
- **LangGraph**: Orchestrates the AI agent flow using a state graph.
- **Groq LLM**: Powers the reasoning engine (`llama-3.3-70b-versatile`) which decides which tools to invoke based on user prompts.
- **LangChain Tools**: Connects the reasoning engine directly to the `MicrosoftGraphClient` securely over the backend.

## ✨ Features
- **Secure Microsoft OAuth**: Authenticates via Azure AD utilizing Supabase Auth.
- **Agentic Reasoning**: Natural language task handling using LangGraph and Groq.
- **Email Management**: Reads inbox and creates drafts/replies.
- **Calendar Management**: Full CRUD for calendar events.
- **To-Do Management**: Full CRUD for Microsoft To-Do task lists.
- **Persistent Memory**: Retains conversation context and messages in Supabase.

## 🛠️ Tech Stack
- **Backend Framework**: FastAPI (Python)
- **Voice Agent Framework**: LiveKit Agents Framework (`livekit-agents`)
- **Agent Orchestration**: LangGraph & LangChain Core
- **LLM Provider**: Groq
- **Database & Auth**: Supabase (PostgreSQL)
- **External APIs**: Microsoft Graph API

## 📁 Folder Structure
```
jarvis/
│
├── app/
│   ├── main.py                     # Primary FastAPI entrypoint
│   ├── config.py                   # Pydantic configuration
│   │
│   ├── auth/
│   │   ├── routes.py               # Authentication REST endpoints (/auth/login, /auth/callback)
│   │   └── microsoft_oauth.py      # Microsoft Azure OAuth2 service
│   │
│   ├── graph/
│   │   ├── client.py               # Microsoft Graph HTTP API client
│   │   ├── email.py                # Email tool bindings
│   │   ├── calendar.py             # Calendar tool bindings
│   │   └── todo.py                 # To-Do tool bindings
│   │
│   ├── agent/
│   │   ├── state.py                # LangGraph State definitions
│   │   ├── tools.py                # Action tools exposed to the LLM
│   │   └── graph.py                # LangGraph reasoning agent engine
│   │
│   ├── routes/
│   │   ├── chat.py                 # Chat interface endpoint
│   │   ├── conversations.py        # Conversation persistence endpoints
│   │   └── ...                     # Sub-service endpoints
│   │
│   └── database/
│       └── supabase.py             # Supabase service and token encryption
│
├── .env                            # Environment variables (Git-ignored)
├── .gitignore                      # Git ignore rules
├── requirements.txt                # Python dependencies
└── README.md                       # Project documentation
```

## 🔐 Environment Variables Required
Create a `.env` file in the root directory (it is automatically ignored by Git):

```ini
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-anon-key
SUPABASE_PROJECT_ID=your-project-id
SUPABASE_REGION=your-region

MICROSOFT_CLIENT_ID=your-azure-client-id
MICROSOFT_CLIENT_SECRET=your-azure-client-secret
MICROSOFT_TENANT_ID=common
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/callback

GROQ_API_KEY=your-groq-api-key
```

## ⚙️ Setup Instructions
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure your `.env` file as shown above.

### Microsoft/Supabase OAuth Setup
- Register an app in **Azure Active Directory (Entra ID)**.
- Set the Redirect URI to match your Supabase instance Auth callback URL.
- Enable `Mail.ReadWrite`, `Calendars.ReadWrite`, `Tasks.ReadWrite`, and `User.Read` permissions.
- In **Supabase**, enable the Azure provider and paste your Microsoft Client ID and Secret.

### Groq Setup
- Generate an API key from the [Groq Console](https://console.groq.com/).
- Place it in your `.env` under `GROQ_API_KEY`.
- The system is pre-configured to use the `llama-3.3-70b-versatile` tool-calling model.

## 🚀 How to Run FastAPI
Start the local server using Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
- **Landing Page**: http://localhost:8000/
- **Dashboard**: http://localhost:8000/dashboard.html
- **API Docs**: http://localhost:8000/docs

## 📡 Available API Endpoints
- `GET /auth/login` - Triggers the OAuth flow.
- `GET /auth/callback` - Captures OAuth tokens.
- `GET /auth/logout` - Ends the session.
- `POST /api/chat` - Submits a prompt to the LangGraph agent.
- `GET /api/conversations` - Retrieves user chat history.
- `GET /api/events`, `POST /api/events`, etc. - Manual endpoints for Graph services.

## 🛡️ Security Notes
- Tokens are securely stored and fetched server-side from Supabase.
- No `access_token` or `refresh_token` is ever exposed to the frontend or directly injected into the LLM context state.
- Authentication utilizes HTTP-only cookies (`jarvis_session`).
- The Groq API key is securely loaded on the server and never hardcoded in the codebase.

## 🛑 IMPORTANT LIMITATION
**Email sending is intentionally disabled.** 
For safety and security reasons, Jarvis will NEVER autonomously send an email. There is no `send_email` tool, and the Microsoft Graph `/me/sendMail` endpoint is completely removed. Jarvis is strictly limited to reading emails and saving responses as **Drafts** in the user's Outlook Drafts folder.
