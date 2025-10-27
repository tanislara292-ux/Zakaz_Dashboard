"""
QTickets REST API integration package.

This module provides the building blocks required to ingest sales and inventory
data from the official QTickets API into ClickHouse.
"""

from .config import QticketsApiConfig
from .client import QticketsApiClient

__all__ = [
    "QticketsApiConfig",
    "QticketsApiClient",
]
