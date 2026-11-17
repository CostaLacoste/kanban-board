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
