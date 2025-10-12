from __future__ import annotations

from pathlib import Path

import pytest

from vk_ads_pipeline.config import ConfigError, load_config


def test_load_config_minimal(tmp_path: Path) -> None:
    sa = tmp_path / "sa.json"
    sa.write_text("{}", encoding="utf-8")
    env = {
        "VK_ACCESS_TOKEN": "token",
        "VK_ACCOUNT_ID": "101",
        "SPREADSHEET_ID": "sheet123",
        "GOOGLE_SA_JSON_PATH": str(sa),
    }
    cfg = load_config(env=env.items(), env_file=None)
    assert cfg.account_id == 101
    assert cfg.campaign_ids == ["*"]
    assert cfg.sheet_name == "VK_Ads"
    assert cfg.google_sa_path == sa


def test_load_config_requires_dates_order(tmp_path: Path) -> None:
    sa = tmp_path / "sa.json"
    sa.write_text("{}", encoding="utf-8")
    env = {
        "VK_ACCESS_TOKEN": "token",
        "VK_ACCOUNT_ID": "101",
        "SPREADSHEET_ID": "sheet123",
        "GOOGLE_SA_JSON_PATH": str(sa),
        "VK_DATE_FROM": "2024-10-10",
        "VK_DATE_TO": "2024-10-01",
    }
    with pytest.raises(ConfigError):
        load_config(env=env.items(), env_file=None)
