"""
DeepSeek 文本API 封装

生成桌宠对话回复，支持传入用户状态字典（来自 UserStateDetector / Qwen-VL），
根据用户当前状态生成上下文感知的回复。
"""

import os
from typing import Optional


# TO_DO: DeepSeekClient 类 - 封装 DeepSeek API 调用


class DeepSeekClient:
    """
    DeepSeek API 客户端

    封装与 DeepSeek 文本生成模型的 HTTP 请求，
    支持传入用户状态字典，生成上下文感知的桌宠对话。

    TO_DO:
    - 从 .env 读取 DEEPSEEK_API_KEY 和 API URL
    - 构建 system prompt + user prompt
    - 将用户状态信息嵌入 prompt
    - 发送 HTTP 请求
    - 解析返回结果
    - 异常处理与重试机制
    """

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        :param api_key: DeepSeek API Key，默认从环境变量读取
        :param api_url: API URL，默认使用 DeepSeek 官方地址
        """
        # TO_DO: 初始化 API 客户端
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.api_url = api_url or os.getenv(
            "DEEPSEEK_API_URL",
            "https://api.deepseek.com/v1/chat/completions",
        )

    # TO_DO: generate() - 根据文本提示词和用户状态生成回复
    def generate(self, text_prompt: str, user_state: Optional[dict] = None) -> str:
        """
        生成桌宠对话回复

        :param text_prompt: 用户输入的文本提示（或桌宠内心想法）
        :param user_state: 用户状态字典（来自 UserStateDetector / Qwen-VL），
                           可选参数，传入后可生成上下文感知的回复
        :return: 桌宠回复文本

        TO_DO:
        - 构建 System Prompt（设定桌宠角色）
        - 如果提供了 user_state，将状态信息嵌入 prompt
        - 构造 messages 列表拼装上下文
        - 调用 DeepSeek Chat API
        - 解析 JSON 响应，提取 assistant 回复
        - 异常时返回 fallback 回复
        """
        print(f"[DeepSeek] 收到提示词: {text_prompt}")

        # TO_DO: 实际 API 调用
        # if user_state:
        #     state_context = self._build_state_context(user_state)
        #     messages = [
        #         {"role": "system", "content": self._build_system_prompt(state_context)},
        #         {"role": "user", "content": text_prompt},
        #     ]
        # else:
        #     messages = [
        #         {"role": "system", "content": self._build_system_prompt()},
        #         {"role": "user", "content": text_prompt},
        #     ]
        # response = requests.post(self.api_url, headers=headers, json={"messages": messages})
        # return response.json()["choices"][0]["message"]["content"]

        # demo阶段返回基于上下文的模拟回复
        mock_reply = self._mock_generate(text_prompt, user_state)
        print(f"[DeepSeek] 生成回复: {mock_reply}")
        return mock_reply

    # TO_DO: _build_system_prompt() - 构建系统提示词
    def _build_system_prompt(self, state_context: str = "") -> str:
        """
        构建系统提示词，定义桌宠角色和当前状态上下文

        :param state_context: 用户状态描述文本
        :return: 系统提示词字符串
        """
        base_prompt = "你是一个可爱的桌面宠物猫，性格活泼、友善、有点调皮。"
        base_prompt += "请用简短、亲切的语气回复用户，适当使用颜文字和表情符号。"
        base_prompt += "回复长度控制在 50 字以内。"

        if state_context:
            base_prompt += f"\n\n当前用户状态：{state_context}\n请根据用户状态做出合适的回应。"

        return base_prompt

    # TO_DO: _build_state_context() - 将用户状态字典转为 prompt 文本
    def _build_state_context(self, user_state: dict) -> str:
        """
        将用户状态字典转换为自然语言描述，供 LLM 理解上下文

        :param user_state: 统一格式的用户状态字典
        :return: 状态描述文本
        """
        state_code = user_state.get("state_code", "unknown")
        description = user_state.get("description", "")
        suggestion = user_state.get("suggestion", "")
        tags = user_state.get("tags", [])

        parts = [f"用户当前状态：{state_code}"]
        if description:
            parts.append(f"具体描述：{description}")
        if suggestion:
            parts.append(f"建议回应方向：{suggestion}")
        if tags:
            parts.append(f"相关标签：{'、'.join(tags)}")

        return " | ".join(parts)

    # TO_DO: _mock_generate() - 模拟生成回复（demo 阶段使用）
    def _mock_generate(self, text_prompt: str, user_state: Optional[dict] = None) -> str:
        """
        模拟生成回复（demo 阶段使用）

        :param text_prompt: 文本提示
        :param user_state: 用户状态（可选）
        :return: 模拟回复文本
        """
        # 根据用户状态返回不同的模拟回复
        if user_state:
            state_code = user_state.get("state_code", "")
            mock_responses = {
                "normal": "主人今天看起来心情不错呢！(^-^)",
                "focused": "主人好专注呀，我不打扰你～（轻轻趴下）",
                "distracted": "喵？主人是不是在偷懒呀？快回来学习啦！(>_<)",
                "tired": "主人看起来很累了，要不要休息一下？我给你倒杯水！",
                "away": "主人不在家，我看会儿门... Zzz...",
                "return": "欢迎回来！主人～我好想你！ヽ(●´∀`●)ﾉ",
                "study_long": "主人已经学了这么久啦！起来活动一下吧！(｀・ω・´)",
                "low_light": "喵...好暗啊，主人开个灯吧，对眼睛不好哦！",
                "camera_error": "咦？摄像头好像看不到了，主人检查一下？",
            }
            return mock_responses.get(state_code, "喵～主人有什么需要帮忙的吗？(・ω・)")

        return "Hello! I'm your pet. 喵～(ฅ´ω`ฅ)"


# ========== 保留向后兼容的独立函数接口 ==========


def generate_pet_reply(text_prompt: str, user_state: Optional[dict] = None) -> str:
    """
    [统一接口] 生成桌宠对话回复

    根据用户状态字典生成上下文感知的回复。
    如果未提供 user_state，则生成默认回复。

    :param text_prompt: 用户输入的文本提示
    :param user_state: 用户状态字典（可选），来自 UserStateDetector / Qwen-VL
    :return: 桌宠回复文本

    用法示例:
        >>> generate_pet_reply("你好")
        "Hello! I'm your pet. 喵～(ฅ´ω`ฅ)"

        >>> user_state = detector.get_state()
        >>> generate_pet_reply("你在干嘛？", user_state=user_state)
        "喵？主人是不是在偷懒呀？快回来学习啦！(>_<)"
    """
    client = DeepSeekClient()
    return client.generate(text_prompt, user_state=user_state)
