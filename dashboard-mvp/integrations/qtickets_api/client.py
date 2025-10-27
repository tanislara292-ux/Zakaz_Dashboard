"""
HTTP client for the official QTickets REST API.

The client provides thin wrappers around the endpoints required by the data
pipeline.  It implements retry/backoff for rate limiting (HTTP 429) and server
errors (5xx), and normalises responses for downstream processing.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urljoin

import requests

from integrations.common.logging import StructuredLogger, setup_integrations_logger
from integrations.common.time import to_msk


class QticketsApiError(RuntimeError):
    """Base exception for QTickets API failures."""


class QticketsApiClient:
    """Wrapper around the official QTickets REST API."""

    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        logger: Optional[StructuredLogger] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logger or setup_integrations_logger("qtickets_api")
        self.default_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # --------------------------------------------------------------------- #
    # Public endpoints
    # --------------------------------------------------------------------- #
    def list_events(self) -> List[Dict[str, Any]]:
        """
        Retrieve the catalogue of events that are not marked as deleted.

        Returns:
            List of raw event payloads provided by the API.
        """
        filters = [{"column": "deleted_at", "operator": "null"}]
        params = {"where": json.dumps(filters, ensure_ascii=False)}
        payload = self._collect_paginated("events", params=params)
        self.logger.info(
            "Fetched events from QTickets API",
            metrics={"endpoint": "events", "records": len(payload)},
        )
        return payload

    def list_orders(self, date_from: datetime, date_to: datetime) -> List[Dict[str, Any]]:
        """
        Retrieve paid orders within the requested time window.

        Args:
            date_from: inclusive lower bound (MSK).
            date_to: exclusive upper bound (MSK).
        """
        filters: List[Dict[str, Any]] = [{"column": "payed", "value": 1}]
        if date_from:
            filters.append(
                {
                    "column": "payed_at",
                    "operator": ">=",
                    "value": to_msk(date_from).isoformat(),
                }
            )
        if date_to:
            filters.append(
                {
                    "column": "payed_at",
                    "operator": "<",
                    "value": to_msk(date_to).isoformat(),
                }
            )

        params = {"where": json.dumps(filters, ensure_ascii=False)}
        payload = self._collect_paginated("orders", params=params)

        # Ensure only orders with payed_at inside the requested window remain.
        filtered: List[Dict[str, Any]] = []
        for order in payload:
            payed_at = order.get("payed_at")
            if not payed_at:
                continue
            try:
                payed_dt = to_msk(payed_at)
            except Exception:
                # Keep the record – the transformer will decide how to handle it.
                filtered.append(order)
                continue

            if date_from and payed_dt < to_msk(date_from):
                continue
            if date_to and payed_dt >= to_msk(date_to):
                continue
            filtered.append(order)

        self.logger.info(
            "Fetched orders from QTickets API",
            metrics={
                "endpoint": "orders",
                "records": len(filtered),
                "raw_records": len(payload),
            },
        )
        return filtered

    def list_shows(self, event_id: Any) -> Sequence[Dict[str, Any]]:
        """
        Retrieve shows (sessions) for the given event.

        The API documentation did not expose a dedicated endpoint during the
        initial integration scope.  The method is left as a placeholder so that
        once the endpoint is clarified it can be implemented without touching
        downstream code.
        """
        raise NotImplementedError(
            "The QTickets API documentation does not define an endpoint for "
            "listing shows per event. Contact the vendor to clarify how show_id "
            "should be retrieved for inventory snapshots."
        )

    def get_seats(self, show_id: Any) -> List[Dict[str, Any]]:
        """
        Retrieve seat availability for a concrete show (session).

        Args:
            show_id: Identifier of the show/session inside QTickets.
        """
        response = self._request("GET", f"shows/{show_id}/seats")
        seats = self._extract_items(response)
        self.logger.info(
            "Fetched seats snapshot",
            metrics={"endpoint": "shows/{id}/seats", "show_id": show_id, "records": len(seats)},
        )
        return seats

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _collect_paginated(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Collect all pages for an endpoint that supports pagination."""
        items: List[Dict[str, Any]] = []
        page = 1

        while True:
            page_params = dict(params or {})
            if "page" not in page_params:
                page_params["page"] = page

            payload = self._request("GET", path, params=page_params, json_body=body)
            current_items = self._extract_items(payload)
            if not current_items:
                break

            items.extend(current_items)
            if not self._has_next_page(payload, page):
                break
            page += 1

        return items

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Perform an HTTP request with retry/backoff."""
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        headers = dict(self.default_headers)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code in self.RETRYABLE_STATUS:
                    raise QticketsApiError(
                        f"Temporary HTTP {response.status_code} for {url}: {response.text}"
                    )

                response.raise_for_status()

                if not response.content:
                    return None

                try:
                    return response.json()
                except ValueError as err:
                    raise QticketsApiError(f"Invalid JSON response from {url}") from err

            except QticketsApiError as err:
                last_error = err
                self._sleep(attempt, err)
            except requests.RequestException as err:
                last_error = err
                self._sleep(attempt, err)

        message = f"QTickets API request failed after {self.max_retries} attempts: {url}"
        if last_error:
            message = f"{message} ({last_error})"
        raise QticketsApiError(message)

    def _sleep(self, attempt: int, error: Exception) -> None:
        """Sleep with exponential backoff and log the retry."""
        wait = self.backoff_factor * (2 ** (attempt - 1))
        self.logger.warning(
            "Temporary QTickets API error, backing off",
            metrics={
                "attempt": attempt,
                "max_attempts": self.max_retries,
                "sleep_seconds": wait,
                "error": str(error),
            },
        )
        time.sleep(wait)

    def _extract_items(self, payload: Any) -> List[Dict[str, Any]]:
        """Normalise the API payload into a list of dictionaries."""
        if payload is None:
            return []

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                return [item for item in payload["data"] if isinstance(item, dict)]
            if isinstance(payload.get("results"), list):
                return [item for item in payload["results"] if isinstance(item, dict)]

        return []

    def _has_next_page(self, payload: Any, current_page: int) -> bool:
        """Inspect metadata to decide whether more pages should be requested."""
        if not isinstance(payload, dict):
            return False

        meta = payload.get("meta")
        if isinstance(meta, dict):
            if "has_next" in meta:
                return bool(meta["has_next"])
            if "next_page" in meta:
                return meta["next_page"] is not None
            if "page" in meta and "total_pages" in meta:
                try:
                    return int(meta["page"]) < int(meta["total_pages"])
                except (TypeError, ValueError):
                    return False

        links = payload.get("links")
        if isinstance(links, dict) and links.get("next"):
            return True

        # Fallback: stop pagination if the endpoint does not provide explicit metadata.
        return False
