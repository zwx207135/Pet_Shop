"""Database configuration loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when a required database setting is missing."""


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value or ""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DbConfig:
    driver: str
    server: str
    database: str
    auth_user: str
    auth_password: str
    clerk_user: str
    clerk_password: str
    manager_user: str
    manager_password: str
    encrypt: bool = True
    trust_server_certificate: bool = True
    timeout: int = 5

    @classmethod
    def from_env(cls) -> "DbConfig":
        return cls(
            driver=_env("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            server=_env("DB_SERVER", "localhost"),
            database=_env("DB_NAME", "PetCareDB"),
            auth_user=_env("DB_AUTH_USER", "petcare_auth"),
            auth_password=_env("DB_AUTH_PASSWORD", required=True),
            clerk_user=_env("DB_CLERK_USER", "petcare_clerk"),
            clerk_password=_env("DB_CLERK_PASSWORD", required=True),
            manager_user=_env("DB_MANAGER_USER", "petcare_manager"),
            manager_password=_env("DB_MANAGER_PASSWORD", required=True),
            encrypt=_env_bool("DB_ENCRYPT", True),
            trust_server_certificate=_env_bool("DB_TRUST_SERVER_CERTIFICATE", True),
            timeout=int(_env("DB_TIMEOUT", "5")),
        )

    def credentials(self, role: str) -> tuple[str, str]:
        if role == "auth":
            return self.auth_user, self.auth_password
        if role == "clerk":
            return self.clerk_user, self.clerk_password
        if role == "manager":
            return self.manager_user, self.manager_password
        raise ConfigError(f"Unknown database role: {role}")

    def connection_string(self, role: str) -> str:
        user, password = self.credentials(role)
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
            f"UID={user}",
            f"PWD={password}",
            f"Encrypt={'yes' if self.encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'}",
            "APP=PetCareDAO",
        ]
        return ";".join(parts) + ";"
