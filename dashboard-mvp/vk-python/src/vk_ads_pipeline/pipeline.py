"""Orchestrates VK Ads data retrieval and persistence."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .client import VkAdsClient, VkAdsError
from .config import VkAdsConfig
from .sink.clickhouse_sink import ClickHouseSink
from .transforms import normalize_statistics
from .transform.normalize import normalize_vk_ads_row

logger = logging.getLogger(__name__)


def _chunked(values: Iterable[int], size: int) -> Iterator[list[int]]:
    chunk: list[int] = []
    for value in values:
        chunk.append(value)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


@dataclass
class PipelineStats:
    fetched_ads: int
    fetched_campaigns: int
    rows_produced: int
    rows_inserted: int


class VkAdsPipeline:
    """High-level pipeline that glues together client, transforms and sinks."""

    def __init__(
        self,
        config: VkAdsConfig,
        *,
        client: VkAdsClient | None = None,
        ch_sink: ClickHouseSink | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._ch_sink = ch_sink

    def run(self) -> PipelineStats:
        stats_rows: list[dict[str, str]] = []
        campaigns_meta: dict[int, dict]
        ads_meta: dict[int, dict]

        with (self._client or VkAdsClient(access_token=self._config.access_token)) as client:
            campaigns_meta = self._load_campaigns(client)
            ads_meta = self._load_ads(client, campaigns_meta)

            ids_source: Iterable[int]
            if self._config.ids_type == "campaign":
                ids_source = campaigns_meta.keys()
            else:
                ids_source = ads_meta.keys()

            for bucket in _chunked([int(i) for i in ids_source], size=200):
                logger.debug("Fetching stats chunk size=%d", len(bucket))
                try:
                    batch = client.get_statistics(
                        account_id=self._config.account_id,
                        client_id=self._config.client_id,
                        ids_type=self._config.ids_type,
                        ids=bucket,
                        period=self._config.period,
                        date_from=self._config.date_from.isoformat(),
                        date_to=self._config.date_to.isoformat(),
                        metrics=self._config.metrics,
                    )
                except VkAdsError as exc:
                    logger.error("Stats chunk failed (%s): %s", bucket, exc)
                    continue
                normalized_rows = normalize_statistics(
                    ids_type=self._config.ids_type,
                    stats=batch,
                    ads_meta=ads_meta,
                    campaigns_meta=campaigns_meta,
                )
                
                # Дополнительная нормализация для ClickHouse
                if self._config.sink == "clickhouse":
                    for row in normalized_rows:
                        normalize_vk_ads_row(row, self._config.account_id)
                
                stats_rows.extend(normalized_rows)

        rows_inserted = 0

        if self._config.output_csv:
            self._dump_csv(stats_rows, self._config.output_csv, header=list(self._config.header))

        if not self._config.dry_run:
            # Всегда используем ClickHouse как единственный sink
            ch_sink = self._ch_sink or ClickHouseSink()
            rows_inserted = ch_sink.insert_vk_stg(stats_rows)
            logger.info("Inserted %d new rows into ClickHouse", rows_inserted)
        else:
            logger.info("Dry-run complete: produced %d rows", len(stats_rows))

        return PipelineStats(
            fetched_ads=len(ads_meta),
            fetched_campaigns=len(campaigns_meta),
            rows_produced=len(stats_rows),
            rows_inserted=rows_inserted,
        )

    def _load_campaigns(self, client: VkAdsClient) -> dict[int, dict]:
        response = client.get_campaigns(
            account_id=self._config.account_id,
            client_id=self._config.client_id,
            campaign_ids=self._config.campaign_ids if self._config.campaign_ids != ["*"] else None,
        )
        campaigns = {int(item["id"]): item for item in response if "id" in item}
        logger.info("Fetched %d campaigns", len(campaigns))
        return campaigns

    def _load_ads(self, client: VkAdsClient, campaigns_meta: dict[int, dict]) -> dict[int, dict]:
        campaign_ids = self._config.campaign_ids
        if campaign_ids == ["*"]:
            campaign_ids = list(campaigns_meta.keys()) or ["*"]
        ads = client.get_ads(
            account_id=self._config.account_id,
            client_id=self._config.client_id,
            campaign_ids=campaign_ids,
            include_deleted=False,
        )
        ads_meta = {int(item["id"]): item for item in ads if "id" in item}
        logger.info("Fetched %d ads", len(ads_meta))
        return ads_meta

    @staticmethod
    def _dump_csv(rows: list[dict[str, str]], path: Path, header: list[str]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
