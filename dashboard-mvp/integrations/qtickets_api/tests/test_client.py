"""Tests for the Qtickets API client request/ retry behaviour."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import List
from unittest.mock import MagicMock

import pytest
import requests

from integrations.common.time import now_msk
from integrations.qtickets_api.client import QticketsApiClient, QticketsApiError


def _make_response(status: int, payload: dict | List[dict] | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = "https://qtickets.test/api"
    response.headers["Content-Type"] = "application/json"
    if payload is None:
        response._content = b""
    else:
        response._content = json.dumps(payload).encode("utf-8")
    response.request = requests.Request("GET", response.url).prepare()
    return response


def test_request_does_not_retry_non_retryable_status(monkeypatch):
    client = QticketsApiClient(base_url="https://qtickets.test", token="secret", org_name="test-org")
    response = _make_response(403, {"code": "forbidden", "message": "Forbidden"})

    mocked_request = MagicMock(return_value=response)
    monkeypatch.setattr(client.session, "request", mocked_request)

    with pytest.raises(QticketsApiError) as exc:
        client.fetch_orders_get(now_msk(), now_msk())

    assert exc.value.status == 403
    assert mocked_request.call_count == 1


def test_request_retries_and_succeeds_on_server_errors(monkeypatch):
    client = QticketsApiClient(base_url="https://qtickets.test", token="secret", org_name="test-org")

    failure = _make_response(502, {"code": "bad_gateway"})
    success = _make_response(200, {"data": []})

    mocked_request = MagicMock(side_effect=[failure, failure, success])
    monkeypatch.setattr(client.session, "request", mocked_request)

    result = client.fetch_orders_get(now_msk(), now_msk())

    assert result == []
    assert mocked_request.call_count == 3


def test_stub_mode_short_circuits_requests(monkeypatch):
    client = QticketsApiClient(
        base_url="https://qtickets.test",
        token="secret",
        dry_run=True,
    )

    mocked_request = MagicMock()
    monkeypatch.setattr(client.session, "request", mocked_request)

    assert client.list_events() == []
    assert mocked_request.call_count == 0


def test_fetch_orders_get_includes_payed_filter(monkeypatch):
    """Test that fetch_orders_get includes mandatory payed=1 filter in GET query parameters."""
    client = QticketsApiClient(base_url="https://qtickets.test", token="secret", org_name="test-org")

    # Mock successful response with some orders
    response = _make_response(200, {"data": [
        {"id": 1, "payed_at": "2023-01-01T10:00:00", "amount": 1000},
        {"id": 2, "payed_at": "2023-01-01T11:00:00", "amount": 1500}
    ]})

    mocked_request = MagicMock(return_value=response)
    monkeypatch.setattr(client.session, "request", mocked_request)

    date_from = now_msk()
    date_to = date_from + timedelta(hours=1)

    result = client.fetch_orders_get(date_from, date_to)

    # Verify that GET request was made (not POST)
    assert mocked_request.call_count == 1
    call_args = mocked_request.call_args
    method = call_args[0][0]  # First positional argument is the method
    assert method == "GET"

    # Verify that query parameters contain the mandatory payed=1 filter
    call_kwargs = call_args[1]
    params = call_kwargs.get("params", {})
    assert "where" in params
    assert "orderBy" in params
    assert "per_page" in params

    # Parse the where JSON string
    where_str = params["where"]
    where_filters = json.loads(where_str)
    assert isinstance(where_filters, list)

    # Check that payed=1 filter is present
    payed_filter = next((f for f in where_filters if f.get("column") == "payed"), None)
    assert payed_filter is not None
    assert payed_filter["value"] == 1

    # Verify that pagination and ordering are included
    order_by_str = params["orderBy"]
    order_by = json.loads(order_by_str)
    assert order_by == {"payed_at": "desc"}
    assert params.get("per_page") == 200

    # Check that date filters are present and rendered in ISO format
    date_filters = [f for f in where_filters if f.get("column") == "payed_at"]
    assert len(date_filters) == 2
    operators = {f.get("operator") for f in date_filters}
    assert operators == {">=", "<"}
    for f in date_filters:
        assert "value" in f
        assert "T" in f["value"]  # ISO 8601 timestamp
