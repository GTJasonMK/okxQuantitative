# 日志工具模块
# 统一管理日志输出

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..config import LOGS_DIR


def setup_logger(
    name: str = "okx_quant",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    配置日志器

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件名，不指定则使用日期命名
        console: 是否输出到控制台

    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件输出
    if log_file is None:
        log_file = f"{datetime.now().strftime('%Y%m%d')}.log"

    file_path = LOGS_DIR / log_file
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 预配置的日志器
logger = setup_logger()


# 便捷函数
def info(msg: str):
    """记录INFO级别日志"""
    logger.info(msg)


def warning(msg: str):
    """记录WARNING级别日志"""
    logger.warning(msg)


def error(msg: str):
    """记录ERROR级别日志"""
    logger.error(msg)


def debug(msg: str):
    """记录DEBUG级别日志"""
    logger.debug(msg)
