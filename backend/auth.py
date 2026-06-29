import base64
import os
import secrets

from fastapi import HTTPException, Request

AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "changeme")


def verify_auth(request: Request):
    if request.cookies.get("session") == AUTH_PASSWORD:
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], AUTH_PASSWORD):
        return True
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            _, password = decoded.split(":", 1)
            if secrets.compare_digest(password, AUTH_PASSWORD):
                return True
        except Exception:
            pass
    raise HTTPException(status_code=401, detail="Unauthorized")
