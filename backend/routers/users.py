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


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=40)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=80)
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    active: bool | None = None


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


@router.put("/{user_id}", dependencies=[Depends(require_admin)])
def update_user(user_id: int, user: UserUpdate):
    db = get_db()
    try:
        current = db.execute(
            "SELECT id, username, display_name, role, active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="User not found")

        updates = []
        values = []
        if user.username is not None:
            updates.append("username = ?")
            values.append(user.username.strip())
        if user.display_name is not None:
            updates.append("display_name = ?")
            values.append(user.display_name.strip() if user.display_name else None)
        if user.role is not None:
            updates.append("role = ?")
            values.append(user.role)
        if user.active is not None:
            updates.append("active = ?")
            values.append(1 if user.active else 0)
        if user.password:
            updates.append("password_hash = ?")
            values.append(hash_password(user.password))
        if updates:
            values.append(user_id)
            try:
                db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", values)
                db.commit()
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    raise HTTPException(status_code=409, detail="Username already exists") from exc
                raise

        row = db.execute(
            """SELECT id, username, display_name, role, active, created_at
               FROM users WHERE id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row)
    finally:
        db.close()
