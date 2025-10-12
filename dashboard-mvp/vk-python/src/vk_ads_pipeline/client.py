"""VK Ads API client with minimal wrapper helpers."""

from __future__ import annotations

import json
import logging
from contextlib import AbstractContextManager
from typing import Iterable, Sequence

import httpx

logger = logging.getLogger(__name__)


class VkAdsError(RuntimeError):
    """Base error for VK Ads API failures."""


def _encode_campaign_ids(ids: Sequence[int] | Sequence[str]) -> str:
    if ids == ["*"]:
        return json.dumps(["*"])
    return json.dumps([{"campaign_id": int(item)} for item in ids])


class VkAdsClient(AbstractContextManager["VkAdsClient"]):
    """Thin wrapper over VK Ads HTTP API."""

    def __init__(
        self,
        *,
        access_token: str,
        api_version: str = "5.199",
        timeout: float = 30.0,
        base_url: str = "https://api.vk.com",
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._token = access_token
        self._version = api_version

    def close(self) -> None:
        self._client.close()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request(self, method: str, params: dict) -> dict:
        payload = dict(params)
        payload["access_token"] = self._token
        payload["v"] = self._version
        response = self._client.post(f"/method/{method}", data=payload)
        try:
            data = response.json()
        except ValueError as exc:
            raise VkAdsError(f"Не удалось декодировать ответ {method}: {exc}") from exc

        if "error" in data:
            err = data["error"]
            raise VkAdsError(
                f"VK API error {err.get('error_code')}: {err.get('error_msg')} (method={method})"
            )

        return data.get("response", {})

    def get_campaigns(
        self,
        *,
        account_id: int,
        client_id: int | None = None,
        campaign_ids: Sequence[int] | Sequence[str] | None = None,
    ) -> list[dict]:
        params: dict[str, object] = {"account_id": account_id}
        if client_id is not None:
            params["client_id"] = client_id
        if campaign_ids:
            params["campaign_ids"] = _encode_campaign_ids(campaign_ids)
        result = self._request("ads.getCampaigns", params)
        if isinstance(result, dict) and "items" in result:
            return result["items"]  # type: ignore[return-value]
        return result if isinstance(result, list) else []

    def get_ads(
        self,
        *,
        account_id: int,
        campaign_ids: Sequence[int] | Sequence[str],
        client_id: int | None = None,
        include_deleted: bool = False,
    ) -> list[dict]:
        params: dict[str, object] = {
            "account_id": account_id,
            "include_deleted": 1 if include_deleted else 0,
            "campaign_ids": _encode_campaign_ids(campaign_ids),
        }
        if client_id is not None:
            params["client_id"] = client_id
        result = self._request("ads.getAds", params)
        if isinstance(result, dict) and "items" in result:
            return result["items"]  # type: ignore[return-value]
        return result if isinstance(result, list) else []

    def get_statistics(
        self,
        *,
        account_id: int,
        ids_type: str,
        ids: Sequence[int],
        period: str,
        date_from: str,
        date_to: str,
        metrics: Iterable[str],
        client_id: int | None = None,
    ) -> list[dict]:
        params: dict[str, object] = {
            "account_id": account_id,
            "ids_type": ids_type,
            "ids": ",".join(str(item) for item in ids),
            "period": period,
            "date_from": date_from,
            "date_to": date_to,
            "metrics": ",".join(metrics),
        }
        if client_id is not None:
            params["client_id"] = client_id

        result = self._request("ads.getStatistics", params)
        if isinstance(result, list):
            return result
        return []
