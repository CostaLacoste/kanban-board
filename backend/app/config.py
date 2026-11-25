from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AUTH_SECRET = "flowboard-local-development-secret-change-me"


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    cors_origins: tuple[str, ...]
    database_url: str = ""
    max_attachment_size: int = 5 * 1024 * 1024
    max_attachments_per_task: int = 5
    auth_secret: str = DEFAULT_AUTH_SECRET
    auth_required: bool = False
    access_token_minutes: int = 60 * 24
    rate_limit_per_minute: int = 240
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "Flowboard <noreply@flowboard.local>"
    object_storage_path: Path | None = None
    public_app_url: str = "http://localhost:4173"
    webauthn_rp_id: str = "localhost"
    webauthn_origin: str = "http://localhost:4173"
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    api_public_url: str = "http://localhost:8000/api/v1"
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_microsoft_client_id: str = ""
    oauth_microsoft_client_secret: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        raw_origins = os.getenv(
            "FLOWBOARD_CORS_ORIGINS",
            "http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:8000,http://localhost:8000",
        )
        origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        database_path = Path(
            os.getenv("FLOWBOARD_DATABASE_PATH", BACKEND_DIR / "data" / "flowboard.db")
        ).expanduser()
        return cls(
            database_path=database_path,
            cors_origins=origins,
            database_url=os.getenv("DATABASE_URL", os.getenv("FLOWBOARD_DATABASE_URL", "")),
            auth_secret=os.getenv("FLOWBOARD_AUTH_SECRET", DEFAULT_AUTH_SECRET),
            auth_required=os.getenv("FLOWBOARD_AUTH_REQUIRED", "false").lower() == "true",
            access_token_minutes=int(os.getenv("FLOWBOARD_ACCESS_TOKEN_MINUTES", "1440")),
            rate_limit_per_minute=int(os.getenv("FLOWBOARD_RATE_LIMIT_PER_MINUTE", "240")),
            smtp_host=os.getenv("FLOWBOARD_SMTP_HOST", ""),
            smtp_port=int(os.getenv("FLOWBOARD_SMTP_PORT", "587")),
            smtp_username=os.getenv("FLOWBOARD_SMTP_USERNAME", ""),
            smtp_password=os.getenv("FLOWBOARD_SMTP_PASSWORD", ""),
            smtp_from=os.getenv("FLOWBOARD_SMTP_FROM", "Flowboard <noreply@flowboard.local>"),
            object_storage_path=(
                Path(os.environ["FLOWBOARD_OBJECT_STORAGE_PATH"]).expanduser()
                if os.getenv("FLOWBOARD_OBJECT_STORAGE_PATH") else None
            ),
            public_app_url=os.getenv("FLOWBOARD_PUBLIC_APP_URL", "http://localhost:4173").rstrip("/"),
            webauthn_rp_id=os.getenv("FLOWBOARD_WEBAUTHN_RP_ID", "localhost"),
            webauthn_origin=os.getenv("FLOWBOARD_WEBAUTHN_ORIGIN", os.getenv("FLOWBOARD_PUBLIC_APP_URL", "http://localhost:4173")).rstrip("/"),
            vapid_public_key=os.getenv("FLOWBOARD_VAPID_PUBLIC_KEY", ""),
            vapid_private_key=os.getenv("FLOWBOARD_VAPID_PRIVATE_KEY", ""),
            api_public_url=os.getenv("FLOWBOARD_API_PUBLIC_URL", "http://localhost:8000/api/v1").rstrip("/"),
            oauth_google_client_id=os.getenv("FLOWBOARD_GOOGLE_CLIENT_ID", ""),
            oauth_google_client_secret=os.getenv("FLOWBOARD_GOOGLE_CLIENT_SECRET", ""),
            oauth_github_client_id=os.getenv("FLOWBOARD_GITHUB_CLIENT_ID", ""),
            oauth_github_client_secret=os.getenv("FLOWBOARD_GITHUB_CLIENT_SECRET", ""),
            oauth_microsoft_client_id=os.getenv("FLOWBOARD_MICROSOFT_CLIENT_ID", ""),
            oauth_microsoft_client_secret=os.getenv("FLOWBOARD_MICROSOFT_CLIENT_SECRET", ""),
        )

