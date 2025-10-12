"""Transform utilities for VK Ads data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qs, urlparse


def parse_utm(url: str | None) -> dict[str, str]:
    if not url:
        return {}
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {key: values[0] for key, values in params.items() if key.startswith("utm_") and values}


def _to_currency(value: str | int | float | None) -> str:
    if value in (None, ""):
        return "0"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0"


def _to_int(value: str | int | float | None) -> str:
    if value in (None, ""):
        return "0"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "0"


def _normalize_date(raw: str | None, fallback: str) -> str:
    if not raw:
        return fallback
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        return raw[:10]


def normalize_statistics(
    *,
    ids_type: str,
    stats: Iterable[dict],
    ads_meta: dict[int, dict],
    campaigns_meta: dict[int, dict],
) -> list[dict[str, str]]:
    """Flatten VK Ads API response into sheet rows."""
    rows: list[dict[str, str]] = []

    campaign_names = defaultdict(str)
    for cid, info in campaigns_meta.items():
        name = info.get("name") or info.get("title")
        if name:
            campaign_names[int(cid)] = str(name)

    for item in stats:
        ident = item.get("id")
        if ident is None:
            continue
        entries = item.get("stats") or []
        meta = ads_meta.get(int(ident), {})
        campaign_id = meta.get("campaign_id") or item.get("campaign_id") or ident
        campaign_id = int(campaign_id)
        adgroup_id = int(meta.get("id") or ident)
        adgroup_name = meta.get("name") or ""
        campaign_name = campaign_names.get(int(campaign_id), "")
        utm = parse_utm(meta.get("link_url") or meta.get("link_href") or meta.get("domain"))

        for entry in entries:
            day = _normalize_date(entry.get("day"), entry.get("month") or "")
            row = {
                "date": day,
                "campaign_id": str(campaign_id),
                "campaign_name": campaign_name,
                "adgroup_id": str(adgroup_id),
                "adgroup_name": str(adgroup_name),
                "cost": _to_currency(entry.get("spent")),
                "clicks": _to_int(entry.get("clicks")),
                "impressions": _to_int(entry.get("impressions")),
                "city": meta.get("cities") or "",
                "utm_source": utm.get("utm_source", ""),
                "utm_medium": utm.get("utm_medium", ""),
                "utm_campaign": utm.get("utm_campaign", ""),
                "utm_content": utm.get("utm_content", ""),
                "utm_term": utm.get("utm_term", ""),
            }
            rows.append(row)

        if ids_type == "campaign" and not entries:
            rows.append(
                {
                    "date": "",
                    "campaign_id": str(campaign_id),
                    "campaign_name": campaign_name,
                    "adgroup_id": str(adgroup_id),
                    "adgroup_name": str(adgroup_name),
                    "cost": "0",
                    "clicks": "0",
                    "impressions": "0",
                    "city": meta.get("cities") or "",
                    "utm_source": utm.get("utm_source", ""),
                    "utm_medium": utm.get("utm_medium", ""),
                    "utm_campaign": utm.get("utm_campaign", ""),
                    "utm_content": utm.get("utm_content", ""),
                    "utm_term": utm.get("utm_term", ""),
                }
            )
    return rows
