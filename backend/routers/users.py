from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import hash_password, require_admin, verify_auth
from database import get_db

router = APIRouter(prefix="/api/users")


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=80)
    role: str = Field(default="member", pattern="^(admin|member)$")


@router.get("/me")
def current_user(user: dict = Depends(verify_auth)):
    return user


@router.get("", dependencies=[Depends(require_admin)])
def list_users():
    db = get_db()
    try:
        rows = db.execute(
            """SELECT id, username, display_name, role, active, created_at
               FROM users ORDER BY username"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def create_user(user: UserCreate):
    db = get_db()
    try:
        try:
            cur = db.execute(
                """INSERT INTO users (username, display_name, password_hash, role, active)
                   VALUES (?, ?, ?, ?, 1)""",
                (
                    user.username.strip(),
                    user.display_name.strip() if user.display_name else None,
                    hash_password(user.password),
                    user.role,
                ),
            )
            db.commit()
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(status_code=409, detail="Username already exists") from exc
            raise
        row = db.execute(
            """SELECT id, username, display_name, role, active, created_at
               FROM users WHERE id = ?""",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)
    finally:
        db.close()
