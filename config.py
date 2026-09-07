"""
Central configuration for the Biomedical AI MCP project.

Configuration is controlled through environment variables with safe
development defaults.

Environment variables:
    BIOMED_MCP_SERVER_COMMAND
    BIOMED_MCP_SERVER_SCRIPT
    BIOMED_DEFAULT_DOCUMENT_ID
    BIOMED_RESEARCH_TOP_K
    BIOMED_MAX_QUESTION_LENGTH
    BIOMED_LOG_LEVEL
    BIOMED_DATABASE_PATH
    BIOMED_DOCUMENTS_DIR
"""

import logging
import os
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = Path(
    os.getenv(
        "BIOMED_DATABASE_PATH",
        str(BASE_DIR / "biomedical.db"),
    )
).resolve()

DOCUMENTS_DIR = Path(
    os.getenv(
        "BIOMED_DOCUMENTS_DIR",
        str(BASE_DIR / "documents"),
    )
).resolve()


# ============================================================
# MCP SERVER CONFIGURATION
# ============================================================

MCP_SERVER_COMMAND = os.getenv(
    "BIOMED_MCP_SERVER_COMMAND",
    "python",
).strip()

MCP_SERVER_SCRIPT = os.getenv(
    "BIOMED_MCP_SERVER_SCRIPT",
    "server.py",
).strip()


# ============================================================
# RESEARCH CONFIGURATION
# ============================================================

DEFAULT_DOCUMENT_ID = os.getenv(
    "BIOMED_DEFAULT_DOCUMENT_ID",
    "DOC001",
).strip()


def _read_positive_int(
    environment_name: str,
    default: int,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    """
    Read an integer environment variable safely.

    Invalid, missing, or out-of-range values return the supplied
    default instead of causing application startup to fail.
    """

    raw_value = os.getenv(environment_name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    if value < minimum:
        return default

    if maximum is not None and value > maximum:
        return default

    return value


# RESEARCH_TOP_K intentionally allows 0 because the existing
# project configuration contract accepts that value.
RESEARCH_TOP_K = _read_positive_int(
    "BIOMED_RESEARCH_TOP_K",
    default=5,
    minimum=0,
    maximum=20,
)


# ============================================================
# INPUT CONFIGURATION
# ============================================================

MAX_QUESTION_LENGTH = _read_positive_int(
    "BIOMED_MAX_QUESTION_LENGTH",
    default=2000,
    minimum=1,
    maximum=10000,
)


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

LOG_LEVEL = os.getenv(
    "BIOMED_LOG_LEVEL",
    "INFO",
).strip().upper()

_ALLOWED_LOG_LEVELS = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}

if LOG_LEVEL not in _ALLOWED_LOG_LEVELS:
    LOG_LEVEL = "INFO"


def configure_logging() -> None:
    """
    Configure application-wide logging from LOG_LEVEL.

    This function is intentionally idempotent: calling it multiple
    times does not add duplicate handlers. If the root logger already
    has handlers, its level is updated to the configured level.
    """

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    root_logger = logging.getLogger()

    root_logger.setLevel(level)

    # We intentionally do not use logging.basicConfig() here because
    # basicConfig() cannot identify an application-owned handler reliably
    # when the root logger is managed by a host application or test runner.
    # Reuse the application's handler if it already exists.
    # This keeps the function idempotent without interfering with
    # handlers installed by a host application or test runner.
    for handler in root_logger.handlers:
        if getattr(handler, "_biomed_mcp_handler", False):
            return

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    )
    handler._biomed_mcp_handler = True
    root_logger.addHandler(handler)
