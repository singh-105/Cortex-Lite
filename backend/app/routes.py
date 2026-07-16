from fastapi import APIRouter
from app.router_logic import should_escalate, handle_locally, handle_via_api, log_call, get_history

router = APIRouter()

@router.post("/route-task")
def route_task(payload: dict):
    query = payload["query"]
    if should_escalate(query):
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