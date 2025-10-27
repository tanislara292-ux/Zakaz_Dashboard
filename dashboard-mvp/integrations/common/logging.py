"""Lightweight logging helpers shared across integrations."""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, Optional, Protocol, TypeVar

__all__ = [
    "Metrics",
    "StructuredLogger",
    "get_logger",
    "setup_integrations_logger",
    "log_execution_time",
    "log_data_operation",
]

Metrics = Dict[str, Any]

_LOGGER_CONFIGURED = False


class StructuredLogger(logging.Logger):
    """Logger that supports optional ``metrics`` keyword argument."""

    def _attach_metrics(self, message: str, metrics: Optional[Metrics]) -> str:
        if not metrics:
            return message
        try:
            serialized = json.dumps(metrics, ensure_ascii=False, default=str)
        except TypeError:
            serialized = str(metrics)
        return f"{message} | metrics={serialized}"

    def debug(self, msg: str, *args: Any, metrics: Optional[Metrics] = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().debug(self._attach_metrics(msg, metrics), *args, **kwargs)

    def info(self, msg: str, *args: Any, metrics: Optional[Metrics] = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().info(self._attach_metrics(msg, metrics), *args, **kwargs)

    def warning(self, msg: str, *args: Any, metrics: Optional[Metrics] = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().warning(self._attach_metrics(msg, metrics), *args, **kwargs)

    def error(self, msg: str, *args: Any, metrics: Optional[Metrics] = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().error(self._attach_metrics(msg, metrics), *args, **kwargs)

    def critical(self, msg: str, *args: Any, metrics: Optional[Metrics] = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().critical(self._attach_metrics(msg, metrics), *args, **kwargs)


def _configure_root_logger() -> None:
    """Initialise root logger to emit ISO timestamps to stdout."""
    global _LOGGER_CONFIGURED  # pylint: disable=global-statement

    if _LOGGER_CONFIGURED:
        return

    logging.setLoggerClass(StructuredLogger)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)sZ %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime  # type: ignore[attr-defined]
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    level_name = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)  # type: ignore[attr-defined]
    root.setLevel(level_name if isinstance(level_name, int) else logging.INFO)

    _LOGGER_CONFIGURED = True


def get_logger(name: str) -> StructuredLogger:
    """Return a configured structured logger."""
    _configure_root_logger()
    logger = logging.getLogger(name)
    logger.propagate = False
    return logger  # type: ignore[return-value]


def setup_integrations_logger(name: str, log_file: Optional[str] = None) -> StructuredLogger:
    """
    Backwards-compatible helper used across integrations for consistent logging.

    ``log_file`` argument is accepted for compatibility but ignored (we log to stdout).
    """
    return get_logger(name)


F = TypeVar("F", bound=Callable[..., Any])


def log_execution_time(logger: StructuredLogger) -> Callable[[F], F]:
    """Decorator that measures execution time and logs it on completion."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any):  # type: ignore[override]
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                logger.info(
                    "Execution finished",
                    metrics={
                        "function": func.__name__,
                        "duration_seconds": round(duration, 4),
                    },
                )

        return wrapper  # type: ignore[return-value]

    return decorator


class _CallableWithRows(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def log_data_operation(
    logger: StructuredLogger,
    operation: str,
    source: str,
    target: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that logs start/end metadata for data movement steps."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            start = time.time()
            logger.info(
                "Starting data operation",
                metrics={
                    "operation": operation,
                    "source": source,
                    "target": target,
                    "function": func.__name__,
                },
            )
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                row_count = None
                if isinstance(result, (list, tuple, set)):
                    row_count = len(result)
                elif isinstance(result, dict) and "rows" in result:
                    try:
                        row_count = len(result["rows"])  # type: ignore[arg-type]
                    except TypeError:
                        row_count = result.get("rows")

                logger.info(
                    "Finished data operation",
                    metrics={
                        "operation": operation,
                        "source": source,
                        "target": target,
                        "function": func.__name__,
                        "duration_seconds": round(duration, 4),
                        "rows": row_count,
                    },
                )
                return result
            except Exception:  # pylint: disable=broad-except
                duration = time.time() - start
                logger.error(
                    "Data operation failed",
                    metrics={
                        "operation": operation,
                        "source": source,
                        "target": target,
                        "function": func.__name__,
                        "duration_seconds": round(duration, 4),
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
