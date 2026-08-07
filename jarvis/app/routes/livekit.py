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

    import json
    session_id = request.cookies.get("jarvis_session") or ""
    metadata_json = json.dumps({"session_id": session_id, "email": current_user.get("email")})

    token = (
        api.AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(identity)
        .with_name(user_name)
        .with_metadata(metadata_json)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    # 2. Dispatch LiveKit Agent to the room cleanly
    try:
        async with api.LiveKitAPI(
            settings.LIVEKIT_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        ) as lk_api:
            # Clear old dispatches for this room to prevent double runner collision
            try:
                dispatches = await lk_api.agent_dispatch.list_dispatch(room=room)
                for d in getattr(dispatches, "agent_dispatches", []):
                    await lk_api.agent_dispatch.delete_dispatch(dispatch_id=d.id, room=room)
            except Exception:
                pass

            await lk_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name="jarvis",
                    room=room,
                    metadata=metadata_json,
                )
            )
            print(f"Agent 'jarvis' dispatched successfully to room: {room} with session metadata.")
    except Exception as e:
        print(f"Agent dispatch notice: {e}")


    return {
        "token": token.to_jwt(),
        "ws_url": settings.LIVEKIT_URL,
        "room": room,
    }


