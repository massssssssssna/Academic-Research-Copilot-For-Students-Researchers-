import os
import base64
import urllib.parse
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.auth.microsoft_oauth import ms_oauth
from app.database.supabase import supabase_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _make_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()


def _redirect_error(reason: str):
    return RedirectResponse(
        url=f"/login.html?error={urllib.parse.quote(reason)}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# GET /auth/login  — Start Microsoft OAuth (via Supabase Azure provider)
# ---------------------------------------------------------------------------
@router.get("/login")
async def login():
    state = _make_state()
    auth_url = ms_oauth.get_authorization_url(state)

    response = RedirectResponse(url=auth_url, status_code=302)
    # Store state in cookie so we can validate it in the callback
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------
# GET /auth/callback  — Supabase redirects here after Microsoft login
# ---------------------------------------------------------------------------
@router.get("/callback")
async def callback(
    request: Request,
    code: str = None,
    error: str = None,
    error_description: str = None,
):
    # If Supabase/Azure returned an error
    if error or not code:
        reason = error_description or error or "Authentication was cancelled or failed."
        return _redirect_error(reason)

    state = request.cookies.get("oauth_state")
    if not state:
        return _redirect_error("Login session expired. Please try again.")

    try:
        tokens = ms_oauth.exchange_code_for_tokens(code, state)
    except Exception as exc:
        return _redirect_error(str(exc))

    # Ensure we got a real Microsoft Graph access token
    if not tokens.get("access_token"):
        return _redirect_error(
            "Microsoft did not return an access token. "
            "Ensure 'provider_token' is enabled in Supabase Auth settings."
        )

    # Create a server-side session
    session_id = "sess_" + base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()
    supabase_db.save_user_tokens(session_id, tokens)

    response = RedirectResponse(url="/dashboard.html", status_code=302)
    response.set_cookie(
        key="jarvis_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,  # 8 hours
    )
    response.delete_cookie("oauth_state")
    return response


# ---------------------------------------------------------------------------
# GET /auth/me  — Return current user info (used by frontend JS)
# ---------------------------------------------------------------------------
@router.get("/me")
async def get_me(request: Request):
    session_id = request.cookies.get("jarvis_session")
    session = supabase_db.get_user_session(session_id) if session_id else None

    if session:
        return {
            "authenticated": True,
            "user": {
                "email": session.get("email", ""),
                "name": session.get("name", "User"),
            },
        }
    return JSONResponse({"authenticated": False, "user": None}, status_code=401)


# ---------------------------------------------------------------------------
# GET /auth/logout  — Clear session and redirect to login
# ---------------------------------------------------------------------------
@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("jarvis_session")
    if session_id:
        supabase_db.delete_session(session_id)

    response = RedirectResponse(url="/login.html", status_code=302)
    response.delete_cookie("jarvis_session")
    return response
