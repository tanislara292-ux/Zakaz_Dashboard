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
        partners_base_url: Optional[str] = None,
        partners_token: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logger or setup_integrations_logger("qtickets_api")

        token_value = (token or "").strip()
        self.default_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token_value}",
        }
        self._token_fingerprint = self._mask_token(token_value)

        partners_token_value = (partners_token or "").strip() or token_value
        partners_base = (partners_base_url or "").strip().rstrip("/") or None
        self.partners_base_url = partners_base
        self.partners_headers: Optional[Dict[str, str]] = None
        if partners_base:
            self.partners_headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {partners_token_value}",
            }
        self._partners_token_fingerprint = self._mask_token(partners_token_value)

        self.org_name = (org_name or "").strip() or None
        self.dry_run = bool(dry_run)
        missing_token = not token_value
        missing_base_url = not self.base_url
        self.stub_mode = (
            self.dry_run or self.org_name is None or missing_token or missing_base_url
        )
        self.partners_ready = bool(self.partners_base_url and self.partners_headers)

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

        filters = self._build_orders_filters(date_from, date_to)
        order_by = {"payed_at": "desc"}
        body: Dict[str, Any] = {
            "where": filters,
            "orderBy": order_by,
            "per_page": 200,
        }
        if self.org_name:
            body["organization"] = self.org_name

        self.logger.info(
            "Fetching orders via GET with JSON body",
            metrics={
                "endpoint": "orders",
                "method": "GET",
                "filters": filters,
                "order_by": order_by,
            },
        )

        payload = self._collect_paginated(
            "orders",
            method="GET",
            json_body=body,
        )

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
            "Fetched orders from QTickets API via GET",
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

        filters = self._build_orders_filters(date_from, date_to)
        order_by = {"payed_at": "desc"}
        body: Dict[str, Any] = {
            "where": filters,
            "orderBy": order_by,
            "per_page": 200,
        }
        if self.org_name:
            body["organization"] = self.org_name

        self.logger.info(
            "Fetching orders via POST fallback with JSON body",
            metrics={
                "endpoint": "orders",
                "method": "POST",
                "filters": filters,
                "order_by": order_by,
            },
        )

        payload = self._collect_paginated(
            "orders",
            method="POST",
            json_body=body,
        )

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
                "method": "POST",
                "records": len(filtered),
                "raw_records": len(payload),
            },
        )
        return filtered

    def _build_orders_filters(
        self, date_from: datetime, date_to: datetime
    ) -> List[Dict[str, Any]]:
        filters: List[Dict[str, Any]] = [{"column": "payed", "value": 1}]
        if date_from:
            filters.append(
                {
                    "column": "payed_at",
                    "operator": ">=",
                    "value": self._format_datetime_for_api(date_from),
                }
            )
        if date_to:
            filters.append(
                {
                    "column": "payed_at",
                    "operator": "<",
                    "value": self._format_datetime_for_api(date_to),
                }
            )
        return filters

    # ------------------------------------------------------------------ #
    # Backwards-compatible helpers used by legacy code paths
    # ------------------------------------------------------------------ #
    def list_orders_since(self, hours_back: int) -> List[Dict[str, Any]]:
        """Compatibility wrapper mirroring the historical interface."""
        window_end = now_msk()
        window_start = window_end - timedelta(hours=max(1, int(hours_back or 0)))
        return self.list_orders(window_start, window_end)

    def get_order(self, order_id: Any) -> Dict[str, Any]:
        """Retrieve a single order payload from `/orders/{id}`."""
        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient.get_order() stub mode",
                metrics={"order_id": order_id},
            )
            return {}
        payload = self._request("GET", f"orders/{order_id}")
        order = self._extract_single_item(payload)
        self.logger.info(
            "Fetched specific order from QTickets API",
            metrics={"endpoint": "orders/{id}", "order_id": order_id},
        )
        return order

    def list_clients(self, *, per_page: int = 200) -> List[Dict[str, Any]]:
        """Retrieve all clients accessible to the organisation."""
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_clients() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []
        body = {"per_page": per_page}
        payload = self._collect_paginated(
            "clients",
            method="GET",
            json_body=body,
        )
        self.logger.info(
            "Fetched clients from QTickets API",
            metrics={"endpoint": "clients", "records": len(payload)},
        )
        return payload

    def get_client(self, client_id: Any) -> Dict[str, Any]:
        """Retrieve a single client payload."""
        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient.get_client() stub mode",
                metrics={"client_id": client_id},
            )
            return {}
        payload = self._request("GET", f"clients/{client_id}")
        client = self._extract_single_item(payload)
        self.logger.info(
            "Fetched specific client from QTickets API",
            metrics={"endpoint": "clients/{id}", "client_id": client_id},
        )
        return client

    def list_price_shades(self) -> List[Dict[str, Any]]:
        """Retrieve configured price shade catalog."""
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_price_shades() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []
        payload = self._collect_paginated("price-shades")
        self.logger.info(
            "Fetched price shades from QTickets API",
            metrics={"endpoint": "price-shades", "records": len(payload)},
        )
        return payload

    def list_discounts(self) -> List[Dict[str, Any]]:
        """Retrieve discount definitions."""
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_discounts() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []
        payload = self._collect_paginated("discounts")
        self.logger.info(
            "Fetched discounts from QTickets API",
            metrics={"endpoint": "discounts", "records": len(payload)},
        )
        return payload

    def list_promo_codes(self) -> List[Dict[str, Any]]:
        """Retrieve promo code catalogue."""
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_promo_codes() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []
        payload = self._collect_paginated("promo-codes")
        self.logger.info(
            "Fetched promo codes from QTickets API",
            metrics={"endpoint": "promo-codes", "records": len(payload)},
        )
        return payload

    def list_barcodes(
        self,
        *,
        filters: Optional[List[Dict[str, Any]]] = None,
        per_page: int = 200,
    ) -> List[Dict[str, Any]]:
        """Retrieve ticket barcodes with optional filters."""
        if self.stub_mode:
            self.logger.warning(
                f"QticketsApiClient.list_barcodes() stub for org={self.org_name or '<missing_org>'} -> []"
            )
            return []
        body: Dict[str, Any] = {"per_page": per_page}
        if filters:
            body["where"] = filters
        payload = self._collect_paginated(
            "barcodes",
            method="GET",
            json_body=body,
        )
        self.logger.info(
            "Fetched barcodes from QTickets API",
            metrics={"endpoint": "barcodes", "records": len(payload)},
        )
        return payload

    def get_barcode(self, barcode: Any) -> Dict[str, Any]:
        """Retrieve barcode scan metadata."""
        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient.get_barcode() stub mode",
                metrics={"barcode": barcode},
            )
            return {}
        payload = self._request("GET", f"barcodes/{barcode}")
        entry = self._extract_single_item(payload)
        self.logger.info(
            "Fetched barcode details from QTickets API",
            metrics={"endpoint": "barcodes/{id}", "barcode": barcode},
        )
        return entry

    def list_event_seats(self, event_id: Any) -> Dict[str, Any]:
        """Fetch seat map for the event via REST API."""
        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient.list_event_seats() stub mode",
                metrics={"event_id": event_id},
            )
            return {}
        payload = self._request("GET", f"events/{event_id}/seats")
        self.logger.info(
            "Fetched event level seats",
            metrics={"endpoint": "events/{id}/seats", "event_id": event_id},
        )
        return payload or {}

    def get_event_show_seats(self, event_id: Any, show_id: Any) -> Dict[str, Any]:
        """Fetch seat map for a concrete show via REST API."""
        if self.stub_mode:
            self.logger.warning(
                "QticketsApiClient.get_event_show_seats() stub mode",
                metrics={"event_id": event_id, "show_id": show_id},
            )
            return {}
        payload = self._request("GET", f"events/{event_id}/seats/{show_id}")
        self.logger.info(
            "Fetched show level seats",
            metrics={
                "endpoint": "events/{id}/seats/{show_id}",
                "event_id": event_id,
                "show_id": show_id,
            },
        )
        return payload or {}

    def partners_event_seats(
        self, event_id: Any, show_id: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Fetch seat map via the partners API."""
        if not self.partners_ready:
            self.logger.warning(
                "Partners seat request skipped: configuration incomplete",
                metrics={
                    "event_id": event_id,
                    "show_id": show_id,
                    "partners_base_url": self.partners_base_url,
                },
            )
            return {}

        path = f"events/seats/{event_id}"
        if show_id is not None:
            path = f"{path}/{show_id}"
        payload = self._request(
            "GET",
            path,
            base_url=self.partners_base_url,
            headers=self.partners_headers,
            api_label="partners",
            token_fp=self._partners_token_fingerprint,
        )
        self.logger.info(
            "Fetched partner seat snapshot",
            metrics={
                "endpoint": "partners.events.seats",
                "event_id": event_id,
                "show_id": show_id,
            },
        )
        return payload or {}

    def find_partner_tickets(
        self,
        *,
        filter_payload: Dict[str, Any],
        event_id: Optional[Any] = None,
        show_id: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Search partner tickets by external identifiers."""
        if not filter_payload:
            raise ValueError("filter_payload must not be empty for partner ticket search")
        if not self.partners_ready:
            self.logger.warning(
                "Partner ticket search skipped: configuration incomplete",
                metrics={
                    "event_id": event_id,
                    "show_id": show_id,
                    "partners_base_url": self.partners_base_url,
                },
            )
            return []

        if event_id is not None and show_id is not None:
            path = f"tickets/find/{event_id}/{show_id}"
        elif event_id is not None:
            path = f"tickets/find/{event_id}"
        else:
            path = "tickets/find"

        payload = self._request(
            "POST",
            path,
            json_body={"filter": filter_payload},
            base_url=self.partners_base_url,
            headers=self.partners_headers,
            api_label="partners",
            token_fp=self._partners_token_fingerprint,
        )
        records = self._extract_items(payload)
        self.logger.info(
            "Executed partner ticket search",
            metrics={
                "endpoint": "partners.tickets.find",
                "records": len(records),
                "event_id": event_id,
                "show_id": show_id,
                "filter_keys": sorted(filter_payload.keys()),
            },
        )
        return records

    @staticmethod
    def _format_datetime_for_api(value: datetime) -> str:
        """Render MSK datetimes in ISO-8601 with colon in the UTC offset (+03:00)."""
        dt = to_msk(value)
        # Some QTickets environments ignore filters with compact offsets like +0300,
        # therefore we normalise everything to +03:00 form even if strftime omits
        # the colon.
        formatted = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        if len(formatted) > 5 and formatted[-3] != ":":
            return f"{formatted[:-2]}:{formatted[-2:]}"
        return formatted

    def fetch_orders_since(self, hours_back: int) -> List[Dict[str, Any]]:
        """Alias retained for legacy imports."""
        return self.list_orders_since(hours_back)


    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _collect_paginated(
        self,
        path: str,
        *,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Collect all pages for an endpoint that supports pagination."""
        items: List[Dict[str, Any]] = []
        page = 1

        verb = (method or "GET").upper()
        while True:
            page_params = dict(params or {})
            page_body = dict(json_body) if json_body is not None else None

            if page_body is not None and "page" not in page_body:
                page_body["page"] = page
            if page_body is None and "page" not in page_params:
                page_params["page"] = page

            payload = self._request(
                verb,
                path,
                params=page_params or None,
                json_body=page_body,
                base_url=base_url,
                headers=headers,
            )

            current_items = self._extract_items(payload)
            if not current_items:
                break

            items.extend(current_items)
            if not self._has_next_page(payload, page):
                break
            page += 1

        return items

    def _request_metrics(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]],
        body: Optional[Dict[str, Any]] = None,
        *,
        api_label: str = "rest",
        token_fp: Optional[str] = None,
    ) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "method": method.upper(),
            "path": path.lstrip("/"),
            "api": api_label,
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
        metrics["token_fp"] = token_fp or self._token_fingerprint
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
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        api_label: Optional[str] = None,
        token_fp: Optional[str] = None,
    ) -> Any:
        """Perform an HTTP request with structured logging and retry/backoff."""
        api_name = api_label or ("partners" if base_url and base_url != self.base_url else "rest")
        request_metrics = self._request_metrics(
            method, path, params, json_body, api_label=api_name, token_fp=token_fp
        )

        if self.stub_mode:
            self.logger.info(
                "Suppressed HTTP request in stub mode",
                metrics=request_metrics,
            )
            return []

        base = (base_url or self.base_url).rstrip("/")
        url = urljoin(base + "/", path.lstrip("/"))
        header_bucket = dict(headers or self.default_headers)
        effective_token_fp = token_fp or (
            self._partners_token_fingerprint if api_name == "partners" else self._token_fingerprint
        )
        request_metrics["token_fp"] = effective_token_fp

        last_error: Optional[QticketsApiError] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=header_bucket,
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

    def _extract_single_item(self, payload: Any) -> Dict[str, Any]:
        """Extract a single object from API responses that wrap data arrays."""
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        return item
            if isinstance(data, dict):
                return data
            return payload
        return {}

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
