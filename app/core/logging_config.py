from __future__ import annotations

import sys
from typing import Any

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    """Configure loguru for structured console logging."""

    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format=(
            "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | "
            "{level: <8} | {name}:{function}:{line} - {message}"
        ),
    )


def get_logger(**kwargs: Any):
    return logger.bind(**kwargs)
