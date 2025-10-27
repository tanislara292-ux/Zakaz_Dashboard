"""Public exports for the ``integrations.common`` convenience package."""

from .ch import ClickHouseClient, get_client, get_client_from_config
from .logging import (
    Metrics,
    StructuredLogger,
    get_logger,
    log_data_operation,
    log_execution_time,
    setup_integrations_logger,
)
from .time import (
    date_range,
    days_ago,
    format_msk,
    is_weekend,
    now_msk,
    parse_period,
    to_date,
    to_msk,
    today_msk,
    utcnow,
)
from .utm import (
    build_utm_content,
    extract_utm_params,
    normalize_city,
    parse_utm_content,
    validate_utm_content,
)

__all__ = [
    # ClickHouse helpers
    "ClickHouseClient",
    "get_client",
    "get_client_from_config",
    # Time helpers
    "utcnow",
    "now_msk",
    "today_msk",
    "to_msk",
    "to_date",
    "date_range",
    "days_ago",
    "format_msk",
    "is_weekend",
    "parse_period",
    # UTM helpers
    "normalize_city",
    "parse_utm_content",
    "extract_utm_params",
    "build_utm_content",
    "validate_utm_content",
    # Logging helpers
    "StructuredLogger",
    "Metrics",
    "get_logger",
    "log_execution_time",
    "log_data_operation",
    "setup_integrations_logger",
]
