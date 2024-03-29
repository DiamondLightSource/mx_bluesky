from __future__ import annotations

import functools
import logging
import logging.config
from os import environ
from pathlib import Path
from typing import Optional

VISIT_PATH = Path("/dls_sw/i24/etc/ssx_current_visit.txt")

# Logging set up
logging.getLogger("I24ssx").addHandler(logging.NullHandler())

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "class": "logging.Formatter",
            "format": "%(message)s",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        "I24ssx": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        }
    },
}

logging.config.dictConfig(logging_config)


def _read_visit_directory_from_file() -> Path:
    with open(VISIT_PATH, "r") as f:
        visit = f.readline().rstrip()
    return Path(visit)


def _get_logging_file_path() -> Path:
    """Get the path to write the artemis log files to.
    If on a beamline, this will be written to the according area depending on the
    BEAMLINE envrionment variable. If no envrionment variable is found it will default
    it to the tmp/dev directory.
    Returns:
        logging_path (Path): Path to the log file for the file handler to write to.
    """
    beamline: Optional[str] = environ.get("BEAMLINE")
    logging_path: Path

    if beamline:
        logging_path = _read_visit_directory_from_file() / "tmp/serial/logs"
    else:
        logging_path = Path("./tmp/logs/")

    Path(logging_path).mkdir(parents=True, exist_ok=True)
    return logging_path


def config(logfile: str | None = None, write_mode: str = "a", delayed: bool = False):
    """
    Configure the logging.

    Args:
        logfile (str, optional): Filename for logfile. If passed, create a file handler\
            for the logger to write to file the log output. Defaults to None.
        write_mode (str, optional): String indicating writing mode for the output \
            .log file. Defaults to "a".
    """
    logger = logging.getLogger("I24ssx")
    if logfile:
        logs = _get_logging_file_path() / logfile
        fileFormatter = logging.Formatter(
            "%(asctime)s %(levelname)s: \t(%(name)s) %(message)s",
            datefmt="%d-%m-%Y %I:%M:%S",
        )
        FH = logging.FileHandler(logs, mode=write_mode, encoding="utf-8", delay=delayed)
        FH.setLevel(logging.DEBUG)
        FH.setFormatter(fileFormatter)
        logger.addHandler(FH)


def log_on_entry(func):
    logger = logging.getLogger("I24ssx")

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        name = func.__name__
        logger.debug("Running %s " % name)
        return func(*args, **kwargs)

    return decorator
