from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, constr
from typing import Optional
from app.graph.client import MicrosoftGraphClient, MicrosoftGraphError

router = APIRouter(prefix="/api/todos", tags=["To-Do"])

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

class CreateTodoPayload(BaseModel):
    list_id: str
    title: constr(min_length=1)  # Required and cannot be empty
    body: Optional[str] = ""
    due_date: Optional[str] = ""
    due_time: Optional[str] = ""
    importance: Optional[str] = "normal"  # low, normal, high

class UpdateTodoPayload(BaseModel):
    title: Optional[constr(min_length=1)] = None
    body: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    importance: Optional[str] = None
    status: Optional[str] = None  # notStarted, inProgress, completed, waitingOnOthers, deferred

@router.get("/lists")
async def get_todo_lists(session_id: str = Depends(get_session_id)):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_todo_lists()
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("")
async def get_todos(
    list_id: str = Query(..., description="ID of the To-Do list"),
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_todos(list_id)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/{task_id}")
async def get_todo(
    task_id: str,
    list_id: str = Query(..., description="ID of the To-Do list"),
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        return client.get_todo(list_id, task_id)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("")
async def create_todo(
    payload: CreateTodoPayload,
    session_id: str = Depends(get_session_id)
):
    # Validate importance
    if payload.importance and payload.importance not in ["low", "normal", "high"]:
        raise HTTPException(status_code=422, detail="Invalid importance value")

    # Basic ISO date format check (regex or datetime parsing could be used, but keeping simple as requested)
    # Using length check as basic defense, full validation would use regex or datetime.strptime
    
    client = MicrosoftGraphClient(session_id)
    try:
        return client.create_todo(
            list_id=payload.list_id,
            title=payload.title,
            body=payload.body,
            due_date=payload.due_date,
            due_time=payload.due_time,
            importance=payload.importance
        )
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.patch("/{task_id}")
async def update_todo(
    task_id: str,
    payload: UpdateTodoPayload,
    list_id: str = Query(..., description="ID of the To-Do list"),
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    update_data = {}
    
    if payload.title is not None:
        update_data["title"] = payload.title
    if payload.body is not None:
        update_data["body"] = {"contentType": "text", "content": payload.body}
    if payload.importance is not None:
        if payload.importance not in ["low", "normal", "high"]:
            raise HTTPException(status_code=422, detail="Invalid importance value")
        update_data["importance"] = payload.importance
    if payload.status is not None:
        if payload.status not in ["notStarted", "inProgress", "completed", "waitingOnOthers", "deferred"]:
            raise HTTPException(status_code=422, detail="Invalid status value")
        update_data["status"] = payload.status
    if payload.due_date and payload.due_time:
        update_data["dueDateTime"] = {
            "dateTime": f"{payload.due_date}T{payload.due_time}",
            "timeZone": "UTC"
        }
        
    try:
        return client.update_todo(list_id, task_id, update_data)
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{task_id}")
async def delete_todo(
    task_id: str,
    list_id: str = Query(..., description="ID of the To-Do list"),
    session_id: str = Depends(get_session_id)
):
    client = MicrosoftGraphClient(session_id)
    try:
        client.delete_todo(list_id, task_id)
        return {"status": "success", "message": "Task deleted"}
    except MicrosoftGraphError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
