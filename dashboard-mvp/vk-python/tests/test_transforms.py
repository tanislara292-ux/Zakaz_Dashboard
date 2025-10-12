from __future__ import annotations

from vk_ads_pipeline.transforms import normalize_statistics


def test_normalize_statistics_merges_meta() -> None:
    stats = [
        {
            "id": 10,
            "stats": [
                {"day": "2024-09-20", "spent": "123.45", "clicks": 12, "impressions": 345},
                {"day": "2024-09-21", "spent": "0", "clicks": 0, "impressions": 0},
            ],
        }
    ]
    ads_meta = {
        10: {
            "id": 10,
            "campaign_id": 5,
            "name": "Test Ad",
            "link_url": "https://example.com?utm_source=vk&utm_medium=cpc&utm_campaign=test",
        }
    }
    campaigns_meta = {
        5: {"id": 5, "name": "Autumn Campaign"},
    }

    rows = normalize_statistics(
        ids_type="ad",
        stats=stats,
        ads_meta=ads_meta,
        campaigns_meta=campaigns_meta,
    )

    assert len(rows) == 2
    assert rows[0]["campaign_name"] == "Autumn Campaign"
    assert rows[0]["adgroup_name"] == "Test Ad"
    assert rows[0]["cost"] == "123.45"
    assert rows[0]["utm_source"] == "vk"
    assert rows[0]["utm_campaign"] == "test"
