import logging
import sys
from app.config import settings


def setup_logging() -> logging.Logger:
    """
    Configure structured logging for the application.
    Logs to both console and a rotating file under logs/.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Format: timestamp | level | module | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # File handler
    try:
        file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        handlers = [console_handler, file_handler]
    except Exception:
        handlers = [console_handler]

    # Root logger
    logging.basicConfig(level=log_level, handlers=handlers)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    logger = logging.getLogger("doc_assistant")
    logger.info(
        f"Logging initialised | env={settings.app_env} | level={settings.log_level}"
    )
    return logger


# Single importable logger used across all modules
logger = setup_logging()
