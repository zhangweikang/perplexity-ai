"""
Logging configuration for Perplexity AI library. / Perplexity AI 库的日志配置。

This module provides centralized logging configuration with support for / 该模块提供集中式日志配置，支持
file and console output, structured logging, and configurable log levels. / 文件和控制台输出、结构化日志以及可配置的日志级别。
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from .config import LOG_FORMAT, LOG_LEVEL, LOG_FILE


def setup_logger(
    name: str = "perplexity",
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    console: bool = True,
) -> logging.Logger:
    """
    Configure and return a logger instance. / 配置并返回一个日志记录器实例。

    Args:
        name: Logger name / 日志记录器名称
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) / 日志级别
        log_file: Path to log file (optional) / 日志文件路径（可选）
        console: Whether to output to console / 是否输出到控制台

    Returns:
        Configured logger instance / 配置好的日志记录器实例

    Example:
        >>> logger = setup_logger("my_app", level="DEBUG")
        >>> logger.info("Application started")
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level or LOG_LEVEL))

    # Remove existing handlers / 移除现有的处理器
    logger.handlers.clear()

    # Create formatter / 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT)

    # Console handler / 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler / 文件处理器
    if log_file or LOG_FILE:
        file_path = Path(log_file or LOG_FILE)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger instance / 默认日志记录器实例
logger = setup_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name. / 获取具有给定名称的日志记录器实例。

    Args:
        name: Logger name / 日志记录器名称

    Returns:
        Logger instance / 日志记录器实例
    """
    return logging.getLogger(f"perplexity.{name}")
