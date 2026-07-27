# -*- coding: utf-8 -*-
"""Configure the package-owned logger."""
import logging
import logging.handlers
import os
from types import MethodType


# This is the single intended switch between persistent and colored output.
OUTPUT_MODE = "file"

OK_LOG_LEVEL = logging.INFO + 5
_HANDLER_MARKER = "_paramws_owned_handler"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOG_FORMAT = (
    "%(asctime)s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)"
)
_RESET = "\x1b[0m"
_LEVEL_COLORS = {
    logging.DEBUG: "\x1b[95m",
    logging.INFO: "\x1b[38;20m",
    logging.WARNING: "\x1b[33;20m",
    logging.ERROR: "\x1b[31;20m",
    logging.CRITICAL: "\x1b[31;1m",
    OK_LOG_LEVEL: "\x1b[92m",
}

logging.addLevelName(OK_LOG_LEVEL, "OK")
logger = logging.getLogger("paramws")


class ColoredFormatter(logging.Formatter):
    """Format package console records with a color for each supported level."""

    def __init__(self):
        super().__init__()
        self._formatters = {
            level: logging.Formatter(
                "%(asctime)s "
                + color
                + "%(levelname)-8s"
                + _RESET
                + " %(message)s (%(filename)s:%(lineno)d)",
                _DATE_FORMAT,
            )
            for level, color in _LEVEL_COLORS.items()
        }
        self._default_formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    def format(self, record):
        formatter = self._formatters.get(record.levelno, self._default_formatter)
        return formatter.format(record)


def _ok(self, message, *args, **kwargs):
    """Log a successful operation while retaining the external caller."""
    if self.isEnabledFor(OK_LOG_LEVEL):
        # This wrapper adds one frame. Incrementing a supplied stacklevel also
        # preserves callers that deliberately report on behalf of their caller.
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        self._log(OK_LOG_LEVEL, message, args, **kwargs)


def _remove_owned_handlers():
    """Detach and close handlers created by this module."""
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def _console_handler():
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ColoredFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    return handler


def _file_handler(log_file):
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=1_000_000,
        backupCount=7,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    return handler


def _configure_logger(output_mode=None):
    """Configure exactly one package-owned output handler."""
    selected_mode = OUTPUT_MODE if output_mode is None else output_mode
    if selected_mode not in {"file", "console"}:
        raise ValueError("OUTPUT_MODE must be either 'file' or 'console'")

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.disabled = False
    logger.ok = MethodType(_ok, logger)

    # Only handlers marked here belong to this package. Consumer handlers, if
    # any, are outside this module's ownership and are left unchanged.
    _remove_owned_handlers()

    if selected_mode == "console":
        handler = _console_handler()
    else:
        log_file = (
            os.environ["PARAMWS_LOG_FILE"]
            if "PARAMWS_LOG_FILE" in os.environ
            else "./paramws.log"
        )
        try:
            handler = _file_handler(log_file)
        except (OSError, ValueError) as error:
            # Do not retry the unusable path. Install the console handler first
            # so the package warning is emitted through its normal logger.
            handler = _console_handler()
            logger.addHandler(handler)
            logger.warning(
                "Could not open paramws log file %r: %s; "
                "falling back to console output",
                log_file,
                error,
            )
            return logger

    logger.addHandler(handler)
    return logger


_configure_logger()
