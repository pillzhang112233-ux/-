import logging
import os
import sys
from datetime import datetime

# 定义日志保存路径
LOG_DIR = os.path.join("database", "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class SmartLogger:
    _instance = None

    @staticmethod
    def get_logger(name="SmartMoneyBot"):
        """
        单例模式获取 Logger，避免重复添加 Handler
        """
        if SmartLogger._instance:
            return SmartLogger._instance

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG) # 捕获所有级别，由 Handler 决定过滤

        # 防止重复添加 Handler (如果被多次调用)
        if logger.hasHandlers():
            return logger

        # --- 格式定义 ---
        # 文件日志格式：包含时间、日志级别、模块名、具体信息
        file_formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - [%(filename)s:%(lineno)d] - %(message)s'
        )
        # 控制台(IDLE)日志格式：只显示时间和信息，保持清爽
        console_formatter = logging.Formatter(
            '%(asctime)s - %(message)s', datefmt='%H:%M:%S'
        )

        # --- Handler 1: 控制台输出 (IDLE) ---
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO) # 控制台只看 INFO，不看调试杂音
        c_handler.setFormatter(console_formatter)
        logger.addHandler(c_handler)

        # 获取当天日期用于文件名
        today = datetime.now().strftime('%Y-%m-%d')

        # --- Handler 2: 运行流水日志 (run_xxxx.log) ---
        run_log_path = os.path.join(LOG_DIR, f"run_{today}.log")
        f_handler = logging.FileHandler(run_log_path, encoding='utf-8')
        f_handler.setLevel(logging.INFO)
        f_handler.setFormatter(file_formatter)
        logger.addHandler(f_handler)

        # --- Handler 3: 错误堆栈日志 (error_xxxx.log) ---
        error_log_path = os.path.join(LOG_DIR, f"error_{today}.log")
        e_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        e_handler.setLevel(logging.ERROR) # 只记录错误
        e_handler.setFormatter(file_formatter)
        logger.addHandler(e_handler)

        SmartLogger._instance = logger
        return logger

# 便捷导出
logger = SmartLogger.get_logger()
