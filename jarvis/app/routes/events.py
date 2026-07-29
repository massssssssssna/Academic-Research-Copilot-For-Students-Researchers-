from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from app.graph.client import MicrosoftGraphClient, MicrosoftGraphError

router = APIRouter(prefix="/api/events", tags=["Events"])

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

class CreateEventPayload(BaseModel):
    subject: str
    start_datetime: datetime
    end_datetime: datetime
    timezone: str = "UTC"
    body: Optional[str] = ""
    location: Optional[str] = ""
    attendees: Optional[List[EmailStr]] = []
    is_online_meeting: Optional[bool] = False

class UpdateEventPayload(BaseModel):
    subject: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    body: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[EmailStr]] = None

@router.get("")
async def get_events(
    top: int = 10, 
    skip: int = 0, 
    start_datetime: Optional[datetime] = None, 
    end_datetime: Optional[datetime] = None, 
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        start_str = start_datetime.isoformat() if start_datetime else None
        end_str = end_datetime.isoformat() if end_datetime else None
        return client.get_events(top=top, skip=skip, start_datetime=start_str, end_datetime=end_str)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/{event_id}")
async def get_event(
    event_id: str, 
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_event(event_id)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("")
async def create_event(
    payload: CreateEventPayload, 
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.create_event(
            subject=payload.subject,
            start_time=payload.start_datetime.isoformat(),
            end_time=payload.end_datetime.isoformat(),
            time_zone=payload.timezone,
            body=payload.body,
            location=payload.location,
            attendees=payload.attendees,
            is_online_meeting=payload.is_online_meeting
        )
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.patch("/{event_id}")
async def update_event(
    event_id: str,
    payload: UpdateEventPayload,
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    
    # Build payload dynamically
    update_data = {}
    if payload.subject is not None:
        update_data["subject"] = payload.subject
    if payload.body is not None:
        update_data["body"] = {"contentType": "HTML", "content": payload.body}
    if payload.location is not None:
        update_data["location"] = {"displayName": payload.location}
    if payload.attendees is not None:
        update_data["attendees"] = [{"emailAddress": {"address": a}, "type": "required"} for a in payload.attendees]
        
    # Start/End times
    if payload.start_datetime is not None:
        update_data["start"] = {"dateTime": payload.start_datetime.isoformat(), "timeZone": payload.timezone or "UTC"}
    if payload.end_datetime is not None:
        update_data["end"] = {"dateTime": payload.end_datetime.isoformat(), "timeZone": payload.timezone or "UTC"}

    try:
        return client.update_event(event_id, update_data)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        client.delete_event(event_id)
        return {"status": "success", "message": "Event deleted"}
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
