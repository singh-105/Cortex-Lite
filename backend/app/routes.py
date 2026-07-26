from fastapi import APIRouter, Depends
from app.router_logic import (
    should_escalate, handle_locally, handle_via_api,
    is_tool_query, handle_tool_query, log_call, get_history, delete_entry, upsert_user
)
from app.auth import verify_google_token, create_session_token, get_current_user

router = APIRouter()

@router.post("/auth/google")
def google_login(payload: dict):
    token = payload["token"]
    user = verify_google_token(token)
    upsert_user(user["sub"], user["email"], user["name"], user["picture"])
    session_token = create_session_token(user["sub"], user["email"])
    return {"token": session_token, "user": user}

@router.post("/route-task")
def route_task(payload: dict, user_id: str = Depends(get_current_user)):
    query = payload["query"]

    if is_tool_query(query):
        answer = handle_tool_query(query)
        used = "tool"
    elif should_escalate(query):
        answer = handle_via_api(query, user_id)
        used = "api"
    else:
        answer = handle_locally(query, user_id)
        used = "local"

    log_call(user_id, query, used, answer)
    return {"answer": answer, "used": used}

@router.get("/history")
def history(user_id: str = Depends(get_current_user)):
    return get_history(user_id)

@router.delete("/history/{entry_id}")
def delete_history(entry_id: int, user_id: str = Depends(get_current_user)):
    delete_entry(entry_id, user_id)
    return {"deleted": entry_id}