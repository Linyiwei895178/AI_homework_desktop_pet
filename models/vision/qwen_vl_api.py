"""
调用Qwen-VL多模态API，返回用户表情/状态
"""

# TO_DO: 调用 Qwen-VL API
# 返回 mock 数据 "happy" 用于demo


def get_user_expression(image_path: str) -> str:
    """
    调用 Qwen-VL API 识别用户表情/状态

    :param image_path: 用户图片路径
    :return: 用户表情状态字符串（如 "happy", "sad", "neutral"）

    TO_DO:
    - 解析环境变量获取 QWEN_VL_API_KEY
    - 构建API请求，传入图片数据
    - 解析返回结果，提取表情状态
    - 异常处理与重试机制
    """
    # TO_DO: 调用 Qwen-VL API
    # 返回 mock 数据 "happy" 用于demo
    print(f"[Qwen-VL] 收到图片路径: {image_path}")
    print("[Qwen-VL] 正在调用 Qwen-VL API... (stub)")

    # demo阶段返回mock数据
    mock_result = "happy"
    print(f"[Qwen-VL] 识别结果: {mock_result}")
    return mock_result
