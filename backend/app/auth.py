import os
import time
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import Header, HTTPException

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")

def verify_google_token(token: str):
    idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
    return {
        "sub": idinfo["sub"],
        "email": idinfo.get("email"),
        "name": idinfo.get("name"),
        "picture": idinfo.get("picture"),
    }

def create_session_token(user_id: str, email: str):
    payload = {"sub": user_id, "email": email, "exp": time.time() + 60 * 60 * 24 * 7}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")