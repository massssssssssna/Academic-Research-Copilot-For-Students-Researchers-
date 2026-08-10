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
    LLM_PRIMARY_MODEL: str = os.getenv("LLM_PRIMARY_MODEL", "llama-3.3-70b-versatile") # High capacity 100k TPM model
    LLM_FAST_MODEL: str = os.getenv("LLM_FAST_MODEL", "llama-3.1-8b-instant")          # Low-latency model
    LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant")   # Active fallback model
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))               # 0.0 (accurate/deterministic) to 1.0 (creative)
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "150"))                      # Short generation token limit for instant speech
    
    # ── VOICE ASSISTANT & TTS/STT TUNING KNOBS ─────────────
    TTS_SPEECH_RATE: float = float(os.getenv("TTS_SPEECH_RATE", "1.1"))               # Fast playback speech rate
    TTS_SPEECH_PITCH: float = float(os.getenv("TTS_SPEECH_PITCH", "1.0"))               # Speech pitch frequency
    TTS_DEFAULT_VOICE: str = os.getenv("TTS_DEFAULT_VOICE", "alloy")                    # Default TTS voice choice
    VAD_THRESHOLD: float = float(os.getenv("VAD_THRESHOLD", "0.5"))                     # Voice Activity Detection sensitivity
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "en-US")                              # Speech Recognition language code
    
    # ── TURN DETECTION & INTERRUPTION TUNING KNOBS ─────────
    MINIMUM_DELAY: float = float(os.getenv("MINIMUM_DELAY", "0.2"))                     # 200ms min turn completion delay for instant response
    MAXIMUM_DELAY: float = float(os.getenv("MAXIMUM_DELAY", "0.8"))                     # 800ms max silence delay before forcing response
    INTERRUPTION_MIN_DURATION_MS: int = int(os.getenv("INTERRUPTION_MIN_DURATION_MS", "300")) # Min speech duration (ms) to trigger interruption
    INTERRUPTION_MIN_WORDS: int = int(os.getenv("INTERRUPTION_MIN_WORDS", "1"))         # Min words needed to trigger interruption
    INTERRUPTION_FALSE_TIMEOUT_MS: int = int(os.getenv("INTERRUPTION_FALSE_TIMEOUT_MS", "500")) # False interruption timeout (ms)

    @property
    def minimum_delay(self) -> float:
        return self.MINIMUM_DELAY

    @property
    def maximum_delay(self) -> float:
        return self.MAXIMUM_DELAY

    @property
    def interruption_min_duration_ms(self) -> int:
        return self.INTERRUPTION_MIN_DURATION_MS

    @property
    def interruption_min_words(self) -> int:
        return self.INTERRUPTION_MIN_WORDS

    @property
    def interruption_false_timeout_ms(self) -> int:
        return self.INTERRUPTION_FALSE_TIMEOUT_MS
    
    # ── API TOOL PAGINATION & PAYLOAD KNOBS ────────────────
    GRAPH_DEFAULT_TOP: int = int(os.getenv("GRAPH_DEFAULT_TOP", "10"))                  # Default items per M365 Graph fetch call
    
    # Groq API Keys (Pool for failover rotation)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    def get_groq_api_keys(self) -> list[str]:
        keys = []
        possible_vars = [
            "GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5",
            "GROQ_1", "GROQ_2", "GROQ_3", "GROQ_4", "GROQ_5"
        ]
        for var in possible_vars:
            val = os.getenv(var, "").strip()
            if val and val not in keys:
                keys.append(val)
        return keys


    # Deepgram & Cartesia API Keys for Voice Agent
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")
    CARTESIA_API_KEY: str = os.getenv("CARTESIA_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── LIVEKIT CONNECTION SETTINGS ────────────────────────────
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")            # e.g. wss://your-project.livekit.cloud
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")    # LiveKit API key
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")  # LiveKit API secret

    # Microsoft OAuth Settings
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "common")
    MICROSOFT_REDIRECT_URI: str = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
