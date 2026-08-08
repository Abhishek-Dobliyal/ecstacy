from __future__ import annotations

import logging

from ecstacy.util.logging import LOGGER_NAME, configure_logging, get_logger


def test_get_logger_namespaced():
    logger = get_logger("ecstacy.app")
    assert logger.name == "ecstacy.app"
    assert logger.parent is logging.getLogger(LOGGER_NAME)


def test_root_logger_has_null_handler():
    root = get_logger()
    assert any(isinstance(h, logging.NullHandler) for h in root.handlers)


def test_configure_logging_idempotent_no_duplicate_stream_handlers():
    logger = configure_logging("DEBUG")
    before = sum(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    logger2 = configure_logging("DEBUG")
    after = sum(isinstance(h, logging.StreamHandler) for h in logger2.handlers)
    assert logger is logger2
    assert before == 1
    assert after == 1
    # restore: remove the stream handler added by this test
    logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)]
    logger.setLevel(logging.NOTSET)
