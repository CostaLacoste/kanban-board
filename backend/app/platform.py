from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .auth import hash_password, verify_password
from .config import Settings
from .database import Database
from .models import utc_now
from .repository import Repository


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _totp(secret: str, moment: int | None = None) -> str:
    counter = int((moment or int(time.time())) / 30)
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str) -> bool:
    now = int(time.time())
    return any(hmac.compare_digest(_totp(secret, now + drift * 30), code) for drift in (-1, 0, 1))


class PlatformService:
    def __init__(self, database: Database, repository: Repository, settings: Settings) -> None:
        self.database = database
        self.repository = repository
        self.settings = settings

    @staticmethod
    def _slug(name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
        return f"{base}-{secrets.token_hex(3)}"

    def ensure_workspace(self, user_id: str, name: str = "My workspace") -> str:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT workspace_id FROM workspace_user_roles WHERE user_id=? ORDER BY created_at LIMIT 1",
                (user_id,),
            ).fetchone()
            if row:
                return row["workspace_id"]
        return self.create_workspace(user_id, name)["id"]

    def create_workspace(self, user_id: str, name: str) -> dict[str, Any]:
        workspace_id = str(uuid4())
        created_at = utc_now()
        snapshot = self.repository.get_workspace()
        snapshot["revision"] = 0
        snapshot["activeBoardId"] = "default"
        snapshot["boards"] = [{
            "id": "default", "name": "Основная доска", "createdAt": created_at,
        }]
        snapshot["tasks"] = []
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO workspaces(id,name,slug,created_by,created_at) VALUES (?,?,?,?,?)",
                (workspace_id, name, self._slug(name), user_id, created_at),
            )
            connection.execute(
                "INSERT INTO workspace_user_roles(workspace_id,user_id,role,created_at) VALUES (?,?,?,?)",
                (workspace_id, user_id, "owner", created_at),
            )
            connection.execute(
                "INSERT INTO workspace_snapshots(workspace_id,revision,payload,updated_at) VALUES (?,?,?,?)",
                (workspace_id, 0, json.dumps(snapshot, ensure_ascii=False), created_at),
            )
            row = connection.execute("SELECT slug FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        return {"id": workspace_id, "name": name, "slug": row["slug"], "role": "owner", "createdAt": created_at}

    def workspace_role(self, workspace_id: str, user_id: str) -> str | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT role FROM workspace_user_roles WHERE workspace_id=? AND user_id=?",
                (workspace_id, user_id),
            ).fetchone()
        return row["role"] if row else None

    def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        self.ensure_workspace(user_id)
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT w.*,r.role FROM workspaces w JOIN workspace_user_roles r ON r.workspace_id=w.id "
                "WHERE r.user_id=? ORDER BY w.created_at", (user_id,),
            ).fetchall()
        return [{"id": r["id"], "name": r["name"], "slug": r["slug"], "role": r["role"], "createdAt": r["created_at"]} for r in rows]

    def set_member(self, workspace_id: str, email: str, role: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            user = connection.execute("SELECT id,name,email FROM users WHERE email=?", (email,)).fetchone()
            if user is None:
                return None
            connection.execute(
                "INSERT INTO workspace_user_roles(workspace_id,user_id,role,created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=excluded.role",
                (workspace_id, user["id"], role, utc_now()),
            )
        return {"id": user["id"], "name": user["name"], "email": user["email"], "role": role}

    def set_board_permission(self, workspace_id: str, board_id: str, user_id: str, role: str) -> dict[str, str]:
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO board_permissions(workspace_id,board_id,user_id,role) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id,board_id,user_id) DO UPDATE SET role=excluded.role",
                (workspace_id, board_id, user_id, role),
            )
        return {"workspaceId": workspace_id, "boardId": board_id, "userId": user_id, "role": role}

    def permitted_boards(self, workspace_id: str, user_id: str) -> set[str]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT board_id FROM board_permissions WHERE workspace_id=? AND user_id=?",
                (workspace_id, user_id),
            ).fetchall()
        return {row["board_id"] for row in rows}

    def filter_snapshot(self, workspace_id: str, user_id: str, role: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        if role == "owner":
            return snapshot
        permitted = self.permitted_boards(workspace_id, user_id)
        if not permitted:
            return snapshot
        result = {**snapshot}
        result["boards"] = [board for board in snapshot.get("boards", []) if board.get("id") in permitted]
        result["tasks"] = [task for task in snapshot.get("tasks", []) if task.get("boardId") in permitted]
        if result.get("activeBoardId") not in permitted:
            result["activeBoardId"] = next(iter(permitted), "default")
        return result

    def get_snapshot(self, workspace_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM workspace_snapshots WHERE workspace_id=?", (workspace_id,)).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["revision"] = row["revision"]
        return payload

    def save_snapshot(self, workspace_id: str, payload: dict[str, Any], expected: int | None) -> dict[str, Any]:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT revision FROM workspace_snapshots WHERE workspace_id=?", (workspace_id,)).fetchone()
            if row is None:
                raise KeyError(workspace_id)
            current = int(row["revision"])
            if expected is not None and current != expected:
                raise RuntimeError(f"revision:{current}")
            revision = current + 1
            snapshot = {**payload, "revision": revision}
            connection.execute(
                "UPDATE workspace_snapshots SET revision=?,payload=?,updated_at=? WHERE workspace_id=?",
                (revision, json.dumps(snapshot, ensure_ascii=False), utc_now(), workspace_id),
            )
        return snapshot

    def my_tasks(self, user_id: str, name: str, email: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for workspace in self.list_workspaces(user_id):
            snapshot = self.get_snapshot(workspace["id"]) or {}
            for task in snapshot.get("tasks") or []:
                if str(task.get("assignee") or "").lower() in {name.lower(), email.lower()}:
                    result.append({**task, "workspaceId": workspace["id"], "workspaceName": workspace["name"]})
        return sorted(result, key=lambda task: (task.get("deadline") or "9999", task.get("priority") != "high"))

    def audit(self, workspace_id: str | None, user_id: str | None, action: str, resource: str, request_id: str, ip: str, metadata: dict[str, Any] | None = None) -> None:
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO audit_logs(id,workspace_id,user_id,action,resource,request_id,ip_address,metadata,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid4()), workspace_id, user_id, action, resource, request_id, ip, json.dumps(metadata or {}), utc_now()),
            )

    def list_audit(self, workspace_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT a.*,u.name,u.email FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id "
                "WHERE a.workspace_id=? ORDER BY a.created_at DESC LIMIT ?",
                (workspace_id, limit),
            ).fetchall()
        return [{
            "id": r["id"], "workspaceId": r["workspace_id"], "userId": r["user_id"],
            "user": r["name"] or r["email"] or "System", "action": r["action"], "resource": r["resource"],
            "requestId": r["request_id"], "ipAddress": r["ip_address"],
            "metadata": json.loads(r["metadata"] or "{}"), "createdAt": r["created_at"],
        } for r in rows]

    def totp_setup(self, user_id: str, email: str) -> dict[str, str]:
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO user_security(user_id,totp_secret,totp_enabled) VALUES (?,?,0) "
                "ON CONFLICT(user_id) DO UPDATE SET totp_secret=excluded.totp_secret,totp_enabled=0",
                (user_id, secret),
            )
        label = email.replace(" ", "%20")
        return {"secret": secret, "uri": f"otpauth://totp/Flowboard:{label}?secret={secret}&issuer=Flowboard"}

    def totp_enable(self, user_id: str, code: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT totp_secret FROM user_security WHERE user_id=?", (user_id,)).fetchone()
            if not row or not row["totp_secret"] or not verify_totp(row["totp_secret"], code):
                return False
            connection.execute("UPDATE user_security SET totp_enabled=1 WHERE user_id=?", (user_id,))
        return True

    def create_email_verification(self, user_id: str) -> str:
        raw = secrets.token_urlsafe(32)
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO email_verifications(id,user_id,token_hash,expires_at,created_at) VALUES (?,?,?,?,?)",
                (str(uuid4()), user_id, _token_hash(raw), (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z"), utc_now()),
            )
        return raw

    def verify_email(self, token: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM email_verifications WHERE token_hash=? AND used_at IS NULL", (_token_hash(token),)).fetchone()
            if not row or datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return False
            now = utc_now()
            connection.execute("UPDATE email_verifications SET used_at=? WHERE id=?", (now, row["id"]))
            connection.execute(
                "INSERT INTO user_security(user_id,email_verified_at) VALUES (?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET email_verified_at=excluded.email_verified_at",
                (row["user_id"], now),
            )
        return True

    def security_status(self, user_id: str) -> dict[str, Any]:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM user_security WHERE user_id=?", (user_id,)).fetchone()
            passkeys = connection.execute("SELECT COUNT(*) AS count FROM webauthn_credentials WHERE user_id=?", (user_id,)).fetchone()["count"]
        return {"totpEnabled": bool(row and row["totp_enabled"]), "emailVerified": bool(row and row["email_verified_at"]), "passkeys": passkeys}

    def passkey_registration_start(self, user_id: str, email: str, name: str) -> dict[str, Any]:
        try:
            from webauthn import generate_registration_options, options_to_json
            from webauthn.helpers.structs import (
                AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement,
            )
        except ImportError as error:
            raise RuntimeError("WebAuthn support is not installed") from error
        options = generate_registration_options(
            rp_id=self.settings.webauthn_rp_id,
            rp_name="Flowboard",
            user_id=user_id.encode(),
            user_name=email,
            user_display_name=name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        challenge_id = str(uuid4())
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO webauthn_challenges(id,user_id,kind,challenge,expires_at,created_at) VALUES (?,?,?,?,?,?)",
                (challenge_id, user_id, "registration", options.challenge,
                 (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), utc_now()),
            )
        return {"challengeId": challenge_id, "publicKey": json.loads(options_to_json(options))}

    def passkey_registration_complete(self, user_id: str, challenge_id: str, credential: dict[str, Any], device_name: str) -> dict[str, Any]:
        try:
            from webauthn import verify_registration_response
            from webauthn.helpers import parse_registration_credential_json
        except ImportError as error:
            raise RuntimeError("WebAuthn support is not installed") from error
        with self.database._lock, self.database.connect() as connection:
            challenge = connection.execute(
                "SELECT * FROM webauthn_challenges WHERE id=? AND user_id=? AND kind='registration'",
                (challenge_id, user_id),
            ).fetchone()
        if not challenge or challenge["expires_at"] < utc_now():
            raise ValueError("Passkey challenge expired")
        result = verify_registration_response(
            credential=parse_registration_credential_json(credential),
            expected_challenge=bytes(challenge["challenge"]),
            expected_rp_id=self.settings.webauthn_rp_id,
            expected_origin=self.settings.webauthn_origin,
            require_user_verification=True,
        )
        item = {"id": str(uuid4()), "deviceName": device_name[:100], "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO webauthn_credentials(id,user_id,credential_id,public_key,sign_count,device_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (item["id"], user_id, result.credential_id, result.credential_public_key, result.sign_count, item["deviceName"], item["createdAt"]),
            )
            connection.execute("DELETE FROM webauthn_challenges WHERE id=?", (challenge_id,))
        return item

    def passkey_authentication_start(self, email: str) -> dict[str, Any] | None:
        try:
            from webauthn import generate_authentication_options, options_to_json
            from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
        except ImportError as error:
            raise RuntimeError("WebAuthn support is not installed") from error
        with self.database._lock, self.database.connect() as connection:
            user = connection.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not user:
                return None
            rows = connection.execute("SELECT credential_id FROM webauthn_credentials WHERE user_id=?", (user["id"],)).fetchall()
        if not rows:
            return None
        options = generate_authentication_options(
            rp_id=self.settings.webauthn_rp_id,
            allow_credentials=[PublicKeyCredentialDescriptor(id=bytes(row["credential_id"])) for row in rows],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        challenge_id = str(uuid4())
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO webauthn_challenges(id,user_id,email,kind,challenge,expires_at,created_at) VALUES (?,?,?,?,?,?,?)",
                (challenge_id, user["id"], email, "authentication", options.challenge,
                 (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), utc_now()),
            )
        return {"challengeId": challenge_id, "publicKey": json.loads(options_to_json(options))}

    def passkey_authentication_complete(self, challenge_id: str, credential: dict[str, Any]) -> str | None:
        try:
            from webauthn import verify_authentication_response
            from webauthn.helpers import parse_authentication_credential_json
        except ImportError as error:
            raise RuntimeError("WebAuthn support is not installed") from error
        parsed = parse_authentication_credential_json(credential)
        with self.database._lock, self.database.connect() as connection:
            challenge = connection.execute(
                "SELECT * FROM webauthn_challenges WHERE id=? AND kind='authentication'", (challenge_id,)
            ).fetchone()
            stored = connection.execute(
                "SELECT * FROM webauthn_credentials WHERE credential_id=?", (parsed.raw_id,)
            ).fetchone()
        if not challenge or not stored or challenge["expires_at"] < utc_now() or stored["user_id"] != challenge["user_id"]:
            return None
        result = verify_authentication_response(
            credential=parsed,
            expected_challenge=bytes(challenge["challenge"]),
            expected_rp_id=self.settings.webauthn_rp_id,
            expected_origin=self.settings.webauthn_origin,
            credential_public_key=bytes(stored["public_key"]),
            credential_current_sign_count=int(stored["sign_count"]),
            require_user_verification=True,
        )
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "UPDATE webauthn_credentials SET sign_count=?,last_used_at=? WHERE id=?",
                (result.new_sign_count, utc_now(), stored["id"]),
            )
            connection.execute("DELETE FROM webauthn_challenges WHERE id=?", (challenge_id,))
        return stored["user_id"]

    def register_push(self, user_id: str, endpoint: str, keys: dict[str, str]) -> dict[str, Any]:
        item = {"id": str(uuid4()), "endpoint": endpoint, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO push_subscriptions(id,user_id,endpoint,p256dh,auth,created_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,p256dh=excluded.p256dh,auth=excluded.auth",
                (item["id"], user_id, endpoint, keys.get("p256dh", ""), keys.get("auth", ""), item["createdAt"]),
            )
        return item

    def create_integration(self, workspace_id: str, kind: str, name: str, config: dict[str, Any]) -> dict[str, Any]:
        item = {"id": str(uuid4()), "workspaceId": workspace_id, "kind": kind, "name": name, "active": True, "secret": secrets.token_urlsafe(24), "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO integrations(id,workspace_id,kind,name,config,secret,created_at) VALUES (?,?,?,?,?,?,?)",
                (item["id"], workspace_id, kind, name, json.dumps(config), item["secret"], item["createdAt"]),
            )
        return item

    def list_integrations(self, workspace_id: str) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM integrations WHERE workspace_id=? ORDER BY created_at", (workspace_id,)).fetchall()
        return [{"id": r["id"], "workspaceId": r["workspace_id"], "kind": r["kind"], "name": r["name"], "config": json.loads(r["config"]), "active": bool(r["active"]), "createdAt": r["created_at"]} for r in rows]

    def integration(self, integration_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM integrations WHERE id=? AND active=1", (integration_id,)).fetchone()
        return dict(row) if row else None

    async def deliver_integration(self, integration: dict[str, Any], text: str) -> bool:
        config = json.loads(integration.get("config") or "{}")
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            if integration["kind"] == "slack" and config.get("webhookUrl"):
                response = await client.post(config["webhookUrl"], json={"text": text})
            elif integration["kind"] == "telegram" and config.get("botToken") and config.get("chatId"):
                response = await client.post(
                    f"https://api.telegram.org/bot{config['botToken']}/sendMessage",
                    json={"chat_id": config["chatId"], "text": text},
                )
            else:
                return False
            response.raise_for_status()
        return True

    def add_custom_field(self, workspace_id: str, name: str, field_type: str, options: list[str], required: bool) -> dict[str, Any]:
        item = {"id": str(uuid4()), "workspaceId": workspace_id, "name": name, "fieldType": field_type, "options": options, "required": required, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO custom_fields(id,workspace_id,name,field_type,options,required,created_at) VALUES (?,?,?,?,?,?,?)",
                (item["id"], workspace_id, name, field_type, json.dumps(options), int(required), item["createdAt"]),
            )
        return item

    def list_custom_fields(self, workspace_id: str) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM custom_fields WHERE workspace_id=? ORDER BY created_at", (workspace_id,)).fetchall()
        return [{"id": r["id"], "workspaceId": r["workspace_id"], "name": r["name"], "fieldType": r["field_type"], "options": json.loads(r["options"]), "required": bool(r["required"]), "createdAt": r["created_at"]} for r in rows]

    def create_share(self, workspace_id: str, board_id: str | None, mode: str, password: str | None, expires_at: str | None, user_id: str) -> dict[str, Any]:
        raw = secrets.token_urlsafe(32)
        item = {"id": str(uuid4()), "token": raw, "workspaceId": workspace_id, "boardId": board_id, "mode": mode, "expiresAt": expires_at, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO public_shares(id,workspace_id,token_hash,board_id,mode,password_hash,expires_at,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (item["id"], workspace_id, _token_hash(raw), board_id, mode, hash_password(password) if password else None, expires_at, user_id, item["createdAt"]),
            )
        return item

    def resolve_share(self, token: str, password: str | None = None) -> tuple[dict[str, Any], dict[str, Any]] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM public_shares WHERE token_hash=?", (_token_hash(token),)).fetchone()
        if not row or (row["expires_at"] and row["expires_at"] < utc_now()):
            return None
        if row["password_hash"] and (not password or not verify_password(password, row["password_hash"])):
            return None
        snapshot = self.get_snapshot(row["workspace_id"]) or {}
        if row["board_id"]:
            snapshot["boards"] = [board for board in snapshot.get("boards", []) if board.get("id") == row["board_id"]]
            snapshot["tasks"] = [task for task in snapshot.get("tasks", []) if task.get("boardId") == row["board_id"]]
        return dict(row), snapshot

    def public_form_submit(self, share: dict[str, Any], title: str, description: str, values: dict[str, Any]) -> dict[str, Any]:
        snapshot = self.get_snapshot(share["workspace_id"]) or {}
        task = {
            "id": str(uuid4()), "title": title, "description": description, "status": "todo", "priority": "low",
            "deadline": "", "boardId": share["board_id"] or "default", "order": len(snapshot.get("tasks", [])),
            "archived": False, "recurrence": "none", "tags": ["form"], "checklist": [], "dependsOn": [],
            "assignee": "", "color": "default", "cover": "", "comments": [], "estimatedMinutes": 0,
            "timeSpentSeconds": 0, "timerStartedAt": "", "startDate": "", "goalId": "", "milestone": False,
            "customValues": values, "createdAt": utc_now(), "completedAt": "",
        }
        snapshot.setdefault("tasks", []).append(task)
        self.save_snapshot(share["workspace_id"], snapshot, snapshot.get("revision"))
        return task

    def add_operation(self, workspace_id: str | None, task_id: str, client_id: str, user_id: str | None, field: str, operation: dict[str, Any], lamport: int) -> dict[str, Any]:
        item = {"id": str(uuid4()), "workspaceId": workspace_id, "taskId": task_id, "clientId": client_id, "userId": user_id, "field": field, "operation": operation, "lamport": lamport, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO collaboration_operations(id,workspace_id,task_id,client_id,user_id,field,operation,lamport,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (item["id"], workspace_id, task_id, client_id, user_id, field, json.dumps(operation, ensure_ascii=False), lamport, item["createdAt"]),
            )
        return item

    def list_operations(self, task_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM collaboration_operations WHERE task_id=? AND lamport>? ORDER BY lamport,created_at LIMIT 1000", (task_id, after)).fetchall()
        return [{"id": r["id"], "workspaceId": r["workspace_id"], "taskId": r["task_id"], "clientId": r["client_id"], "userId": r["user_id"], "field": r["field"], "operation": json.loads(r["operation"]), "lamport": r["lamport"], "createdAt": r["created_at"]} for r in rows]

    def assistant(self, action: str, text: str, task: dict[str, Any] | None, workspace_id: str | None) -> dict[str, Any]:
        source = (text or (task or {}).get("description") or (task or {}).get("title") or "").strip()
        if action == "checklist":
            fragments = [part.strip(" .-\n") for part in re.split(r"[.!?;\n]+", source) if part.strip()]
            generic = ["Уточнить результат", "Разбить работу на шаги", "Проверить готовность"]
            items = (fragments if len(fragments) >= 2 else generic)[:8]
            return {"action": action, "checklist": [{"text": item[:100], "done": False} for item in items]}
        if action == "summary":
            lines = [line.strip() for line in source.splitlines() if line.strip()]
            return {"action": action, "summary": " ".join(lines[:5])[:600], "messages": len(lines)}
        snapshot = self.get_snapshot(workspace_id) if workspace_id else self.repository.get_workspace()
        tasks = (snapshot or {}).get("tasks", [])
        if action == "capacity":
            load: dict[str, int] = {}
            for item in tasks:
                if item.get("status") != "done":
                    load[item.get("assignee") or "Unassigned"] = load.get(item.get("assignee") or "Unassigned", 0) + int(item.get("estimatedMinutes") or 0)
            return {"action": action, "capacity": [{"assignee": key, "minutes": value} for key, value in sorted(load.items(), key=lambda pair: pair[1])]}
        scored = sorted(tasks, key=lambda item: (item.get("priority") != "high", item.get("deadline") or "9999"))
        return {"action": action, "tasks": [{"id": item.get("id"), "title": item.get("title"), "reason": "priority+deadline"} for item in scored[:10]]}

    def create_backup(self, workspace_id: str, user_id: str, name: str) -> dict[str, Any]:
        snapshot = self.get_snapshot(workspace_id)
        if snapshot is None:
            raise KeyError(workspace_id)
        item = {"id": str(uuid4()), "workspaceId": workspace_id, "name": name, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_backups(id,workspace_id,name,payload,created_by,created_at) VALUES (?,?,?,?,?,?)",
                (item["id"], workspace_id, name, json.dumps(snapshot, ensure_ascii=False), user_id, item["createdAt"]),
            )
        return item

    def list_backups(self, workspace_id: str) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id,workspace_id,name,created_at FROM workspace_backups WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100",
                (workspace_id,),
            ).fetchall()
        return [{"id": row["id"], "workspaceId": row["workspace_id"], "name": row["name"], "createdAt": row["created_at"]} for row in rows]

    def get_backup(self, workspace_id: str, backup_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM workspace_backups WHERE id=? AND workspace_id=?", (backup_id, workspace_id)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def restore_backup(self, workspace_id: str, backup_id: str) -> dict[str, Any] | None:
        payload = self.get_backup(workspace_id, backup_id)
        if payload is None:
            return None
        current = self.get_snapshot(workspace_id)
        return self.save_snapshot(workspace_id, payload, current.get("revision") if current else None)

    def list_automation_rules(self, workspace_id: str) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM automation_rules WHERE workspace_id=? ORDER BY created_at", (workspace_id,)
            ).fetchall()
        return [{"id": row["id"], "workspaceId": row["workspace_id"], "name": row["name"],
                 "trigger": row["trigger_name"], "triggerValue": row["trigger_value"],
                 "action": row["action_name"], "actionValue": row["action_value"],
                 "active": bool(row["active"]), "createdAt": row["created_at"]} for row in rows]

    def create_automation_rule(self, workspace_id: str, data: Any) -> dict[str, Any]:
        item = {"id": str(uuid4()), "workspaceId": workspace_id, "name": data.name,
                "trigger": data.trigger, "triggerValue": data.trigger_value, "action": data.action,
                "actionValue": data.action_value, "active": data.active, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO automation_rules(id,workspace_id,name,trigger_name,trigger_value,action_name,action_value,active,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (item["id"], workspace_id, item["name"], item["trigger"], item["triggerValue"], item["action"], item["actionValue"], int(item["active"]), item["createdAt"]),
            )
        return item

    def delete_automation_rule(self, workspace_id: str, rule_id: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            return connection.execute("DELETE FROM automation_rules WHERE id=? AND workspace_id=?", (rule_id, workspace_id)).rowcount > 0

    def notification_schedule(self, user_id: str) -> dict[str, Any]:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM notification_schedules WHERE user_id=?", (user_id,)).fetchone()
        return {"leadMinutes": row["lead_minutes"], "digestFrequency": row["digest_frequency"],
                "digestHour": row["digest_hour"], "timezone": row["timezone"]} if row else {
            "leadMinutes": 60, "digestFrequency": "daily", "digestHour": 9, "timezone": "UTC",
        }

    def set_notification_schedule(self, user_id: str, data: Any) -> dict[str, Any]:
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO notification_schedules(user_id,lead_minutes,digest_frequency,digest_hour,timezone,updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET lead_minutes=excluded.lead_minutes,digest_frequency=excluded.digest_frequency,digest_hour=excluded.digest_hour,timezone=excluded.timezone,updated_at=excluded.updated_at",
                (user_id, data.lead_minutes, data.digest_frequency, data.digest_hour, data.timezone, utc_now()),
            )
        return self.notification_schedule(user_id)

    def oauth_start(self, provider: str) -> str:
        providers = {
            "google": (self.settings.oauth_google_client_id, "https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
            "github": (self.settings.oauth_github_client_id, "https://github.com/login/oauth/authorize", "read:user user:email"),
            "microsoft": (self.settings.oauth_microsoft_client_id, "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "openid email profile User.Read"),
        }
        if provider not in providers or not providers[provider][0]:
            raise RuntimeError("OAuth provider is not configured")
        client_id, authorize_url, scope = providers[provider]
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        redirect_uri = f"{self.settings.api_public_url}/auth/oauth/{provider}/callback"
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO oauth_states(id,provider,state_hash,code_verifier,redirect_uri,expires_at,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()), provider, _token_hash(state), verifier, redirect_uri,
                 (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"), utc_now()),
            )
        return f"{authorize_url}?{urlencode({'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code', 'scope': scope, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256'})}"

    def run_scheduled_notifications(self) -> int:
        now = datetime.now(timezone.utc)
        delivered = 0
        with self.database._lock, self.database.connect() as connection:
            schedules = connection.execute(
                "SELECT s.*,u.email,u.name FROM notification_schedules s JOIN users u ON u.id=s.user_id"
            ).fetchall()
            for schedule in schedules:
                try:
                    zone = ZoneInfo(schedule["timezone"])
                except ZoneInfoNotFoundError:
                    zone = timezone.utc
                local_now = now.astimezone(zone)
                workspaces = connection.execute(
                    "SELECT workspace_id FROM workspace_user_roles WHERE user_id=?", (schedule["user_id"],)
                ).fetchall()
                open_tasks: list[dict[str, Any]] = []
                for workspace in workspaces:
                    snapshot = self.get_snapshot(workspace["workspace_id"]) or {}
                    open_tasks.extend(task for task in snapshot.get("tasks", []) if task.get("status") != "done"
                                      and str(task.get("assignee") or "").lower() in {schedule["email"].lower(), schedule["name"].lower()})
                for task in open_tasks:
                    try:
                        deadline = datetime.fromisoformat(f"{task.get('deadline')}T23:59:59").replace(tzinfo=zone)
                    except (TypeError, ValueError):
                        continue
                    if not 0 <= (deadline - local_now).total_seconds() <= int(schedule["lead_minutes"]) * 60:
                        continue
                    key_date = str(task.get("deadline"))
                    exists = connection.execute(
                        "SELECT 1 FROM scheduled_notification_deliveries WHERE user_id=? AND task_id=? AND kind=? AND scheduled_for=?",
                        (schedule["user_id"], task.get("id"), "deadline", key_date),
                    ).fetchone()
                    if exists:
                        continue
                    connection.execute(
                        "INSERT INTO scheduled_notification_deliveries(id,user_id,task_id,kind,scheduled_for,delivered_at) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), schedule["user_id"], task.get("id"), "deadline", key_date, utc_now()),
                    )
                    connection.execute(
                        "INSERT INTO notifications(id,user_id,kind,title,body,created_at) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), schedule["user_id"], "deadline", "Task deadline", str(task.get("title") or "Task"), utc_now()),
                    )
                    connection.execute(
                        "INSERT INTO jobs(id,kind,payload,status,available_at,created_at) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), "push.send", json.dumps({"userId": schedule["user_id"], "title": "Flowboard", "body": f"Due soon: {task.get('title')}"}), "pending", utc_now(), utc_now()),
                    )
                    delivered += 1
                frequency = schedule["digest_frequency"]
                last = datetime.fromisoformat(schedule["last_digest_at"].replace("Z", "+00:00")) if schedule["last_digest_at"] else None
                due_digest = frequency != "off" and local_now.hour >= schedule["digest_hour"] and (
                    not last or (frequency == "daily" and last.astimezone(zone).date() < local_now.date()) or (frequency == "weekly" and (now - last).days >= 7)
                )
                if due_digest:
                    body = f"{len(open_tasks)} open tasks in your workspaces"
                    connection.execute(
                        "INSERT INTO notifications(id,user_id,kind,title,body,created_at) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), schedule["user_id"], "digest", "Flowboard digest", body, utc_now()),
                    )
                    connection.execute("UPDATE notification_schedules SET last_digest_at=? WHERE user_id=?", (utc_now(), schedule["user_id"]))
                    connection.execute(
                        "INSERT INTO jobs(id,kind,payload,status,available_at,created_at) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), "push.send", json.dumps({"userId": schedule["user_id"], "title": "Flowboard digest", "body": body}), "pending", utc_now(), utc_now()),
                    )
                    delivered += 1
        return delivered

    async def oauth_profile(self, provider: str, state: str, code: str) -> dict[str, str]:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM oauth_states WHERE provider=? AND state_hash=?", (provider, _token_hash(state))
            ).fetchone()
            if not row or row["expires_at"] < utc_now():
                raise ValueError("OAuth state is invalid or expired")
            connection.execute("DELETE FROM oauth_states WHERE id=?", (row["id"],))
        provider_config = {
            "google": (self.settings.oauth_google_client_id, self.settings.oauth_google_client_secret, "https://oauth2.googleapis.com/token", "https://openidconnect.googleapis.com/v1/userinfo"),
            "github": (self.settings.oauth_github_client_id, self.settings.oauth_github_client_secret, "https://github.com/login/oauth/access_token", "https://api.github.com/user"),
            "microsoft": (self.settings.oauth_microsoft_client_id, self.settings.oauth_microsoft_client_secret, "https://login.microsoftonline.com/common/oauth2/v2.0/token", "https://graph.microsoft.com/v1.0/me"),
        }
        client_id, secret, token_url, profile_url = provider_config[provider]
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            token_response = await client.post(token_url, data={"client_id": client_id, "client_secret": secret,
                "code": code, "grant_type": "authorization_code", "redirect_uri": row["redirect_uri"],
                "code_verifier": row["code_verifier"]}, headers={"Accept": "application/json"})
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            profile_response = await client.get(profile_url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
            profile_response.raise_for_status()
            profile = profile_response.json()
            email = profile.get("email") or profile.get("mail") or profile.get("userPrincipalName")
            if provider == "github" and not email:
                emails = await client.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"})
                emails.raise_for_status()
                email = next((item["email"] for item in emails.json() if item.get("primary") and item.get("verified")), None)
        if not access_token or not email:
            raise ValueError("OAuth provider did not return a verified email")
        return {"providerUserId": str(profile.get("sub") or profile.get("id")), "email": email,
                "name": str(profile.get("name") or profile.get("login") or email.split("@", 1)[0])}
