from __future__ import annotations

import hashlib
import hmac
import json
import smtplib
from asyncio import to_thread
from email.message import EmailMessage

import httpx

from .config import Settings
from .repository import Repository


async def deliver_outbox(repository: Repository, limit: int = 20) -> dict[str, int]:
    delivered = 0
    failed = 0
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
        for item in repository.pending_outbox(limit):
            body = json.dumps({"event": item["event"], "data": json.loads(item["payload"])}, ensure_ascii=False).encode()
            signature = hmac.new(item["secret"].encode(), body, hashlib.sha256).hexdigest()
            try:
                response = await client.post(
                    item["url"], content=body,
                    headers={"Content-Type": "application/json", "X-Flowboard-Signature": signature},
                )
                response.raise_for_status()
                repository.finish_outbox(item["id"])
                delivered += 1
            except Exception as error:
                repository.finish_outbox(item["id"], str(error))
                failed += 1
    return {"delivered": delivered, "failed": failed}


async def send_email(settings: Settings, recipient: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        return False


async def send_push(repository: Repository, settings: Settings, payload: dict) -> int:
    if not settings.vapid_private_key:
        return 0
    try:
        from pywebpush import webpush
    except ImportError as error:
        raise RuntimeError("Push support is not installed") from error
    with repository.database._lock, repository.database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM push_subscriptions WHERE user_id=?", (payload["userId"],)
        ).fetchall()

    def deliver(row) -> None:
        webpush(
            subscription_info={
                "endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
            },
            data=json.dumps({
                "title": payload.get("title", "Flowboard"),
                "body": payload.get("body", "You have a new notification"),
                "url": payload.get("url", "/"),
            }),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.smtp_from}"},
        )

    delivered = 0
    for row in rows:
        try:
            await to_thread(deliver, row)
            delivered += 1
        except Exception:
            continue
    return delivered

    def deliver() -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    try:
        await to_thread(deliver)
        return True
    except Exception:
        return False


async def process_jobs(repository: Repository, settings: Settings, limit: int = 10) -> dict[str, int]:
    completed = 0
    failed = 0
    for job in repository.claim_jobs(limit):
        try:
            if job["kind"] == "webhooks.deliver":
                result = await deliver_outbox(repository)
                if result["failed"]:
                    raise RuntimeError(f"{result['failed']} webhook deliveries failed")
            elif job["kind"] == "email.send":
                payload = job["payload"]
                delivered = await send_email(
                    settings, payload["recipient"], payload["subject"], payload["body"]
                )
                if settings.smtp_host and not delivered:
                    raise RuntimeError("Email delivery failed")
            elif job["kind"] == "push.send":
                await send_push(repository, settings, job["payload"])
            repository.finish_job(job["id"])
            completed += 1
        except Exception as error:
            repository.finish_job(job["id"], str(error))
            failed += 1
    return {"completed": completed, "failed": failed}
