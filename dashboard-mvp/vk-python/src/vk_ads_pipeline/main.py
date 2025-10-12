"""CLI entrypoint for VK Ads pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from .config import ConfigError, VkAdsConfig, load_config
from .pipeline import PipelineStats, VkAdsPipeline

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VK Ads → Google Sheets pipeline")
    parser.add_argument("--date-from", help="Начальная дата отчёта (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Конечная дата отчёта (YYYY-MM-DD)")
    parser.add_argument(
        "--campaign-ids",
        help="Список campaign_id через запятую или '*', по умолчанию берутся из окружения",
    )
    parser.add_argument("--dry-run", action="store_true", help="Не записывать данные в Google Sheets")
    parser.add_argument("--output-csv", help="Сохранить результат в CSV по указанному пути")
    parser.add_argument("--sink", choices=["sheets", "clickhouse"], default="sheets", help="Куда загружать данные: sheets или clickhouse")
    parser.add_argument("--verbose", action="store_true", help="Уровень логирования DEBUG")
    return parser.parse_args(argv)


def apply_overrides(config: VkAdsConfig, args: argparse.Namespace) -> VkAdsConfig:
    updates = {}
    if args.date_from:
        updates["date_from"] = date.fromisoformat(args.date_from)
    if args.date_to:
        updates["date_to"] = date.fromisoformat(args.date_to)
    if args.campaign_ids:
        raw = [item.strip() for item in args.campaign_ids.split(",") if item.strip()]
        if raw == ["*"]:
            updates["campaign_ids"] = ["*"]
        else:
            try:
                updates["campaign_ids"] = [int(item) for item in raw]
            except ValueError as exc:
                raise ConfigError(f"campaign_ids должны быть числами: {raw}") from exc
    if args.dry_run:
        updates["dry_run"] = True
    if args.output_csv:
        updates["output_csv"] = Path(args.output_csv).expanduser()
    if args.sink:
        updates["sink"] = args.sink
    return config.with_overrides(**updates)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    setup_logging(args.verbose)
    try:
        config = load_config()
        config = apply_overrides(config, args)
    except ConfigError as exc:
        logging.error("Конфигурация: %s", exc)
        return 2

    pipeline = VkAdsPipeline(config)
    try:
        result: PipelineStats = pipeline.run()
    except ConfigError as exc:
        logging.error("Ошибка конфигурации: %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001
        logging.exception("Необработанная ошибка пайплайна: %s", exc)
        return 1

    logging.info(
        "VK Ads pipeline finished: campaigns=%d ads=%d produced=%d inserted=%d",
        result.fetched_campaigns,
        result.fetched_ads,
        result.rows_produced,
        result.rows_inserted,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
