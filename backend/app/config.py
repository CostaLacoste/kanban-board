from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    cors_origins: tuple[str, ...]
    max_attachment_size: int = 5 * 1024 * 1024
    max_attachments_per_task: int = 5

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
        return cls(database_path=database_path, cors_origins=origins)

