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
        self.VOICE_PACK_ID = os.getenv("VOICE_PACK_ID", "")
        self.VOICE_PACK_MODE = os.getenv("VOICE_PACK_MODE", "prefer")
        self.VOICE_PACK_AUTO_BY_PET = os.getenv("VOICE_PACK_AUTO_BY_PET", "true")
        self.COMPUTER_ACTIVITY_ENABLED = os.getenv("COMPUTER_ACTIVITY_ENABLED", "true")
        self.COMPUTER_ACTIVITY_POLL_MS = os.getenv("COMPUTER_ACTIVITY_POLL_MS", "1000")
        self.COMPUTER_ACTIVITY_MIN_DURATION = os.getenv("COMPUTER_ACTIVITY_MIN_DURATION", "0")
        self.COMPUTER_ACTIVITY_COMMENT_COOLDOWN = os.getenv("COMPUTER_ACTIVITY_COMMENT_COOLDOWN", "150")

        # Cloud / Supabase
        self.SUPABASE_URL = os.getenv("SUPABASE_URL", "")
        self.SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

        # Emotion
        self.EMOTION_ANALYSIS_ENABLED = os.getenv("EMOTION_ANALYSIS_ENABLED", "true")

        # Screen usage
        self.SCREEN_USAGE_ENABLED = os.getenv("SCREEN_USAGE_ENABLED", "true")
        self.SCREEN_REMINDER_THRESHOLDS = os.getenv("SCREEN_REMINDER_THRESHOLDS", "60,120,180,240")

        # AI memory
        self.AI_MEMORY_DIR = os.getenv("AI_MEMORY_DIR", "assets/ai_memory")
        self.AI_MEMORY_FILE = os.getenv("AI_MEMORY_FILE", "")

        # UI
        self.UI_OPACITY = os.getenv("UI_OPACITY", "1.0")
        self.UI_SCALE = os.getenv("UI_SCALE", "1.0")
        self.UI_THEME = os.getenv("UI_THEME", "default")
        self.UI_RESPONSE_LANGUAGE = os.getenv("UI_RESPONSE_LANGUAGE", "zh-CN")
        self.UI_AUTO_HIDE = os.getenv("UI_AUTO_HIDE", "false")
        self.UI_MOUSE_FOLLOW = os.getenv("UI_MOUSE_FOLLOW", "false")
        self.UI_FREE_ROAM = os.getenv("UI_FREE_ROAM", "true")
        self.UI_PIN_TO_TOP = os.getenv("UI_PIN_TO_TOP", "true")
        self.UI_SHOW_CHAT_BUBBLE = os.getenv("UI_SHOW_CHAT_BUBBLE", "true")
        self.UI_SHOW_STATUS_BAR = os.getenv("UI_SHOW_STATUS_BAR", "true")
        self.UI_SHOW_CLOUD_PANEL = os.getenv("UI_SHOW_CLOUD_PANEL", "false")

        # Demo / Mock
        self.DESKTOP_PET_MOCK_USER_STATE = os.getenv("DESKTOP_PET_MOCK_USER_STATE", "true")
        self.DESKTOP_PET_MOCK_CLOUD = os.getenv("DESKTOP_PET_MOCK_CLOUD", "false")
        self.DESKTOP_PET_MOCK_GESTURE = os.getenv("DESKTOP_PET_MOCK_GESTURE", "false")

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
