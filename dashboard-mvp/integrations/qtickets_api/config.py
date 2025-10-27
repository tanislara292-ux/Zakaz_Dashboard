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

    # QTickets API settings
    qtickets_token: str
    qtickets_base_url: str
    qtickets_since_hours: int
    org_name: str

    # ClickHouse settings
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_db: str
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_secure: bool
    clickhouse_verify_ssl: bool

    # Runtime settings
    tz: str
    report_tz: str
    job_name: str
    dry_run: bool

    # List of all required environment variables
    REQUIRED_KEYS = (
        "QTICKETS_TOKEN",
        "QTICKETS_BASE_URL",
        "ORG_NAME",
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_PORT",
        "CLICKHOUSE_DB",
        "CLICKHOUSE_USER",
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_SECURE",
        "CLICKHOUSE_VERIFY_SSL",
        "TZ",
        "REPORT_TZ",
        "JOB_NAME",
        "DRY_RUN",
        "QTICKETS_SINCE_HOURS",
    )

    @classmethod
    def load(
        cls, env_file: Optional[str] = None, *, override: bool = True
    ) -> "QticketsApiConfig":
        """
        Load configuration from environment variables (optionally reading a dotenv file).

        If env_file is provided but doesn't exist or can't be read (e.g., permission denied),
        the function will fall back to reading from os.environ directly.

        Args:
            env_file: Path to the dotenv file containing integration secrets.
            override: Whether to overwrite already loaded environment variables.

        Returns:
            QticketsApiConfig: hydrated configuration object.

        Raises:
            ConfigError: if one of the required variables is missing.
        """
        # Try to load from file if provided
        if env_file:
            try:
                if os.path.exists(env_file):
                    load_dotenv(env_file, override=override)
                else:
                    # File doesn't exist, fall back to environment variables
                    pass
            except (OSError, PermissionError):
                # Can't read file (e.g., permission denied), fall back to environment variables
                pass

        # Check for missing required variables
        missing = [key for key in cls.REQUIRED_KEYS if not os.getenv(key)]
        if missing:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Parse boolean values
        def parse_bool(value: str) -> bool:
            return value.lower() in ("true", "1", "yes", "on")

        # Build configuration object
        config = cls(
            # QTickets API
            qtickets_token=os.getenv("QTICKETS_TOKEN", ""),
            qtickets_base_url=os.getenv("QTICKETS_BASE_URL", "").rstrip("/"),
            qtickets_since_hours=int(os.getenv("QTICKETS_SINCE_HOURS", "4")),
            org_name=os.getenv("ORG_NAME", ""),
            # ClickHouse
            clickhouse_host=os.getenv("CLICKHOUSE_HOST", ""),
            clickhouse_port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            clickhouse_db=os.getenv("CLICKHOUSE_DB", ""),
            clickhouse_user=os.getenv("CLICKHOUSE_USER", ""),
            clickhouse_password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            clickhouse_secure=parse_bool(os.getenv("CLICKHOUSE_SECURE", "true")),
            clickhouse_verify_ssl=parse_bool(
                os.getenv("CLICKHOUSE_VERIFY_SSL", "true")
            ),
            # Runtime
            tz=os.getenv("TZ", "Europe/Moscow"),
            report_tz=os.getenv("REPORT_TZ", "Europe/Moscow"),
            job_name=os.getenv("JOB_NAME", "qtickets_api"),
            dry_run=parse_bool(os.getenv("DRY_RUN", "false")),
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
        os.environ["DEFAULT_TZ"] = self.tz
        os.environ["CH_HOST"] = self.clickhouse_host
        os.environ["CH_PORT"] = str(self.clickhouse_port)
        os.environ["CH_USER"] = self.clickhouse_user
        os.environ["CH_PASSWORD"] = self.clickhouse_password
        os.environ["CH_DATABASE"] = self.clickhouse_db
        os.environ["CH_SECURE"] = str(self.clickhouse_secure)
        os.environ["CH_VERIFY_SSL"] = str(self.clickhouse_verify_ssl)

    def auth_headers(self) -> Dict[str, str]:
        """Return the Authorization header required by the QTickets API."""
        return {"Authorization": f"Bearer {self.qtickets_token}"}
