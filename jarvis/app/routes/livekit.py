from fastapi import APIRouter, HTTPException, Query, Request
from livekit import api

from app.database.supabase import supabase_db
from app.config import settings

router = APIRouter(prefix="/api/livekit", tags=["LiveKit"])


def get_current_user_info(request: Request) -> dict:
    session_id = request.cookies.get("jarvis_session")
    if session_id:
        session = supabase_db.get_user_session(session_id)
        if session:
            return {
                "email": session.get("email", "user@example.com"),
                "name": session.get("name", "Jarvis User"),
                "user_id": session.get("user_id", "user"),
            }
    return {"email": "user@example.com", "name": "Jarvis User", "user_id": "guest"}


@router.get("/token")
async def get_livekit_token(
    request: Request,
    room: str = Query("jarvis-room", description="LiveKit room name"),
):
    """
    Generate a LiveKit WebRTC Access Token for the authenticated user to join a room.
    The LiveKit Voice Agent worker will be auto-assigned to this room.
    """
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit API Key or Secret is missing in server environment.",
        )

    current_user = get_current_user_info(request)
    identity = current_user.get("email") or current_user.get("user_id") or "user"
    user_name = current_user.get("name") or identity

    token = (
        api.AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(identity)
        .with_name(user_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    # 2. Dispatch LiveKit Agent to the room
    try:
        lk_api = api.LiveKitAPI(
            settings.LIVEKIT_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        )
        await lk_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="",
                room=room,
            )
        )
        await lk_api.aclose()
    except Exception as e:
        print(f"Agent dispatch notice: {e}")

    return {
        "token": token.to_jwt(),
        "ws_url": settings.LIVEKIT_URL,
        "room": room,
    }


