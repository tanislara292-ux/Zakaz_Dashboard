"""
HTTP client for the official QTickets REST API.

The client provides thin wrappers around the endpoints required by the data
pipeline.  It implements retry/backoff for rate limiting (HTTP 429) and server
errors (5xx), and normalises responses for downstream processing.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urljoin

import requests

from integrations.common.logging import StructuredLogger, setup_integrations_logger
from integrations.common.time import now_msk, to_msk


class QticketsApiError(RuntimeError):
    """Exception carrying structured metadata about QTickets API failures."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id
        self.details = details or {}

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""
        payload: Dict[str, Any] = {
            "message": str(self),
            "status": self.status,
            "code": self.code,
            "request_id": self.request_id,
        }
        payload.update(self.details)
        # Drop empty values for cleaner logs/DB payloads.
        return {k: v for k, v in payload.items() if v not in (None, "")}


class QticketsApiClient:
    """Wrapper around the official QTickets REST API."""

    RETRYABLE_STATUS = {500, 502, 503, 504}

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        logger: Optional[StructuredLogger] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        org_name: Optional[str] = None,
        dry_run: bool = False,
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
        self._token_fingerprint = self._mask_token(token)
        self.org_name = (org_name or "").strip() or None
        self.dry_run = bool(dry_run)
        missing_token = not token or token.strip() == ""
        missing_base_url = not self.base_url
        self.stub_mode = (
            self.dry_run or self.org_name is None or missing_token or missing_base_url
        )

        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient running in stub mode. Requests will not hit the real API.",
                metrics={
                    "org": self.org_name or "<missing_org>",
                    "dry_run": self.dry_run,
                    "missing_token": missing_token,
                    "missing_base_url": missing_base_url,
                },
            )

    # --------------------------------------------------------------------- #
    # Public endpoints
    # --------------------------------------------------------------------- #
    def list_events(self) -> List[Dict[str, Any]]:
        """
        Retrieve the catalogue of events that are not marked as deleted.

        Returns:
            List of raw event payloads provided by the API.
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_events() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []

        filters = [{"column": "deleted_at", "operator": "null"}]
        params = {"where": json.dumps(filters, ensure_ascii=False)}
        payload = self._collect_paginated("events", params=params)
        self.logger.info(
            "Fetched events from QTickets API",
            metrics={"endpoint": "events", "records": len(payload)},
        )
        return payload

    def fetch_orders_get(
        self, date_from: datetime, date_to: datetime
    ) -> List[Dict[str, Any]]:
        """
        Retrieve paid orders via GET request with query parameters.

        This method uses GET with mandatory payed=1 filter
        as required by QTickets API to return actual sales data.

        Args:
            date_from: inclusive lower bound (MSK).
            date_to: exclusive upper bound (MSK).
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.fetch_orders_get() stub for org={self.org_name or '<missing_org>'} "
                f"window=[{date_from} .. {date_to}] -> []"
            )
            return []

        params = {
            "payed": "1",  # Mandatory payed=1 filter
            "organization": self.org_name,
            "limit": "1000",  # Set reasonable page size
        }

        # Add date filters if specified
        if date_from:
            params["since"] = to_msk(date_from).strftime("%Y-%m-%dT%H:%M:%S%z")
        if date_to:
            params["until"] = to_msk(date_to).strftime("%Y-%m-%dT%H:%M:%S%z")

        self.logger.info(
            "Fetching orders via GET with query parameters including payed=1",
            metrics={
                "endpoint": "orders",
                "method": "GET",
                "payed": params.get("payed"),
                "organization": params.get("organization"),
                "date_from": params.get("since"),
                "date_to": params.get("until"),
            },
        )

        payload = self._collect_paginated("orders", params=params)

        # Filter by payed_at locally to ensure exact window matching
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
            "Fetched orders from QTickets API via GET with payed=1 filter",
            metrics={
                "endpoint": "orders",
                "method": "GET",
                "records": len(filtered),
                "raw_records": len(payload),
            },
        )
        return filtered

    def list_orders(
        self, date_from: datetime, date_to: datetime
    ) -> List[Dict[str, Any]]:
        """
        Retrieve paid orders within the requested time window.

        This method now uses GET with query parameters as the primary approach.
        The POST method is kept as fallback for compatibility.

        Args:
            date_from: inclusive lower bound (MSK).
            date_to: exclusive upper bound (MSK).
        """
        try:
            # Try GET method first (preferred for production)
            return self.fetch_orders_get(date_from, date_to)
        except Exception as e:
            self.logger.warning(
                "GET /orders failed, attempting POST fallback",
                metrics={"error": str(e)},
            )
            return self._fetch_orders_post_fallback(date_from, date_to)

    def _fetch_orders_post_fallback(
        self, date_from: datetime, date_to: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fallback method using POST with JSON body (legacy implementation).
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.fetch_orders_post() stub for org={self.org_name or '<missing_org>'} "
                f"window=[{date_from} .. {date_to}] -> []"
            )
            return []

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
            "Fetched orders from QTickets API via POST fallback",
            metrics={
                "endpoint": "orders",
                "records": len(filtered),
                "raw_records": len(payload),
            },
        )
        return filtered

    # ------------------------------------------------------------------ #
    # Backwards-compatible helpers used by legacy code paths
    # ------------------------------------------------------------------ #
    def list_orders_since(self, hours_back: int) -> List[Dict[str, Any]]:
        """Compatibility wrapper mirroring the historical interface."""
        window_end = now_msk()
        window_start = window_end - timedelta(hours=max(1, int(hours_back or 0)))
        return self.fetch_orders_get(window_start, window_end)

    def fetch_orders_since(self, hours_back: int) -> List[Dict[str, Any]]:
        """Alias retained for legacy imports."""
        return self.list_orders_since(hours_back)

    def fetch_inventory_snapshot(self) -> List[Dict[str, Any]]:
        """
        Fetch complete inventory snapshot across all events.

        This method retrieves all events and their seat availability,
        providing a comprehensive snapshot of ticket inventory status.
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.fetch_inventory_snapshot() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []

        try:
            # Get all events
            events = self.list_events()
            if not events:
                self.logger.info("No events found for inventory snapshot")
                return []

            # For each event, get seat information
            inventory_data = []
            for event in events:
                event_id = event.get("id") or event.get("event_id")
                if not event_id:
                    continue

                # Get shows for this event
                shows = self.list_shows(event_id)

                # Aggregate seat data across all shows
                total_seats = 0
                available_seats = 0

                for show in shows:
                    show_id = show.get("show_id") or show.get("id")
                    if not show_id:
                        continue

                    try:
                        seats = self.get_seats(show_id)
                        # Process seat data similar to inventory_agg.py
                        if isinstance(seats, dict) and "data" in seats:
                            zones = seats["data"]
                            for zone_key, zone_data in zones.items():
                                if isinstance(zone_data, dict):
                                    zone_seats = zone_data.get("seats", {})
                                    total_seats += len(zone_seats)
                                    available_seats += sum(
                                        1
                                        for seat_key, seat_info in zone_seats.items()
                                        if isinstance(seat_info, dict)
                                        and seat_info.get("admission") is True
                                    )
                        else:
                            # Fallback processing
                            for seat in seats:
                                if isinstance(seat, dict):
                                    total_seats += 1
                                    if seat.get("admission") is True:
                                        available_seats += 1
                    except Exception as e:
                        self.logger.warning(
                            "Failed to get seats for show",
                            metrics={
                                "event_id": event_id,
                                "show_id": show_id,
                                "error": str(e),
                            },
                        )
                        continue

                # Create inventory record for this event
                inventory_record = {
                    "event_id": str(event_id),
                    "event_name": event.get("name", ""),
                    "city": str(event.get("city", "")).strip().lower(),
                    "snapshot_ts": now_msk().replace(tzinfo=None),
                    "tickets_total": total_seats if total_seats > 0 else None,
                    "tickets_left": available_seats if available_seats > 0 else None,
                }
                inventory_data.append(inventory_record)

            self.logger.info(
                "Built inventory snapshot",
                metrics={"events_processed": len(inventory_data)},
            )
            return inventory_data

        except Exception as e:
            self.logger.error(
                "Failed to fetch inventory snapshot",
                metrics={"error": str(e)},
            )
            raise QticketsApiError(
                f"Failed to fetch inventory snapshot: {e}",
                details={"error": str(e)},
            ) from e

    def list_inventory_snapshot(self) -> List[Dict[str, Any]]:
        """Additional alias kept for backwards compatibility."""
        return self.fetch_inventory_snapshot()

    def list_shows(self, event_id: Any) -> Sequence[Dict[str, Any]]:
        """
        Retrieve shows (sessions) for the given event.

        For now, this method extracts show information from the event payload
        itself, as the QTickets API typically includes show/session data within
        the event object.
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_shows() stub for org={self.org_name or '<missing_org>'} "
                f"event={event_id} -> []"
            )
            return []

        # First, try to get the full event details which may contain shows
        try:
            event_payload = self._request("GET", f"events/{event_id}")
            if isinstance(event_payload, dict):
                # Extract shows from event payload
                shows = []
                candidate_keys = ("shows", "sessions", "seances")

                for key in candidate_keys:
                    shows_data = event_payload.get(key)
                    if isinstance(shows_data, list):
                        for show in shows_data:
                            if isinstance(show, dict):
                                shows.append(show)

                if shows:
                    self.logger.info(
                        "Extracted shows from event payload",
                        metrics={
                            "event_id": event_id,
                            "shows_count": len(shows),
                        },
                    )
                    return shows

                # If no shows found, create a default show from event data
                default_show = {
                    "show_id": event_id,
                    "event_id": event_id,
                    "start_time": event_payload.get("start_time") or event_payload.get("date"),
                    "end_time": event_payload.get("end_time"),
                    "status": event_payload.get("status", "active"),
                }
                self.logger.info(
                    "Created default show from event data",
                    metrics={"event_id": event_id},
                )
                return [default_show]

        except Exception as e:
            self.logger.warning(
                "Failed to extract shows from event payload",
                metrics={"event_id": event_id, "error": str(e)},
            )
            # Fall back to creating a default show
            default_show = {
                "show_id": event_id,
                "event_id": event_id,
                "start_time": None,
                "end_time": None,
                "status": "active",
            }
            return [default_show]

        return []

    def get_seats(self, show_id: Any) -> List[Dict[str, Any]]:
        """
        Retrieve seat availability for a concrete show (session).

        Args:
            show_id: Identifier of the show/session inside QTickets.
        """
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.get_seats() stub for org={self.org_name or '<missing_org>'} "
                f"show={show_id} -> []"
            )
            return []

        response = self._request("GET", f"shows/{show_id}/seats")
        seats = self._extract_items(response)
        self.logger.info(
            "Fetched seats snapshot",
            metrics={
                "endpoint": "shows/{id}/seats",
                "show_id": show_id,
                "records": len(seats),
            },
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
            # Use POST if body is provided, otherwise GET
            method = "POST" if body else "GET"

            if body is not None:
                # For POST requests, include page in the body
                page_body = dict(body)
                if "page" not in page_body:
                    page_body["page"] = page
                payload = self._request(method, path, json_body=page_body)
            else:
                # For GET requests, include page in params
                page_params = dict(params or {})
                if "page" not in page_params:
                    page_params["page"] = page
                payload = self._request(method, path, params=page_params)

            current_items = self._extract_items(payload)
            if not current_items:
                break

            items.extend(current_items)
            if not self._has_next_page(payload, page):
                break
            page += 1

        return items

    def _request_metrics(
        self, method: str, path: str, params: Optional[Dict[str, Any]], body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "method": method.upper(),
            "path": path.lstrip("/"),
        }
        if params:
            metrics["params"] = {k: params[k] for k in sorted(params)}
        if body:
            # Log key info about body but not sensitive data
            body_info = {}
            if "where" in body:
                filters = body["where"]
                if isinstance(filters, list):
                    body_info["filters_count"] = len(filters)
                    body_info["has_payed_filter"] = any(f.get("column") == "payed" for f in filters)
                    # Log column names but not values for security
                    body_info["filter_columns"] = [f.get("column") for f in filters if f.get("column")]
            if "page" in body:
                body_info["page"] = body["page"]
            metrics["body"] = body_info
        metrics["token_fp"] = self._token_fingerprint
        return metrics

    @staticmethod
    def _mask_token(token: Optional[str]) -> str:
        if not token:
            return "<empty>"
        compact = token.strip()
        if len(compact) <= 8:
            return f"{compact[:2]}***"
        return f"{compact[:4]}***{compact[-4:]}"

    def _build_error_context(
        self, path: str, response: requests.Response
    ) -> Dict[str, Any]:
        request_id = (
            response.headers.get("X-Request-ID")
            or response.headers.get("X-Request-Id")
            or response.headers.get("X-Trace-Id")
        )
        body_preview = response.text[:512] if response.text else ""
        message: Optional[str] = None
        code: Optional[str] = None
        payload: Optional[Any] = None

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            raw_code = payload.get("code") or payload.get("error")
            if raw_code is not None:
                code = str(raw_code)
            message = (
                payload.get("message")
                or payload.get("error_description")
                or payload.get("detail")
            )

        return {
            "endpoint": path.lstrip("/"),
            "code": code,
            "message": message or body_preview,
            "request_id": request_id,
            "body_preview": body_preview,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Perform an HTTP request with structured logging and retry/backoff."""
        request_metrics = self._request_metrics(method, path, params, json_body)

        if self.stub_mode:
            self.logger.info(
                "Suppressed HTTP request in stub mode",
                metrics=request_metrics,
            )
            return []

        url = urljoin(self.base_url + "/", path.lstrip("/"))
        headers = dict(self.default_headers)

        last_error: Optional[QticketsApiError] = None
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

                if response.status_code >= 400:
                    error_context = self._build_error_context(path, response)
                    error = QticketsApiError(
                        f"HTTP {response.status_code} for {error_context['endpoint']}",
                        status=response.status_code,
                        code=error_context.get("code"),
                        request_id=error_context.get("request_id"),
                        details={k: v for k, v in error_context.items() if k not in {"endpoint"}},
                    )

                    log_metrics = dict(request_metrics)
                    log_metrics.update(
                        {
                            "http_status": response.status_code,
                            "attempt": attempt,
                            "max_attempts": self.max_retries,
                            "code": error_context.get("code"),
                            "request_id": error_context.get("request_id"),
                            "body_preview": error_context.get("body_preview"),
                        }
                    )

                    if response.status_code in self.RETRYABLE_STATUS and attempt < self.max_retries:
                        self.logger.warning(
                            "Transient QTickets API error",
                            metrics=log_metrics,
                        )
                        last_error = error
                        self._sleep(attempt, error)
                        continue

                    self.logger.error(
                        "QTickets API request failed",
                        metrics=log_metrics,
                    )
                    raise error

                if not response.content:
                    return None

                try:
                    return response.json()
                except ValueError as err:
                    body_preview = response.text[:512]
                    raise QticketsApiError(
                        "Invalid JSON response",
                        status=response.status_code,
                        details={"body_preview": body_preview, **request_metrics},
                    ) from err

            except requests.RequestException as err:
                log_metrics = dict(request_metrics)
                log_metrics.update(
                    {
                        "attempt": attempt,
                        "max_attempts": self.max_retries,
                        "error": err.__class__.__name__,
                    }
                )
                self.logger.warning(
                    "Network error during QTickets API request",
                    metrics=log_metrics,
                )
                last_error = QticketsApiError(
                    f"Network error while calling {path}: {err}",
                    details={"error": err.__class__.__name__},
                )
                if attempt < self.max_retries:
                    self._sleep(attempt, err)
                    continue
            else:
                # Successful response or JSON parsed, break out of retry loop.
                break

        if last_error:
            raise last_error

        raise QticketsApiError(
            f"QTickets API request failed after {self.max_retries} attempts: {path}",
            details=request_metrics,
        )

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
