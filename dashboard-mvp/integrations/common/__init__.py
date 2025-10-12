"""
Общие утилиты для интеграций.
"""

from .ch import ClickHouseClient, get_client
from .time import (
    now_msk, today_msk, to_msk, to_date, date_range, days_ago,
    format_msk, is_weekend, parse_period
)
from .utm import (
    normalize_city, parse_utm_content, extract_utm_params,
    build_utm_content, validate_utm_content
)
from .logging import (
    StructuredLogger, Metrics, get_logger, log_execution_time,
    log_data_operation, setup_integrations_logger
)

__all__ = [
    # ClickHouse
    'ClickHouseClient',
    'get_client',
    
    # Time utilities
    'now_msk',
    'today_msk',
    'to_msk',
    'to_date',
    'date_range',
    'days_ago',
    'format_msk',
    'is_weekend',
    'parse_period',
    
    # UTM utilities
    'normalize_city',
    'parse_utm_content',
    'extract_utm_params',
    'build_utm_content',
    'validate_utm_content',
    
    # Logging utilities
    'StructuredLogger',
    'Metrics',
    'get_logger',
    'log_execution_time',
    'log_data_operation',
    'setup_integrations_logger'
]