import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


def _has_parent_handler(logger: logging.Logger) -> bool:
    parent = logger.parent
    while parent:
        if parent.handlers:
            return True
        parent = parent.parent
    return False


def get_logger(name: str, log_dir: Optional[Union[Path, str]] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    if not _has_parent_handler(logger):
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        logger.addHandler(console)

    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_handler = logging.FileHandler(
            log_dir / f"{timestamp}.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def make_log_path(logs_dir: Union[Path, str], event: str) -> Path:
    """生成符合规范的日志文件路径：logs/YYYY-MM-DD_HH-MM-SS_{event}.log"""
    logs_dir = Path(logs_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_event = event.replace(" ", "_").replace("/", "_")
    return logs_dir / f"{timestamp}_{safe_event}.log"
