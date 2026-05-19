"""
TTS语音输出（API或本地方法）
"""
import os

# TO_DO: 调用TTS生成语音
# 可以保存到 assets/sounds/{pet_id}_sound_{state}_{action}_001.wav


def speak(text: str, pet_id: str = "cat", state: str = "neutral", action: str = "idle"):
    """
    TTS语音输出：将文本转为语音并播放

    :param text: 要朗读的文本
    :param pet_id: 桌宠ID（用于文件命名）
    :param state: 当前状态（用于文件命名）
    :param action: 当前动作（用于文件命名）

    TO_DO:
    - 解析环境变量获取 TTS_API_KEY
    - 调用TTS API生成语音数据
    - 保存到 assets/sounds/{pet_id}_sound_{state}_{action}_001.wav
    - 播放语音文件
    - 异常处理
    """
    # TO_DO: 调用TTS生成语音
    # 可以保存到 assets/sounds/{pet_id}_sound_{state}_{action}_001.wav
    print(f"[TTS] 正在合成语音: \"{text}\"")
    print(f"[TTS] 调用TTS API... (stub)")

    # 构建输出路径
    sounds_dir = os.path.join("assets", "sounds")
    os.makedirs(sounds_dir, exist_ok=True)
    output_path = os.path.join(
        sounds_dir,
        f"{pet_id}_sound_{state}_{action}_001.wav"
    )

    # demo阶段仅打印信息，不生成实际语音
    print(f"[TTS] 语音文件将保存到: {output_path}")
    print(f"[TTS] 播放语音: \"{text}\" (stub)")
