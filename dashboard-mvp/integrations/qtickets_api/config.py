"""
Environment configuration for the QTickets API integration.

The loader expects a dedicated dotenv file (e.g. ``secrets/.env.qtickets_api``)
to provide API credentials and ClickHouse connection parameters.  This module
encapsulates the validation logic and exposes helper methods used by the
integration runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when the integration configuration is incomplete or invalid."""


@dataclass(frozen=True)
class QticketsApiConfig:
    """Typed representation of the integration configuration."""

    base_url: str
    token: str
    clickhouse_host: str
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_db: str
    timezone: str
    org_name: str

    REQUIRED_KEYS = (
        "QTICKETS_API_BASE_URL",
        "QTICKETS_API_TOKEN",
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_USER",
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_DB",
        "TZ",
        "ORG_NAME",
    )

    @classmethod
    def load(cls, env_file: Optional[str] = None, *, override: bool = True) -> "QticketsApiConfig":
        """
        Load configuration from environment variables (optionally reading a dotenv file).

        Args:
            env_file: Path to the dotenv file containing integration secrets.
            override: Whether to overwrite already loaded environment variables.

        Returns:
            QticketsApiConfig: hydrated configuration object.

        Raises:
            ConfigError: if one of the required variables is missing.
        """
        if env_file:
            if not os.path.exists(env_file):
                raise ConfigError(f"Env file not found: {env_file}")
            load_dotenv(env_file, override=override)

        missing = [key for key in cls.REQUIRED_KEYS if not os.getenv(key)]
        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

        base_url = os.getenv("QTICKETS_API_BASE_URL", "").rstrip("/")
        token = os.getenv("QTICKETS_API_TOKEN", "")
        clickhouse_host = os.getenv("CLICKHOUSE_HOST", "")
        clickhouse_user = os.getenv("CLICKHOUSE_USER", "")
        clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")
        clickhouse_db = os.getenv("CLICKHOUSE_DB", "")
        timezone = os.getenv("TZ", "Europe/Moscow")
        org_name = os.getenv("ORG_NAME", "")

        config = cls(
            base_url=base_url,
            token=token,
            clickhouse_host=clickhouse_host,
            clickhouse_user=clickhouse_user,
            clickhouse_password=clickhouse_password,
            clickhouse_db=clickhouse_db,
            timezone=timezone,
            org_name=org_name,
        )

        config._apply_runtime_env()
        return config

    def _apply_runtime_env(self) -> None:
        """
        Propagate config values to environment variables expected by shared utilities.

        ``ClickHouseClient`` reads ``CH_*`` variables, while time helpers rely on
        ``DEFAULT_TZ``.  The loader uses this side effect to avoid duplicating
        connection setup logic across integrations.
        """
        os.environ["DEFAULT_TZ"] = self.timezone
        os.environ["CH_HOST"] = self.clickhouse_host
        os.environ["CH_USER"] = self.clickhouse_user
        os.environ["CH_PASSWORD"] = self.clickhouse_password
        os.environ["CH_DATABASE"] = self.clickhouse_db

    def auth_headers(self) -> Dict[str, str]:
        """Return the Authorization header required by the QTickets API."""
        return {"Authorization": f"Bearer {self.token}"}
