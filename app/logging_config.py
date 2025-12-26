# app/logging_config.py
"""
Centralized logging configuration for the Invoice POC application.

This module provides a consistent logging setup across all modules.
Import and call setup_logging() early in application startup (e.g., in main.py).
"""
import logging
import os
import sys

# Default log format with timestamp, level, module, and message
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default log level (can be overridden via LOG_LEVEL env var)
DEFAULT_LEVEL = logging.INFO

# Map string log level names to logging constants
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _get_log_level_from_env() -> int:
    """
    Get log level from LOG_LEVEL environment variable.

    Returns:
        Logging level constant (e.g., logging.INFO)
    """
    env_level = os.environ.get("LOG_LEVEL", "").upper()
    if env_level in LOG_LEVEL_MAP:
        return LOG_LEVEL_MAP[env_level]
    return DEFAULT_LEVEL


def setup_logging(level: int = None, format_str: str = None) -> None:
    """
    Configure the root logger with consistent formatting.

    This should be called once at application startup before any other logging occurs.

    Args:
        level: Logging level (default: from LOG_LEVEL env var, or INFO if not set)
        format_str: Log format string (default: DEFAULT_FORMAT)
    """
    if level is None:
        level = _get_log_level_from_env()

    if format_str is None:
        format_str = DEFAULT_FORMAT

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt=DEFAULT_DATE_FORMAT,
        stream=sys.stdout,
        force=True  # Override any existing configuration
    )

    # Set level for our application loggers
    logging.getLogger("app").setLevel(level)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log that logging is configured (useful for verifying setup)
    logger = logging.getLogger(__name__)
    logger.info("Logging configured: level=%s", logging.getLevelName(level))


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Usage:
        from app.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
