from fastapi import APIRouter
from app.router_logic import (
    should_escalate, handle_locally, handle_via_api,
    is_tool_query, handle_tool_query, log_call, get_history, delete_entry
)

router = APIRouter()

@router.post("/route-task")
def route_task(payload: dict):
    query = payload["query"]

    if is_tool_query(query):
        answer = handle_tool_query(query)
        used = "tool"
    elif should_escalate(query):
        answer = handle_via_api(query)
        used = "api"
    else:
        answer = handle_locally(query)
        used = "local"

    log_call(query, used, answer)
    return {"answer": answer, "used": used}

@router.get("/history")
def history():
    return get_history()

@router.delete("/history/{entry_id}")
def delete_history(entry_id: int):
    delete_entry(entry_id)
    return {"deleted": entry_id}