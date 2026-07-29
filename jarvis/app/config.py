import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

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
    
    # LLM Settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Microsoft OAuth Settings
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "common")
    MICROSOFT_REDIRECT_URI: str = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
