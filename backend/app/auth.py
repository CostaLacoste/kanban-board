from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .config import Settings
from .database import Database
from .models import LoginRequest, RegisterRequest, utc_now


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, expected = encoded.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(rounds))
        return hmac.compare_digest(_b64(digest), expected)
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class Actor:
    id: str
    email: str
    name: str
    role: str
    authenticated: bool = True

    @classmethod
    def guest(cls) -> "Actor":
        return cls(id="local", email="local@flowboard", name="Local user", role="owner", authenticated=False)


class AuthService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    def _sign(self, signing_input: bytes) -> str:
        return _b64(hmac.new(self.settings.auth_secret.encode(), signing_input, hashlib.sha256).digest())

    def issue_token(self, user_id: str) -> str:
        header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.settings.access_token_minutes)
        payload = _b64(json.dumps({"sub": user_id, "exp": int(expires.timestamp())}, separators=(",", ":")).encode())
        signing_input = f"{header}.{payload}".encode()
        return f"{header}.{payload}.{self._sign(signing_input)}"

    def decode_token(self, token: str) -> str | None:
        try:
            header, payload, signature = token.split(".", 2)
            signing_input = f"{header}.{payload}".encode()
            if not hmac.compare_digest(self._sign(signing_input), signature):
                return None
            claims: dict[str, Any] = json.loads(_unb64(payload))
            if int(claims["exp"]) < int(datetime.now(timezone.utc).timestamp()):
                return None
            return str(claims["sub"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def register(self, data: RegisterRequest) -> tuple[dict[str, Any], str] | None:
        with self.database._lock, self.database.connect() as connection:
            if connection.execute("SELECT 1 FROM users WHERE email = ?", (data.email,)).fetchone():
                return None
            user_id = str(uuid4())
            count = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            role = "owner" if count == 0 else "editor"
            created_at = utc_now()
            connection.execute(
                "INSERT INTO users(id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, data.email, data.name, hash_password(data.password), created_at),
            )
            connection.execute(
                "INSERT INTO workspace_members(user_id, role, created_at) VALUES (?, ?, ?)",
                (user_id, role, created_at),
            )
        return self.get_user(user_id), self.issue_token(user_id)

    def login(self, data: LoginRequest) -> tuple[dict[str, Any], str] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT u.*, m.role FROM users u JOIN workspace_members m ON m.user_id = u.id WHERE u.email = ?",
                (data.email,),
            ).fetchone()
        if row is None or not verify_password(data.password, row["password_hash"]):
            return None
        return self._user_dict(row), self.issue_token(row["id"])

    @staticmethod
    def _user_dict(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"], "email": row["email"], "name": row["name"],
            "role": row["role"], "createdAt": row["created_at"],
        }

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT u.*, m.role FROM users u JOIN workspace_members m ON m.user_id = u.id WHERE u.id = ?",
                (user_id,),
            ).fetchone()
        return self._user_dict(row) if row else None

    def authenticate(self, token: str | None) -> Actor | None:
        if not token:
            return None
        if token.startswith("fb_"):
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            with self.database._lock, self.database.connect() as connection:
                row = connection.execute(
                    "SELECT u.*, m.role FROM api_tokens t JOIN users u ON u.id=t.user_id "
                    "JOIN workspace_members m ON m.user_id=u.id WHERE t.token_hash = ?",
                    (token_hash,),
                ).fetchone()
                if row:
                    connection.execute("UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ?", (utc_now(), token_hash))
        else:
            user_id = self.decode_token(token)
            user = self.get_user(user_id) if user_id else None
            row = user
        if not row:
            return None
        return Actor(id=row["id"], email=row["email"], name=row["name"], role=row["role"])

    def create_api_token(self, user_id: str, name: str) -> dict[str, Any]:
        raw = f"fb_{secrets.token_urlsafe(32)}"
        item = {"id": str(uuid4()), "name": name, "token": raw, "createdAt": utc_now(), "lastUsedAt": None}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO api_tokens(id,user_id,name,token_hash,created_at) VALUES (?,?,?,?,?)",
                (item["id"], user_id, name, hashlib.sha256(raw.encode()).hexdigest(), item["createdAt"]),
            )
        return item

    def list_api_tokens(self, user_id: str) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id,name,created_at,last_used_at FROM api_tokens WHERE user_id=? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        return [{"id": r["id"], "name": r["name"], "token": None, "createdAt": r["created_at"], "lastUsedAt": r["last_used_at"]} for r in rows]

    def delete_api_token(self, user_id: str, token_id: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            return connection.execute("DELETE FROM api_tokens WHERE id=? AND user_id=?", (token_id, user_id)).rowcount > 0

    def list_members(self) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT u.*,m.role FROM users u JOIN workspace_members m ON m.user_id=u.id ORDER BY u.created_at"
            ).fetchall()
        return [self._user_dict(row) for row in rows]

    def update_member_role(self, email: str, role: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT id FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
            if row is None:
                return None
            connection.execute("UPDATE workspace_members SET role=? WHERE user_id=?", (role, row["id"]))
        return self.get_user(row["id"])
