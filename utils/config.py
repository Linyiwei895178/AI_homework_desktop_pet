"""
配置读取（.env）
"""
import os
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

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
        self.DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "")
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.DEEPSEEK_THINKING = os.getenv("DEEPSEEK_THINKING", "disabled")
        self.DEEPSEEK_FORCE_MOCK = os.getenv("DEEPSEEK_FORCE_MOCK", "false")
        self.DEEPSEEK_FALLBACK_TO_MOCK = os.getenv("DEEPSEEK_FALLBACK_TO_MOCK", "true")
        self.TTS_API_URL = os.getenv("TTS_API_URL", "")
        self.TTS_PROVIDER = os.getenv("TTS_PROVIDER", "auto")
        self.EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoyiNeural")
        self.GPT_SOVITS_API_URL = os.getenv("GPT_SOVITS_API_URL", "http://127.0.0.1:9880")
        self.GPT_SOVITS_TIMEOUT = os.getenv("GPT_SOVITS_TIMEOUT", "90")
        self.VOICE_PACK_ID = os.getenv("VOICE_PACK_ID", "")
        self.VOICE_PACK_MODE = os.getenv("VOICE_PACK_MODE", "prefer")
        self.VOICE_PACK_AUTO_BY_PET = os.getenv("VOICE_PACK_AUTO_BY_PET", "true")
        self.OPENVOICE_ENABLED = os.getenv("OPENVOICE_ENABLED", "false")
        self.OPENVOICE_PYTHON = os.getenv("OPENVOICE_PYTHON", "")
        self.OPENVOICE_REPO_DIR = os.getenv("OPENVOICE_REPO_DIR", "")
        self.OPENVOICE_CHECKPOINT_DIR = os.getenv("OPENVOICE_CHECKPOINT_DIR", "")
        self.OPENVOICE_DEVICE = os.getenv("OPENVOICE_DEVICE", "auto")
        self.COMPUTER_ACTIVITY_ENABLED = os.getenv("COMPUTER_ACTIVITY_ENABLED", "true")
        self.COMPUTER_ACTIVITY_POLL_MS = os.getenv("COMPUTER_ACTIVITY_POLL_MS", "1000")
        self.COMPUTER_ACTIVITY_MIN_DURATION = os.getenv("COMPUTER_ACTIVITY_MIN_DURATION", "0")
        self.COMPUTER_ACTIVITY_COMMENT_COOLDOWN = os.getenv("COMPUTER_ACTIVITY_COMMENT_COOLDOWN", "150")

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
