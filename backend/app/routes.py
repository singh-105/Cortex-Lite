from fastapi import APIRouter
from app.router_logic import should_escalate, handle_locally

router = APIRouter()

@router.post("/route-task")
def route_task(payload: dict):
    query = payload["query"]
    if should_escalate(query):
        return {"answer": "would call API here", "used": "api"}
    return {"answer": handle_locally(query), "used": "local"}