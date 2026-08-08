from __future__ import annotations

import logging

LOGGER_NAME = "ecstacy"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ecstacy namespace.

    A NullHandler on the root logger keeps the library silent by default;
    child loggers propagate to it.
    """
    root = logging.getLogger(LOGGER_NAME)
    if not root.handlers:
        root.addHandler(logging.NullHandler())
    if not name or name == LOGGER_NAME:
        return root
    return logging.getLogger(name)


def configure_logging(level: str | int | None = None) -> logging.Logger:
    """Attach a stderr StreamHandler for CLI/headless use.

    level defaults to the ECSTACY_LOG_LEVEL env var, or WARNING. Safe to
    call more than once (no duplicate handlers).
    """
    import os

    logger = get_logger()
    if level is None:
        level = os.environ.get("ECSTACY_LOG_LEVEL", "WARNING")
    if isinstance(level, str):
        numeric = logging.getLevelName(level.upper())
        level = numeric if isinstance(numeric, int) else logging.WARNING
    logger.setLevel(int(level))
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger
