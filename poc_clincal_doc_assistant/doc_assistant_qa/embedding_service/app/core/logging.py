import logging
import sys
import os


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level)

    handlers = [console]

    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/embedding_service.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        handlers.append(file_handler)
    except Exception:
        pass

    logging.basicConfig(level=level, handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)

    logger = logging.getLogger("embedding_service")
    logger.info("Embedding service logging initialised")
    return logger


logger = setup_logging()
