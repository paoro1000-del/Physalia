"""Daily application log files and their seven-day retention policy."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = APP_ROOT / "app_config.json"
DEFAULT_LOG_DIR = APP_ROOT / "logs"
LOG_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
              "WARNING": logging.WARNING, "ERROR": logging.ERROR}
LOG_NAME_RE = re.compile(r"^(\d{8})_app\.log$")
RETENTION_DAYS = 7
LOGGER = logging.getLogger("physalia")


class DailyLogHandler(logging.Handler):
    """Append to one YYYYMMDD_app.log file, switching files at local midnight."""

    def __init__(self, directory: Path, today: date | None = None):
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.current_date = today or date.today()
        self.stream = None
        self._open_current_file()
        self.removed_files = purge_old_log_files(self.directory, self.current_date)

    @property
    def current_path(self) -> Path:
        return self.directory / f"{self.current_date:%Y%m%d}_app.log"

    def _open_current_file(self) -> None:
        self.stream = self.current_path.open("a", encoding="utf-8", newline="\n")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            today = date.today()
            if today != self.current_date:
                self.stream.close()
                self.current_date = today
                self._open_current_file()
            self.stream.write(self.format(record) + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        if self.stream and not self.stream.closed:
            self.stream.flush()

    def close(self) -> None:
        self.acquire()
        try:
            if self.stream and not self.stream.closed:
                self.stream.close()
            super().close()
        finally:
            self.release()


def purge_old_log_files(directory: Path, today: date | None = None) -> list[Path]:
    """Remove matching daily logs at least seven days old; leave other files alone."""
    directory = Path(directory)
    current_date = today or date.today()
    cutoff = current_date - timedelta(days=RETENTION_DAYS)
    removed = []
    try:
        entries = directory.iterdir()
    except FileNotFoundError:
        return removed
    for path in entries:
        match = LOG_NAME_RE.fullmatch(path.name)
        if not match:
            continue
        try:
            file_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            if file_date <= cutoff:
                path.unlink()
                removed.append(path)
        except (OSError, ValueError):
            continue
    return removed


def configure_logging(config_path: Path | None = None,
                      log_dir: Path | None = None) -> logging.Logger:
    """Configure the app logger from app_config.json, defaulting to INFO."""
    config_path = Path(config_path or DEFAULT_CONFIG_PATH)
    log_dir = Path(log_dir or DEFAULT_LOG_DIR)
    level_name = "INFO"
    config_warning = None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("configuration root must be an object")
        requested = config.get("log_level", "INFO")
        if not isinstance(requested, str) or requested.upper() not in LOG_LEVELS:
            raise ValueError("log_level must be DEBUG, INFO, WARNING or ERROR")
        level_name = requested.upper()
    except FileNotFoundError:
        config_warning = "app_config.json not found; using INFO"
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        config_warning = f"invalid logging configuration ({type(exc).__name__}); using INFO"

    logger = logging.getLogger("physalia")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(LOG_LEVELS[level_name])
    logger.propagate = False
    handler = DailyLogHandler(log_dir)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"))
    handler.setLevel(LOG_LEVELS[level_name])
    logger.addHandler(handler)
    if config_warning:
        logger.warning("%s", config_warning)
    logger.info("logging_initialized level=%s removed_old_logs=%d",
                level_name, len(handler.removed_files))
    for removed in handler.removed_files:
        logger.debug("old_log_removed log_date=%s", removed.stem[:8])
    logger.debug("logging_configuration_loaded log_file=%s retention_days=%d",
                 handler.current_path.name, RETENTION_DAYS)
    return logger
