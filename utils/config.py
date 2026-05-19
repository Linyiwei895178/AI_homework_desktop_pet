"""
配置读取（.env）
"""
import os
from dotenv import load_dotenv

# TO_DO: 读取 .env 文件，获取 API Keys
# 例： QWEN_VL_API_KEY, DEEPSEEK_API_KEY, TTS_API_KEY


class Config:
    """
    配置管理类

    读取 .env 文件中的环境变量，提供统一的配置访问接口

    TO_DO:
    - 使用 python-dotenv 加载 .env 文件
    - 读取 QWEN_VL_API_KEY, DEEPSEEK_API_KEY, TTS_API_KEY
    - 提供类型安全的值获取方法
    - 设置合理默认值
    """

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化配置（仅执行一次）"""
        if self._initialized:
            return
        self._initialized = True

        # TO_DO: 读取 .env 文件，获取 API Keys
        # 例： QWEN_VL_API_KEY, DEEPSEEK_API_KEY, TTS_API_KEY

        # 加载 .env 文件
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"[Config] 从 {env_path} 加载配置")
        else:
            print(f"[Config] 未找到 .env 文件，使用默认配置")

        # API Keys
        self.QWEN_VL_API_KEY = os.getenv("QWEN_VL_API_KEY", "")
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
        self.TTS_API_KEY = os.getenv("TTS_API_KEY", "")

        # API URLs（带默认值）
        self.QWEN_VL_API_URL = os.getenv("QWEN_VL_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
        self.DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.TTS_API_URL = os.getenv("TTS_API_URL", "")

        # 应用配置
        self.DEBUG = os.getenv("DEBUG", "True").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    def get(self, key: str, default=None):
        """
        获取配置项
        :param key: 配置键名
        :param default: 默认值
        :return: 配置值
        """
        return getattr(self, key, default)


# 全局配置实例
config = Config()
