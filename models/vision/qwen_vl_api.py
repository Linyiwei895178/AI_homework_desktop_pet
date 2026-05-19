"""
Qwen-VL 多模态API 封装

提供与 UserStateDetector 兼容的接口，支持：
- 图片 → 用户表情/状态识别
- 返回统一格式的状态字典
"""

import os
from typing import Optional

# 可复用 UserStateDetector 中的状态常量
from models.vision.user_state_detector import (
    STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
    STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR, STATE_UNKNOWN, ALL_STATE_CODES,
    create_empty_state, is_valid_state,
)

# TO_DO: QwenVLClient 类 - 封装 Qwen-VL API 调用


class QwenVLClient:
    """
    Qwen-VL API 客户端

    封装与阿里云 DashScope Qwen-VL 模型的 HTTP 请求，
    接收图片，返回统一格式的用户状态字典。

    TO_DO:
    - 从 .env 读取 QWEN_VL_API_KEY 和 API URL
    - 实现图片编码（base64）
    - 构建 API 请求体
    - 解析返回结果，映射到统一状态字典
    - 异常处理与重试机制
    """

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        :param api_key: Qwen-VL API Key，默认从环境变量读取
        :param api_url: API URL，默认使用 DashScope 地址
        """
        # TO_DO: 初始化 API 客户端
        self.api_key = api_key or os.getenv("QWEN_VL_API_KEY", "")
        self.api_url = api_url or os.getenv(
            "QWEN_VL_API_URL",
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        )

        # 状态码映射：Qwen-VL 原始输出 → 统一 state_code
        # TO_DO: 根据实际 Qwen-VL 返回内容完善映射规则
        self._state_mapping = {
            "happy": STATE_NORMAL,
            "sad": STATE_TIRED,
            "neutral": STATE_NORMAL,
            "angry": STATE_DISTRACTED,
            "surprised": STATE_NORMAL,
            "fearful": STATE_DISTRACTED,
            "disgusted": STATE_DISTRACTED,
        }

    # TO_DO: analyze_image() - 分析单张图片
    def analyze_image(self, image_path: str) -> dict:
        """
        分析单张图片，返回用户状态字典

        :param image_path: 图片文件路径
        :return: 统一格式的状态字典

        TO_DO:
        - 读取图片并转为 base64
        - 构建 API 请求（多模态输入）
        - 发送 HTTP 请求到 DashScope
        - 解析 JSON 响应，提取表情/状态
        - 映射到统一 state_code
        - 异常时返回 camera_error 或 unknown
        """
        print(f"[Qwen-VL] 收到图片路径: {image_path}")
        print("[Qwen-VL] 正在调用 Qwen-VL API... (stub)")

        # demo阶段返回模拟数据
        mock_state = create_empty_state(STATE_NORMAL)
        mock_state["state_code"] = STATE_NORMAL
        mock_state["state_name"] = "正常状态"
        mock_state["description"] = "用户表情正常，姿态自然。"
        mock_state["tags"] = ["正常", "微笑"]
        mock_state["confidence"] = 0.90
        mock_state["duration"] = 5.0
        mock_state["need_response"] = False
        mock_state["suggestion"] = ""
        mock_state["source"] = ["qwen_vl"]

        print(f"[Qwen-VL] 识别结果: {mock_state['state_code']}")
        return mock_state

    # TO_DO: analyze_image_with_prompt() - 带自定义提示词分析
    def analyze_image_with_prompt(self, image_path: str, prompt: str) -> dict:
        """
        使用自定义提示词分析图片

        :param image_path: 图片路径
        :param prompt: 自定义提示词（引导模型关注特定方面）
        :return: 统一格式的状态字典
        """
        # TO_DO: 自定义 prompt 的 API 调用
        return self.analyze_image(image_path)


# ========== 保留向后兼容的独立函数接口 ==========


def get_user_expression(image_path: str) -> str:
    """
    [旧接口] 获取用户表情状态（已弃用，推荐使用 QwenVLClient）

    :param image_path: 用户图片路径
    :return: 用户表情状态字符串
    """
    client = QwenVLClient()
    state_dict = client.analyze_image(image_path)
    return state_dict["state_code"]


def get_user_state(image_path: str) -> dict:
    """
    [新接口] 获取统一格式的用户状态字典

    直接对接 UserStateDetector 的输出格式，
    方便 deepseek_api.py 和 pet_state.py 直接调用。

    :param image_path: 用户图片路径
    :return: 统一格式的状态字典
    """
    client = QwenVLClient()
    return client.analyze_image(image_path)
