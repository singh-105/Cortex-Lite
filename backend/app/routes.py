from fastapi import APIRouter, Depends
from app.router_logic import (
    should_escalate, handle_locally, handle_via_api, try_tool_call,
    log_call, get_history, delete_entry, upsert_user,
    get_usage, get_today_cloud_count, DAILY_CLOUD_LIMIT
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
    limit_hit = False

    tool_answer, tool_name = try_tool_call(query)
    if tool_answer is not None:
        answer, used = tool_answer, "tool"
    elif should_escalate(query):
        if get_today_cloud_count(user_id) >= DAILY_CLOUD_LIMIT:
            answer, used, limit_hit = handle_locally(query, user_id), "local", True
        else:
            answer, used = handle_via_api(query, user_id), "api"
    else:
        answer, used = handle_locally(query, user_id), "local"

    log_call(user_id, query, used, answer)
    return {"answer": answer, "used": used, "limit_hit": limit_hit, "usage": get_usage(user_id)}

@router.get("/usage")
def usage(user_id: str = Depends(get_current_user)):
    return get_usage(user_id)

@router.get("/history")
def history(user_id: str = Depends(get_current_user)):
    return get_history(user_id)

@router.delete("/history/{entry_id}")
def delete_history(entry_id: int, user_id: str = Depends(get_current_user)):
    delete_entry(entry_id, user_id)
    return {"deleted": entry_id}