-- ========================================================
-- JARVIS ACADEMIC COPILOT — COMPLETE SUPABASE SETUP SCRIPT
-- Paste this script directly into Supabase SQL Editor & click RUN
-- ========================================================

-- 1. Create user_sessions table
CREATE TABLE IF NOT EXISTS public.user_sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    email TEXT,
    name TEXT,
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    provider TEXT DEFAULT 'microsoft_azure',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create conversations table
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Disable Row Level Security (RLS) so FastAPI API requests can insert & read without 401 errors
ALTER TABLE public.user_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages DISABLE ROW LEVEL SECURITY;

-- 5. Grant full permissions to anon & authenticated API roles
GRANT ALL ON TABLE public.user_sessions TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.conversations TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.messages TO anon, authenticated, service_role;

-- 6. Add permissive fallback RLS policies in case RLS is re-enabled
DROP POLICY IF EXISTS "Allow anon all user_sessions" ON public.user_sessions;
CREATE POLICY "Allow anon all user_sessions" ON public.user_sessions FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon all conversations" ON public.conversations;
CREATE POLICY "Allow anon all conversations" ON public.conversations FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon all messages" ON public.messages;
CREATE POLICY "Allow anon all messages" ON public.messages FOR ALL USING (true) WITH CHECK (true);
