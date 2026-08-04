# 📐 Jarvis AI Copilot: System Visualizations & Diagrams

This document contains visual diagrams for the **Jarvis AI Academic Copilot**:
1. **Architecture Diagram**: High-level structural components & system layers.
2. **Flow Diagram (Sequence Diagram)**: Step-by-step data execution pipeline.
3. **Entity Relationship (ER) Diagram**: Supabase database schema and relationships.

---

## 🏗️ 1. System Architecture Diagram

```mermaid
graph TD
    subgraph Client_Layer["🖥️ Frontend Client Layer"]
        UI["Dashboard Web UI (HTML5 / Vanilla CSS / JS)"]
        STT["🎤 Web Speech STT (webkitSpeechRecognition)"]
        TTS["🔊 Browser SpeechSynthesis TTS Engine"]
        LiveKitWebRTC["🎧 LiveKit WebRTC Real-Time Audio Client"]
    end

    subgraph Backend_Layer["⚡ FastAPI Backend Infrastructure"]
        Router["FastAPI Application Gateway / REST API"]
        AuthModule["Microsoft OAuth2 & Token Manager"]
        Config["Centralized Config & Tuning Knobs (app/config.py)"]
        
        subgraph Agent_Engine["🧠 LangGraph AI Reasoning Engine"]
            StateGraph["LangGraph State Machine (StateGraph)"]
            ModelFallback["Multi-Model Fallback Chain"]
            ToolNode["LangChain Tool Execution Engine"]
        end

        VoiceWorker["🎙️ LiveKit Agents Voice Worker (VoicePipelineAgent)"]
    end

    subgraph External_Services["☁️ External Cloud Services & APIs"]
        Groq["⚡ Groq LPU Cloud (Llama 3.3 70B / Llama 3.1 8B)"]
        Supabase["🗄️ Supabase PostgreSQL & Auth Store"]
        MSGraph["Microsoft Graph API (Emails, Calendar, MS To-Do)"]
    end

    %% Connections
    UI <-->|HTTP / REST JSON| Router
    STT --> UI
    UI --> TTS
    LiveKitWebRTC <-->|WebRTC Stream| VoiceWorker
    Router --> AuthModule
    Router --> StateGraph
    StateGraph --> ModelFallback
    ModelFallback <-->|Chat Completions & Tool Calls| Groq
    ModelFallback --> ToolNode
    ToolNode <-->|Authenticated API Calls| MSGraph
    AuthModule <-->|Token Storage & OAuth| Supabase
    StateGraph <-->|Persistence & History| Supabase
    Config --> StateGraph
```

---

## 🔄 2. End-to-End Sequence Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as 👤 Researcher
    participant UI as 🖥️ Dashboard Web UI
    participant STT as 🎤 Speech-to-Text
    participant Server as ⚡ FastAPI Backend
    participant Agent as 🧠 LangGraph Agent
    participant LLM as ⚡ Groq LLM Engine
    participant Tools as 🛠️ MS Graph Tools
    participant MS as ☁️ Microsoft 365
    participant TTS as 🔊 Text-to-Speech

    User->>UI: Speaks voice command or types prompt
    UI->>STT: Start audio stream recognition
    STT-->>UI: Real-time text transcript
    UI->>Server: POST /api/chat (Message + Conversation ID)
    Server->>Agent: Invoke State Graph (History + System Prompt + Session ID)
    Agent->>LLM: Send Prompt + Tool Schemas (Tuning: Temp=0.3, MaxTokens=400)
    
    alt Agent Decides Tool Invocation
        LLM-->>Agent: Returns Tool Call Request (e.g. get_emails / create_todo)
        Agent->>Tools: Inject Session ID & Execute Tool
        Tools->>MS: Fetch/Modify Data via Microsoft Graph API
        MS-->>Tools: Graph JSON Response
        Tools-->>Agent: Tool Output State
        Agent->>LLM: Pass Tool Result back for final synthesis
    end

    LLM-->>Agent: Returns natural response text
    Agent-->>Server: Final AI response
    Server-->>UI: Return JSON { conversation_id, reply }
    UI->>TTS: Speak response text (Tuning: Rate=0.98, Pitch=1.0)
    TTS-->>User: Plays natural voice audio response
```

---

## 🗄️ 3. Entity Relationship (ER) Diagram (Database Schema)

```mermaid
erDiagram
    users ||--o{ user_sessions : "has"
    users ||--o{ conversations : "owns"
    conversations ||--|{ messages : "contains"

    users {
        uuid id PK "Primary Key (Auth User ID)"
        string email "User Email Address"
        string full_name "User Full Name"
        timestamp created_at "Account Creation Date"
    }

    user_sessions {
        uuid id PK "Session Primary Key"
        uuid user_id FK "Foreign Key to auth.users"
        string email "Microsoft Account Email"
        string name "User Display Name"
        string access_token_encrypted "AES Encrypted MS Access Token"
        string refresh_token_encrypted "AES Encrypted MS Refresh Token"
        string provider "Default: microsoft_azure"
        timestamp created_at "Session Created Timestamp"
        timestamp updated_at "Session Updated Timestamp"
    }

    conversations {
        uuid id PK "Conversation UUID"
        uuid user_id FK "Foreign Key to auth.users"
        string title "Conversation Title / First Prompt"
        timestamp created_at "Created Timestamp"
        timestamp updated_at "Last Message Timestamp"
    }

    messages {
        uuid id PK "Message UUID"
        uuid conversation_id FK "Foreign Key to conversations.id"
        string role "user | assistant | system"
        string content "Message text content"
        timestamp created_at "Message Timestamp"
    }
```
