import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings(BaseSettings):
    APP_NAME: str = "Jarvis Academic Research Copilot"
    DEBUG: bool = True
    
    # Supabase Settings
    SUPABASE_URL: str = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://iztqgmhcimuficgpfvki.supabase.co")
    SUPABASE_KEY: str = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_R8gPDMHV52AqAwA9PJiWPQ_Ek1GUbjw")
    # Service role key bypasses RLS — set this in .env as SUPABASE_SERVICE_KEY
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_PROJECT_ID: str = os.getenv("SUPABASE_PROJECT_ID", "iztqgmhcimuficgpfvki")
    SUPABASE_REGION: str = os.getenv("SUPABASE_REGION", "ap-southeast-2")
    
    # ── LLM & AGENT TUNING KNOBS ───────────────────────────
    LLM_PRIMARY_MODEL: str = os.getenv("LLM_PRIMARY_MODEL", "llama-3.3-70b-versatile")  # Main reasoning model
    LLM_FAST_MODEL: str = os.getenv("LLM_FAST_MODEL", "llama-3.1-8b-instant")          # Low-latency fallback model
    LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL", "gemma2-9b-it")   # Supported fallback model
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))               # 0.0 (accurate/deterministic) to 1.0 (creative)
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "400"))                      # Maximum generation token limit per response
    
    # ── VOICE ASSISTANT & TTS/STT TUNING KNOBS ─────────────
    TTS_SPEECH_RATE: float = float(os.getenv("TTS_SPEECH_RATE", "0.98"))               # Playback speech rate (0.5 to 2.0)
    TTS_SPEECH_PITCH: float = float(os.getenv("TTS_SPEECH_PITCH", "1.0"))               # Speech pitch frequency (0.5 to 1.5)
    TTS_DEFAULT_VOICE: str = os.getenv("TTS_DEFAULT_VOICE", "alloy")                    # Default TTS voice choice
    VAD_THRESHOLD: float = float(os.getenv("VAD_THRESHOLD", "0.5"))                     # Voice Activity Detection sensitivity (0.1 to 0.9)
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "en-US")                              # Speech Recognition language code
    
    # ── API TOOL PAGINATION & PAYLOAD KNOBS ────────────────
    GRAPH_DEFAULT_TOP: int = int(os.getenv("GRAPH_DEFAULT_TOP", "10"))                  # Default items per M365 Graph fetch call
    
    # Groq API Key
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Supabase Settings
    
    # Microsoft OAuth Settings
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "common")
    MICROSOFT_REDIRECT_URI: str = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
