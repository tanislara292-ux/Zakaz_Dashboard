"""Thin ClickHouse client wrapper with retry and env-based defaults."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

import clickhouse_connect
from clickhouse_connect.driver.exceptions import ClickHouseError

if TYPE_CHECKING:
    from integrations.qtickets_api.config import QticketsApiConfig


logger = logging.getLogger(__name__)

_ENV_ALIASES = {
    "host": ("CLICKHOUSE_HOST", "CH_HOST"),
    "port": ("CLICKHOUSE_PORT", "CLICKHOUSE_HTTP_PORT", "CH_PORT"),
    "user": ("CLICKHOUSE_USER", "CH_USER", "CLICKHOUSE_USERNAME"),
    "password": ("CLICKHOUSE_PASSWORD", "CH_PASSWORD"),
    "database": ("CLICKHOUSE_DB", "CLICKHOUSE_DATABASE", "CH_DATABASE"),
    "secure": ("CLICKHOUSE_SECURE", "CH_SECURE"),
    "verify": ("CLICKHOUSE_VERIFY_SSL", "CH_VERIFY_SSL"),
}


def _read_env(key: str) -> Optional[str]:
    """Return the first non-empty environment value for the provided alias key."""
    for env_name in _ENV_ALIASES.get(key, ()):
        value = os.getenv(env_name)
        if value is not None and value.strip() != "":
            return value
    return None


def _parse_bool(value: Optional[str], *, default: bool = False) -> bool:
    """Return parsed bool for common textual truthy/falsey values."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return default


class ClickHouseClient:
    """A small convenience wrapper around ``clickhouse_connect``."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        secure: Optional[bool] = None,
        verify: Optional[bool] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connect_timeout: int = 10,
        send_receive_timeout: int = 30,
    ) -> None:
        env_secure = _parse_bool(_read_env("secure"), default=False)
        env_verify = _parse_bool(_read_env("verify"), default=env_secure)

        self.host = host or _read_env("host") or "localhost"
        self.secure = env_secure if secure is None else secure
        self.verify = env_verify if verify is None else verify

        default_port = "8443" if self.secure else "8123"
        port_env = _read_env("port")
        resolved_port = port_env if port_env is not None else default_port
        self.port = port if port is not None else int(resolved_port)
        self.username = username or _read_env("user") or "default"
        self.password = password or _read_env("password") or ""
        self.database = database or _read_env("database") or "default"

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connect_timeout = connect_timeout
        self.send_receive_timeout = send_receive_timeout

        self.client = None
        self._connect()

    # ------------------------------------------------------------------ #
    # Connection helpers
    # ------------------------------------------------------------------ #
    def _connect(self) -> None:
        """Establish a connection with simple exponential backoff."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.client = clickhouse_connect.get_client(
                    host=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    database=self.database,
                    secure=self.secure,
                    verify=self.verify,
                    connect_timeout=self.connect_timeout,
                    send_receive_timeout=self.send_receive_timeout,
                )
                self.client.command("SELECT 1")
                scheme = "https" if self.secure else "http"
                message = f"Connected to ClickHouse at {scheme}://{self.host}:{self.port}"
                logger.info(message)
                logging.getLogger("qtickets_api").info(message)
                return
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                logger.warning(
                    "ClickHouse connection attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** (attempt - 1)))
        if last_error:
            raise last_error

    def _call_with_retry(self, func, *args, **kwargs):
        """Retry wrapper used by query/command helpers."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except ClickHouseError as exc:
                last_error = exc
                logger.warning(
                    "ClickHouseError (%s): %r",
                    exc.__class__.__name__,
                    exc,
                    exc_info=True,
                )
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                logger.error(
                    "Unexpected ClickHouse error (%s): %r",
                    exc.__class__.__name__,
                    exc,
                    exc_info=True,
                )
            if attempt < self.max_retries:
                time.sleep(self.retry_delay * (2 ** (attempt - 1)))
                self._connect()
        if last_error:
            raise last_error

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def execute(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> clickhouse_connect.driver.query.ResultSet:
        """Execute a SELECT-style query with retries."""
        if parameters:
            return self._call_with_retry(self.client.query, query, parameters)
        return self._call_with_retry(self.client.query, query)

    def insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]] | Sequence[Dict[str, Any]],
        column_names: Optional[List[str]] = None,
    ) -> None:
        """Insert data into ClickHouse with retries."""
        kwargs: Dict[str, Any] = {}
        if column_names:
            kwargs["column_names"] = column_names
        rows = len(data) if isinstance(data, Sequence) else None
        logger.debug("Insert into %s rows=%s", table, rows if rows is not None else 'unknown')
        if column_names:
            logger.debug("Insert columns=%s", column_names)
        self._call_with_retry(self.client.insert, table, data, **kwargs)
        if rows is not None:
            logger.info("Inserted %s rows into %s", rows, table)

    def command(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute a command (DDL/DML) with retries."""
        if parameters:
            return self._call_with_retry(self.client.command, query, parameters)
        return self._call_with_retry(self.client.command, query)


def get_client(env_file: Optional[str] = None) -> ClickHouseClient:
    """Return a client configured from environment variables or a dotenv file."""
    if env_file:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    return ClickHouseClient()


def get_client_from_config(cfg: "QticketsApiConfig") -> ClickHouseClient:
    """Return a client configured from a ``QticketsApiConfig`` instance."""
    return ClickHouseClient(
        host=cfg.clickhouse_host,
        port=cfg.clickhouse_port,
        username=cfg.clickhouse_user,
        password=cfg.clickhouse_password,
        database=cfg.clickhouse_db,
        secure=cfg.clickhouse_secure,
        verify=cfg.clickhouse_verify_ssl,
    )
