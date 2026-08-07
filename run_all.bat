@echo off
echo Starting Jarvis Academic Research Copilot Services...

cd /d "%~dp0jarvis"

start "Jarvis FastAPI Server" cmd /k "cd /d "%~dp0jarvis" && .venv\Scripts\uvicorn app.main:app --reload --port 8000"
start "Jarvis Caddy Proxy" cmd /k "cd /d "%~dp0jarvis" && caddy.exe run --config Caddyfile"
start "Jarvis Voice Agent" cmd /k "cd /d "%~dp0jarvis" && .venv\Scripts\python.exe -m app.voice_agent dev"

echo All 3 services launched successfully!
