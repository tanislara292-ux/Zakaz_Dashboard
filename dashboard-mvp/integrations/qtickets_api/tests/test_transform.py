from __future__ import annotations

from datetime import datetime

from integrations.qtickets_api.transform import (
    transform_clients,
    transform_partner_tickets,
)


def test_transform_clients_normalizes_fields():
    clients = [
        {
            "id": 1,
            "email": "User@example.com",
            "details": {"name": "Ivan", "surname": "Ivanov", "phone": "+7123"},
        }
    ]
    rows = transform_clients(clients, version=42, ingested_at=datetime(2025, 1, 1, 0, 0, 0))
    assert rows[0]["client_id"] == "1"
    assert rows[0]["email"] == "user@example.com"
    assert rows[0]["phone"] == "+7123"
    assert rows[0]["_ver"] == 42
    assert rows[0]["payload_json"].startswith("{")


def test_transform_partner_tickets_casts_paid_flag():
    payload = [
        {"id": "t1", "paid": True, "price": "123.45"},
        {"id": "t2", "paid": 0, "price": None},
    ]
    rows = transform_partner_tickets(payload, version=99, ingested_at=datetime(2025, 1, 1, 12, 0, 0))
    assert rows[0]["ticket_id"] == "t1"
    assert rows[0]["paid"] == 1
    assert rows[0]["price"] == 123.45
    assert rows[1]["paid"] == 0
