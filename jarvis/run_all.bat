@echo off
echo Starting Jarvis Academic Research Copilot Services...

start "Jarvis FastAPI Server" cmd /k "cd /d "%~dp0" && .venv\Scripts\uvicorn app.main:app --reload --port 8000"
start "Jarvis Caddy Proxy" cmd /k "cd /d "%~dp0" && caddy.exe run --config Caddyfile"
start "Jarvis Voice Agent" cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe -m app.voice_agent dev"

echo All 3 services (FastAPI, Caddy, LiveKit Voice Agent) launched in separate windows!
