from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .config import Settings
from .database import Database
from .models import InvitationAccept, LoginRequest, RegisterRequest, utc_now


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


def verify_totp_code(secret: str, code: str) -> bool:
    try:
        key = base64.b32decode(secret + "=" * (-len(secret) % 8))
        for drift in (-1, 0, 1):
            counter = int(time.time() / 30) + drift
            digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
            offset = digest[-1] & 0x0F
            value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
            if hmac.compare_digest(f"{value:06d}", code):
                return True
    except (ValueError, TypeError):
        return False
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

    def issue_token(self, user_id: str, user_agent: str = "unknown", ip_address: str = "unknown") -> str:
        session_id = str(uuid4())
        now = utc_now()
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO auth_sessions(id,user_id,user_agent,ip_address,created_at,last_seen_at) VALUES (?,?,?,?,?,?)",
                (session_id, user_id, user_agent[:300], ip_address[:100], now, now),
            )
        header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.settings.access_token_minutes)
        payload = _b64(json.dumps({"sub": user_id, "sid": session_id, "exp": int(expires.timestamp())}, separators=(",", ":")).encode())
        signing_input = f"{header}.{payload}".encode()
        return f"{header}.{payload}.{self._sign(signing_input)}"

    def decode_token(self, token: str) -> tuple[str, str] | None:
        try:
            header, payload, signature = token.split(".", 2)
            signing_input = f"{header}.{payload}".encode()
            if not hmac.compare_digest(self._sign(signing_input), signature):
                return None
            claims: dict[str, Any] = json.loads(_unb64(payload))
            if int(claims["exp"]) < int(datetime.now(timezone.utc).timestamp()):
                return None
            return str(claims["sub"]), str(claims.get("sid") or "")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def register(
        self, data: RegisterRequest, user_agent: str = "unknown", ip_address: str = "unknown"
    ) -> tuple[dict[str, Any], str] | None:
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
        return self.get_user(user_id), self.issue_token(user_id, user_agent, ip_address)

    def login(
        self, data: LoginRequest, user_agent: str = "unknown", ip_address: str = "unknown"
    ) -> tuple[dict[str, Any], str] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT u.*, m.role FROM users u JOIN workspace_members m ON m.user_id = u.id WHERE u.email = ?",
                (data.email,),
            ).fetchone()
        if row is None or not verify_password(data.password, row["password_hash"]):
            return None
        with self.database._lock, self.database.connect() as connection:
            security = connection.execute(
                "SELECT totp_secret,totp_enabled FROM user_security WHERE user_id=?", (row["id"],)
            ).fetchone()
        if security and security["totp_enabled"] and (
            not data.otp or not verify_totp_code(security["totp_secret"], data.otp)
        ):
            return None
        return self._user_dict(row), self.issue_token(row["id"], user_agent, ip_address)

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
            decoded = self.decode_token(token)
            user_id, session_id = decoded if decoded else (None, None)
            user = self.get_user(user_id) if user_id else None
            if user and session_id:
                with self.database._lock, self.database.connect() as connection:
                    session = connection.execute(
                        "SELECT revoked_at FROM auth_sessions WHERE id=? AND user_id=?",
                        (session_id, user_id),
                    ).fetchone()
                    if session is None or session["revoked_at"]:
                        user = None
                    else:
                        connection.execute(
                            "UPDATE auth_sessions SET last_seen_at=? WHERE id=?", (utc_now(), session_id)
                        )
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

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_invitation(self, email: str, role: str, actor_id: str) -> dict[str, Any]:
        raw = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        item = {
            "id": str(uuid4()), "email": email.lower().strip(), "role": role, "token": raw,
            "expiresAt": (now + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
            "acceptedAt": None, "createdAt": utc_now(),
        }
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO invitations(id,email,role,token_hash,expires_at,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                (item["id"], item["email"], role, self._hash_token(raw), item["expiresAt"], actor_id, item["createdAt"]),
            )
        return item

    def list_invitations(self) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id,email,role,expires_at,accepted_at,created_at FROM invitations ORDER BY created_at DESC"
            ).fetchall()
        return [{
            "id": row["id"], "email": row["email"], "role": row["role"], "token": None,
            "expiresAt": row["expires_at"], "acceptedAt": row["accepted_at"], "createdAt": row["created_at"],
        } for row in rows]

    def accept_invitation(
        self, data: InvitationAccept, user_agent: str = "unknown", ip_address: str = "unknown"
    ) -> tuple[dict[str, Any], str] | None:
        now = datetime.now(timezone.utc)
        with self.database._lock, self.database.connect() as connection:
            invitation = connection.execute(
                "SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL",
                (self._hash_token(data.token),),
            ).fetchone()
            if invitation is None:
                return None
            expires = datetime.fromisoformat(invitation["expires_at"].replace("Z", "+00:00"))
            if expires < now or connection.execute("SELECT 1 FROM users WHERE email=?", (invitation["email"],)).fetchone():
                return None
            user_id = str(uuid4())
            created_at = utc_now()
            connection.execute(
                "INSERT INTO users(id,email,name,password_hash,created_at) VALUES (?,?,?,?,?)",
                (user_id, invitation["email"], data.name, hash_password(data.password), created_at),
            )
            connection.execute(
                "INSERT INTO workspace_members(user_id,role,created_at) VALUES (?,?,?)",
                (user_id, invitation["role"], created_at),
            )
            connection.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (created_at, invitation["id"]))
        return self.get_user(user_id), self.issue_token(user_id, user_agent, ip_address)

    def create_password_reset(self, email: str) -> tuple[str, str] | None:
        with self.database._lock, self.database.connect() as connection:
            user = connection.execute("SELECT id,email FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
            if user is None:
                return None
            raw = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO password_resets(id,user_id,token_hash,expires_at,created_at) VALUES (?,?,?,?,?)",
                (str(uuid4()), user["id"], self._hash_token(raw),
                 (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), utc_now()),
            )
        return user["email"], raw

    def reset_password(self, token: str, password: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM password_resets WHERE token_hash=? AND used_at IS NULL", (self._hash_token(token),)
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return False
            now = utc_now()
            connection.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["user_id"]))
            connection.execute("UPDATE password_resets SET used_at=? WHERE id=?", (now, row["id"]))
            connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=?", (now, row["user_id"]))
        return True

    def list_sessions(self, user_id: str, current_id: str = "") -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM auth_sessions WHERE user_id=? AND revoked_at IS NULL ORDER BY last_seen_at DESC", (user_id,)
            ).fetchall()
        return [{
            "id": row["id"], "userAgent": row["user_agent"], "ipAddress": row["ip_address"],
            "createdAt": row["created_at"], "lastSeenAt": row["last_seen_at"], "current": row["id"] == current_id,
        } for row in rows]

    def revoke_session(self, user_id: str, session_id: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            return connection.execute(
                "UPDATE auth_sessions SET revoked_at=? WHERE id=? AND user_id=? AND revoked_at IS NULL",
                (utc_now(), session_id, user_id),
            ).rowcount > 0

    def token_session_id(self, token: str | None) -> str:
        decoded = self.decode_token(token or "") if token else None
        return decoded[1] if decoded else ""
