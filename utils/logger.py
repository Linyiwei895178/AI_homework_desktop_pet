"""
日志记录
"""
import logging
import os
from datetime import datetime

# TO_DO: 配置日志格式、输出级别、文件路径


def setup_logger(name: str = "AI_Desktop_Pet", log_level: str = "INFO") -> logging.Logger:
    """
    设置并返回一个日志记录器

    :param name: 日志记录器名称
    :param log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :return: 配置好的 Logger 实例

    TO_DO:
    - 配置日志格式（时间、级别、模块名、消息）
    - 输出到控制台
    - 可选：输出到日志文件
    - 日期滚动
    """
    # TO_DO: 创建logger实例并配置
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 设置日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # 创建控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # 设置日志格式
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # 添加handler到logger
    logger.addHandler(console_handler)

    # 可选：添加文件handler
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"pet_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "AI_Desktop_Pet") -> logging.Logger:
    """
    获取已存在的日志记录器，若不存在则新建

    :param name: 日志记录器名称
    :return: Logger 实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
