"""
日志记录：控制台 + 文件 + 可选的追踪日志
"""
import logging
import os
from datetime import datetime


def setup_logger(
    name: str = "AI_Desktop_Pet",
    log_level: str = "INFO",
    enable_file: bool = True,
    enable_console: bool = True,
    trace_log: bool = False,
) -> logging.Logger:
    """
    设置并返回一个日志记录器。

    :param name: 日志记录器名称
    :param log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :param enable_file: 是否输出到日志文件
    :param enable_console: 是否输出到控制台
    :param trace_log: 是否启用追踪日志（写入单独的 trace_*.log 文件）
    :return: 配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台 handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件 handler
    if enable_file:
        logs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"pet_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 追踪日志 handler
    if trace_log:
        logs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
        os.makedirs(logs_dir, exist_ok=True)
        trace_file = os.path.join(logs_dir, f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        trace_handler = logging.FileHandler(trace_file, encoding="utf-8")
        trace_handler.setLevel(logging.DEBUG)
        trace_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(module)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S.%f"
        )
        trace_handler.setFormatter(trace_formatter)
        logger.addHandler(trace_handler)

    return logger


def get_logger(name: str = "AI_Desktop_Pet") -> logging.Logger:
    """获取已存在的日志记录器，若不存在则新建。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
