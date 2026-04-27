"""loguru 日志初始化。"""

import sys
from pathlib import Path

from loguru import logger

from ..config import LOG_DIR, get_settings


def setup_logging() -> None:
    """统一配置控制台和文件日志。

    这里不输出任何 API Key，只记录请求、节点执行、外部调用和异常摘要。
    """
    settings = get_settings()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = Path(LOG_DIR) / "app.log"

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        colorize=True,
        backtrace=settings.debug,
        diagnose=settings.debug,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level}</level> | {message}",
    )
    logger.add(
        log_file,
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=False,
        backtrace=settings.debug,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
    )
