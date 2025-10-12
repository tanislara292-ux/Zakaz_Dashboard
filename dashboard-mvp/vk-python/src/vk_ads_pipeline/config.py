"""Configuration helpers for VK Ads pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required configuration values are missing or invalid."""


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"Некорректная дата: {value}") from exc


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _ensure_path(path: str | None) -> Path:
    if not path:
        raise ConfigError("Не указан путь к Google Service Account (GOOGLE_SA_JSON_PATH)")
    p = Path(path).expanduser()
    if not p.exists():
        raise ConfigError(f"Файл Service Account не найден: {p}")
    return p


def _parse_campaign_ids(raw: Sequence[str]) -> list[int]:
    result: list[int] = []
    for item in raw:
        if item == "*":
            return ["*"]  # type: ignore[return-value]
        try:
            result.append(int(item))
        except ValueError as exc:
            raise ConfigError(f"Идентификатор кампании должен быть числом: {item}") from exc
    return result


@dataclass(frozen=True)
class VkAdsConfig:
    """Holds all runtime configuration for the pipeline."""

    access_token: str
    account_id: int
    client_id: int | None
    ids_type: str
    campaign_ids: list[int] | list[str]
    metrics: list[str]
    period: str
    date_from: date
    date_to: date
    timezone: str
    spreadsheet_id: str
    sheet_name: str
    google_sa_path: Path
    dry_run: bool = False
    output_csv: Path | None = None
    sink: str = "sheets"  # "sheets" или "clickhouse"

    def with_overrides(self, **updates) -> "VkAdsConfig":
        """Return a copy of the config with certain fields replaced."""
        return replace(self, **{k: v for k, v in updates.items() if v is not None})

    @property
    def key_columns(self) -> tuple[str, ...]:
        return ("date", "campaign_id", "adgroup_id")

    @property
    def header(self) -> tuple[str, ...]:
        return (
            "date",
            "campaign_id",
            "campaign_name",
            "adgroup_id",
            "adgroup_name",
            "cost",
            "clicks",
            "impressions",
            "city",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
        )


def load_config(
    *, env: Iterable[tuple[str, str | None]] | None = None, env_file: str | Path | None = ".env"
) -> VkAdsConfig:
    """Load configuration from environment variables."""
    if env is None:
        load_dotenv(env_file, override=False)
        accessor = os.getenv
    else:
        store = {k: v for k, v in env}

        def accessor(name: str) -> str | None:
            return store.get(name)

    access_token = accessor("VK_ACCESS_TOKEN")
    if not access_token:
        raise ConfigError("Не задан VK_ACCESS_TOKEN")

    account_id_raw = accessor("VK_ACCOUNT_ID")
    if not account_id_raw:
        raise ConfigError("Не задан VK_ACCOUNT_ID")
    try:
        account_id = int(account_id_raw)
    except ValueError as exc:
        raise ConfigError("VK_ACCOUNT_ID должен быть числом") from exc

    client_id_raw = accessor("VK_CLIENT_ID")
    client_id = None
    if client_id_raw:
        try:
            client_id = int(client_id_raw)
        except ValueError as exc:
            raise ConfigError("VK_CLIENT_ID должен быть числом") from exc

    ids_type = accessor("VK_IDS_TYPE") or "ad"
    ids_type = ids_type.lower()
    if ids_type not in {"ad", "campaign"}:
        raise ConfigError("VK_IDS_TYPE должен быть 'ad' или 'campaign'")

    campaigns = _split_csv(accessor("VK_CAMPAIGN_IDS"))
    campaign_ids = _parse_campaign_ids(campaigns) if campaigns else ["*"]  # type: ignore[arg-type]

    metrics_raw = _split_csv(accessor("VK_METRICS") or "spent,clicks,impressions")
    metrics = metrics_raw or ["spent", "clicks", "impressions"]

    period = accessor("VK_PERIOD") or "day"

    today = date.today()
    default_from = today - timedelta(days=1)
    date_from = _to_date(accessor("VK_DATE_FROM"), default_from)
    date_to = _to_date(accessor("VK_DATE_TO"), today)
    if date_from > date_to:
        raise ConfigError("VK_DATE_FROM не может быть позже VK_DATE_TO")

    timezone = accessor("REPORT_TZ") or accessor("VK_TIMEZONE") or "Europe/Moscow"

    spreadsheet_id = accessor("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ConfigError("Не указан SPREADSHEET_ID")

    sheet_name = accessor("VK_SHEET_NAME") or "VK_Ads"

    google_sa = _ensure_path(accessor("GOOGLE_SA_JSON_PATH"))

    dry_run = _to_bool(accessor("VK_DRY_RUN"))

    output_csv_raw = accessor("VK_OUTPUT_CSV")
    output_csv = Path(output_csv_raw).expanduser() if output_csv_raw else None

    return VkAdsConfig(
        access_token=access_token,
        account_id=account_id,
        client_id=client_id,
        ids_type=ids_type,
        campaign_ids=campaign_ids,
        metrics=metrics,
        period=period,
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        google_sa_path=google_sa,
        dry_run=dry_run,
        output_csv=output_csv,
        sink=accessor("VK_SINK") or "sheets",
    )
