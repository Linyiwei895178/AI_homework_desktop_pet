"""
调用DeepSeek文本API，生成桌宠对话
"""

# TO_DO: 调用 DeepSeek API
# 返回 mock 数据 "Hello! I'm your pet."


def generate_pet_reply(text_prompt: str) -> str:
    """
    调用 DeepSeek 文本API 生成桌宠对话回复

    :param text_prompt: 用户输入的文本提示
    :return: 桌宠回复文本

    TO_DO:
    - 解析环境变量获取 DEEPSEEK_API_KEY
    - 构建API请求，传入prompt
    - 解析返回结果，提取回复文本
    - 异常处理与重试机制
    """
    # TO_DO: 调用 DeepSeek API
    # 返回 mock 数据 "Hello! I'm your pet."
    print(f"[DeepSeek] 收到提示词: {text_prompt}")
    print("[DeepSeek] 正在调用 DeepSeek API... (stub)")

    # demo阶段返回mock数据
    mock_reply = "Hello! I'm your pet."
    print(f"[DeepSeek] 生成回复: {mock_reply}")
    return mock_reply
