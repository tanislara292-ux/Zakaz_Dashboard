"""
Environment configuration for the QTickets API integration.

The loader expects a dedicated dotenv file (e.g. ``secrets/.env.qtickets_api``)
to provide API credentials and ClickHouse connection parameters.  This module
encapsulates the validation logic and exposes helper methods used by the
integration runtime.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

ENV_ALIASES = {
    "QTICKETS_TOKEN": ("QTICKETS_TOKEN", "QTICKETS_API_TOKEN"),
    "QTICKETS_BASE_URL": ("QTICKETS_BASE_URL", "QTICKETS_API_BASE_URL"),
    "QTICKETS_SINCE_HOURS": ("QTICKETS_SINCE_HOURS", "QTICKETS_LOOKBACK_HOURS"),
    "ORG_NAME": ("ORG_NAME", "QTICKETS_ORG_NAME"),
    "CLICKHOUSE_HOST": ("CLICKHOUSE_HOST", "CH_HOST"),
    "CLICKHOUSE_PORT": ("CLICKHOUSE_PORT", "CH_PORT", "CLICKHOUSE_HTTP_PORT"),
    "CLICKHOUSE_DB": ("CLICKHOUSE_DB", "CLICKHOUSE_DATABASE", "CH_DATABASE"),
    "CLICKHOUSE_USER": (
        "CLICKHOUSE_USER",
        "CLICKHOUSE_USER_WRITE",
        "CH_USER",
        "CH_USER_WRITE",
        "CLICKHOUSE_USERNAME",
    ),
    "CLICKHOUSE_PASSWORD": (
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_PASSWORD_WRITE",
        "CH_PASSWORD",
        "CH_PASSWORD_WRITE",
    ),
    "CLICKHOUSE_SECURE": ("CLICKHOUSE_SECURE", "CH_SECURE"),
    "CLICKHOUSE_VERIFY_SSL": ("CLICKHOUSE_VERIFY_SSL", "CH_VERIFY_SSL"),
    "TZ": ("TZ", "DEFAULT_TZ"),
    "REPORT_TZ": ("REPORT_TZ", "QTICKETS_REPORT_TZ"),
    "JOB_NAME": ("JOB_NAME", "QTICKETS_JOB_NAME"),
    "DRY_RUN": ("DRY_RUN", "QTICKETS_DRY_RUN"),
    "QTICKETS_PARTNERS_BASE_URL": (
        "QTICKETS_PARTNERS_BASE_URL",
        "QTICKETS_PARTNERS_API_BASE_URL",
    ),
    "QTICKETS_PARTNERS_TOKEN": (
        "QTICKETS_PARTNERS_TOKEN",
        "QTICKETS_PARTNERS_API_TOKEN",
    ),
    "QTICKETS_PARTNERS_FIND_REQUESTS": (
        "QTICKETS_PARTNERS_FIND_REQUESTS",
        "QTICKETS_PARTNERS_FIND_REQUESTS_JSON",
    ),
}

DEFAULTS = {
    "CLICKHOUSE_SECURE": "false",
    "CLICKHOUSE_VERIFY_SSL": "false",
}

SKIPPABLE_RESOURCE_ENV = {
    "clients": "QTICKETS_SKIP_CLIENTS",
    "price_shades": "QTICKETS_SKIP_PRICE_SHADES",
    "discounts": "QTICKETS_SKIP_DISCOUNTS",
    "promo_codes": "QTICKETS_SKIP_PROMO_CODES",
    "barcodes": "QTICKETS_SKIP_BARCODES",
    "partner_tickets": "QTICKETS_SKIP_PARTNER_TICKETS",
}


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
    qtickets_partners_base_url: Optional[str]
    qtickets_partners_token: Optional[str]
    partners_find_requests: List[Dict[str, Any]]

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
    skip_resources: Dict[str, bool] = field(default_factory=dict)

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

        def _read_env(key: str) -> Optional[str]:
            for alias in ENV_ALIASES.get(key, (key,)):
                value = os.getenv(alias)
                if value is not None and value.strip() != "":
                    return value
            return DEFAULTS.get(key)

        # Check for missing required variables (respecting aliases/defaults)
        raw_env = {key: _read_env(key) for key in cls.REQUIRED_KEYS}
        missing = [key for key, value in raw_env.items() if value is None or value.strip() == ""]
        if missing:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        partners_base = (_read_env("QTICKETS_PARTNERS_BASE_URL") or "").strip()
        partners_token = (_read_env("QTICKETS_PARTNERS_TOKEN") or "").strip() or None
        partners_requests_raw = (_read_env("QTICKETS_PARTNERS_FIND_REQUESTS") or "").strip()
        partners_requests: List[Dict[str, Any]] = []
        if partners_requests_raw:
            try:
                parsed = json.loads(partners_requests_raw)
            except json.JSONDecodeError as exc:
                raise ConfigError(
                    "QTICKETS_PARTNERS_FIND_REQUESTS must be a valid JSON array"
                ) from exc
            if isinstance(parsed, dict):
                partners_requests = [parsed]
            elif isinstance(parsed, list):
                partners_requests = [
                    req for req in parsed if isinstance(req, dict)
                ]
            else:
                raise ConfigError(
                    "QTICKETS_PARTNERS_FIND_REQUESTS must be a JSON object or array of objects"
                )

        # Parse boolean values
        def parse_bool(key: str, value: str) -> bool:
            val = value.strip().lower()
            if val in ("true", "1", "yes", "on"):
                return True
            if val in ("false", "0", "no", "off"):
                return False
            raise ConfigError(f"Invalid boolean value for {key}: {value}")

        def parse_int(key: str, value: str) -> int:
            try:
                return int(value.strip())
            except ValueError as exc:
                raise ConfigError(f"{key} must be an integer, got: {value}") from exc

        skip_flags: Dict[str, bool] = {}
        for resource, env_name in SKIPPABLE_RESOURCE_ENV.items():
            raw_value = _read_env(env_name)
            if raw_value is None:
                continue
            skip_flags[resource] = parse_bool(env_name, raw_value)

        # Build configuration object
        config = cls(
            # QTickets API
            qtickets_token=raw_env["QTICKETS_TOKEN"],
            qtickets_base_url=raw_env["QTICKETS_BASE_URL"].rstrip("/"),
            qtickets_since_hours=parse_int("QTICKETS_SINCE_HOURS", raw_env["QTICKETS_SINCE_HOURS"]),
            org_name=raw_env["ORG_NAME"],
            qtickets_partners_base_url=partners_base or None,
            qtickets_partners_token=partners_token,
            partners_find_requests=partners_requests,
            # ClickHouse
            clickhouse_host=raw_env["CLICKHOUSE_HOST"],
            clickhouse_port=parse_int("CLICKHOUSE_PORT", raw_env["CLICKHOUSE_PORT"]),
            clickhouse_db=raw_env["CLICKHOUSE_DB"],
            clickhouse_user=raw_env["CLICKHOUSE_USER"],
            clickhouse_password=raw_env["CLICKHOUSE_PASSWORD"],
            clickhouse_secure=parse_bool("CLICKHOUSE_SECURE", raw_env["CLICKHOUSE_SECURE"]),
            clickhouse_verify_ssl=parse_bool(
                "CLICKHOUSE_VERIFY_SSL", raw_env["CLICKHOUSE_VERIFY_SSL"]
            ),
            # Runtime
            tz=raw_env["TZ"],
            report_tz=raw_env["REPORT_TZ"],
            job_name=raw_env["JOB_NAME"],
            dry_run=parse_bool("DRY_RUN", raw_env["DRY_RUN"]),
            skip_resources=skip_flags,
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

        os.environ["CLICKHOUSE_HOST"] = self.clickhouse_host
        os.environ["CLICKHOUSE_PORT"] = str(self.clickhouse_port)
        os.environ["CLICKHOUSE_USER"] = self.clickhouse_user
        os.environ["CLICKHOUSE_PASSWORD"] = self.clickhouse_password
        os.environ["CLICKHOUSE_DB"] = self.clickhouse_db
        os.environ["CLICKHOUSE_SECURE"] = (
            "true" if self.clickhouse_secure else "false"
        )
        os.environ["CLICKHOUSE_VERIFY_SSL"] = (
            "true" if self.clickhouse_verify_ssl else "false"
        )
        os.environ["CLICKHOUSE_DATABASE"] = self.clickhouse_db
        os.environ["CLICKHOUSE_HTTP_PORT"] = str(self.clickhouse_port)

        os.environ["CH_HOST"] = self.clickhouse_host
        os.environ["CH_PORT"] = str(self.clickhouse_port)
        os.environ["CH_USER"] = self.clickhouse_user
        os.environ["CH_PASSWORD"] = self.clickhouse_password
        os.environ["CH_DATABASE"] = self.clickhouse_db
        os.environ["CH_SECURE"] = "true" if self.clickhouse_secure else "false"
        os.environ["CH_VERIFY_SSL"] = "true" if self.clickhouse_verify_ssl else "false"

    def should_skip(self, resource: str) -> bool:
        """Return True when the resource is disabled via QTICKETS_SKIP_* flags."""
        return self.skip_resources.get(resource, False)

    def auth_headers(self) -> Dict[str, str]:
        """Return the Authorization header required by the QTickets API."""
        return {"Authorization": f"Bearer {self.qtickets_token}"}
