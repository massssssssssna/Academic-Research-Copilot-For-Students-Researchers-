import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.auth.routes import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.emails import router as email_router
from app.routes.events import router as events_router
from app.routes.todos import router as todos_router
from app.routes.conversations import router as conversations_router
from app.routes.livekit import router as livekit_router
from app.database.supabase import supabase_db

app = FastAPI(
    title=settings.APP_NAME,
    description="Jarvis — Your AI assistant for Microsoft 365 (Calendar, Mail, To-Do)",
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1, "docExpansion": "none"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(email_router)
app.include_router(events_router)
app.include_router(todos_router)
app.include_router(conversations_router)
app.include_router(livekit_router)

# Serve /static directory (CSS, JS, images)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_html(filename: str) -> str:
    path = os.path.join(BASE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root — redirect to login or dashboard depending on session."""
    session_id = request.cookies.get("jarvis_session")
    if session_id and supabase_db.get_user_session(session_id):
        return RedirectResponse(url="/dashboard.html", status_code=302)
    return RedirectResponse(url="/login.html", status_code=302)


@app.get("/login.html", response_class=HTMLResponse)
async def serve_login():
    return HTMLResponse(content=_read_html("login.html"))


@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Protected — redirect to login if not authenticated."""
    session_id = request.cookies.get("jarvis_session")
    if not session_id or not supabase_db.get_user_session(session_id):
        return RedirectResponse(url="/login.html?error=Please+sign+in+to+continue", status_code=302)
    return HTMLResponse(content=_read_html("dashboard.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
