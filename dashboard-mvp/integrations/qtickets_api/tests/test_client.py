"""Tests for the Qtickets API client request/ retry behaviour."""

from __future__ import annotations

import json
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
    client = QticketsApiClient(base_url="https://qtickets.test", token="secret")
    response = _make_response(403, {"code": "forbidden", "message": "Forbidden"})

    mocked_request = MagicMock(return_value=response)
    monkeypatch.setattr(client.session, "request", mocked_request)

    with pytest.raises(QticketsApiError) as exc:
        client.fetch_orders_get(now_msk(), now_msk())

    assert exc.value.status == 403
    assert mocked_request.call_count == 1


def test_request_retries_and_succeeds_on_server_errors(monkeypatch):
    client = QticketsApiClient(base_url="https://qtickets.test", token="secret")

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
