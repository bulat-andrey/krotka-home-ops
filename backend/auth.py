import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import HTTPException, Request

from database import get_db

AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "changeme")
DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def ensure_default_admin_user():
    db = get_db()
    try:
        row = db.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,)).fetchone()
        if row:
            return
        db.execute(
            """INSERT INTO users (username, display_name, password_hash, role, active)
               VALUES (?, ?, ?, 'admin', 1)""",
            (DEFAULT_ADMIN_USERNAME, "Admin", hash_password(AUTH_PASSWORD)),
        )
        db.commit()
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    db = get_db()
    try:
        row = db.execute(
            """SELECT id, username, display_name, password_hash, role, active
               FROM users WHERE username = ?""",
            (username,),
        ).fetchone()
        if not row or not row["active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
        }
    finally:
        db.close()


def verify_auth(request: Request):
    session = request.cookies.get("session")
    if session and ":" in session:
        username, password = session.split(":", 1)
        user = authenticate_user(username, password)
        if user:
            return user

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            username, password = decoded.split(":", 1)
            user = authenticate_user(username, password)
            if user:
                return user
        except Exception:
            pass
    raise HTTPException(status_code=401, detail="Unauthorized")


def require_admin(request: Request):
    user = verify_auth(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
