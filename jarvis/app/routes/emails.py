from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from app.graph.client import MicrosoftGraphClient, MicrosoftGraphError

router = APIRouter(prefix="/api/emails", tags=["Emails"])

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

class DraftEmailPayload(BaseModel):
    subject: str
    body: str
    to_recipients: List[EmailStr]
    cc_recipients: Optional[List[EmailStr]] = []
    bcc_recipients: Optional[List[EmailStr]] = []

class ReplyDraftPayload(BaseModel):
    body: str

@router.get("")
async def get_emails(
    top: int = 10, 
    skip: int = 0, 
    search: Optional[str] = None, 
    folder: str = "inbox",
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_messages(top=top, skip=skip, search=search, folder=folder)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/{message_id}")
async def get_email(
    message_id: str, 
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_message(message_id)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{message_id}")
async def delete_email(
    message_id: str,
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        client.delete_message(message_id)
        return {"status": "success", "message": "Email deleted successfully"}
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/draft")
async def create_draft(
    payload: DraftEmailPayload, 
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.create_draft(
            subject=payload.subject,
            content=payload.body,
            to_recipients=payload.to_recipients
            # Graph client currently only implemented for to_recipients to keep it simple, 
            # but we accept cc and bcc in the model for future extensions.
        )
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/{message_id}/reply-draft")
async def create_reply_draft(
    message_id: str,
    payload: ReplyDraftPayload,
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.create_reply_draft(message_id, payload.body)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
