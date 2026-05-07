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
        fh = logging.FileHandler("logs/ai_layer_service.log", encoding="utf-8")
        fh.setFormatter(formatter)
        fh.setLevel(level)
        handlers.append(fh)
    except Exception:
        pass

    logging.basicConfig(level=level, handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)

    logger = logging.getLogger("ai_layer_service")
    logger.info("AI layer service logging initialised")
    return logger


logger = setup_logging()
