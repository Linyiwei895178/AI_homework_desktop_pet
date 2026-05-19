"""
UserStateDetector - 用户状态检测器

整合 Qwen-VL 及 MediaPipe 等上游模块，输出统一的用户状态字典格式。
"""

import os
from typing import Optional

# 状态大类常量定义
STATE_NORMAL = "normal"          # 正常状态
STATE_FOCUSED = "focused"        # 专注学习
STATE_DISTRACTED = "distracted"  # 疑似分心
STATE_TIRED = "tired"            # 疑似疲劳
STATE_AWAY = "away"              # 离开座位
STATE_RETURN = "return"          # 回到座位
STATE_STUDY_LONG = "study_long"  # 学习过久
STATE_LOW_LIGHT = "low_light"    # 环境偏暗
STATE_CAMERA_ERROR = "camera_error"  # 摄像头异常
STATE_UNKNOWN = "unknown"        # 未知状态

# 所有有效状态码列表
ALL_STATE_CODES = [
    STATE_NORMAL,
    STATE_FOCUSED,
    STATE_DISTRACTED,
    STATE_TIRED,
    STATE_AWAY,
    STATE_RETURN,
    STATE_STUDY_LONG,
    STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR,
    STATE_UNKNOWN,
]

# 状态码 → 中文名称映射
STATE_NAME_MAP = {
    STATE_NORMAL: "正常状态",
    STATE_FOCUSED: "专注学习",
    STATE_DISTRACTED: "疑似分心",
    STATE_TIRED: "疑似疲劳",
    STATE_AWAY: "离开座位",
    STATE_RETURN: "回到座位",
    STATE_STUDY_LONG: "学习过久",
    STATE_LOW_LIGHT: "环境偏暗",
    STATE_CAMERA_ERROR: "摄像头异常",
    STATE_UNKNOWN: "未知状态",
}


def create_empty_state(state_code: str = STATE_UNKNOWN) -> dict:
    """
    创建一个默认的空状态字典（用于初始化或错误降级）

    :param state_code: 状态码
    :return: 标准格式的状态字典
    """
    return {
        "state_code": state_code,
        "state_name": STATE_NAME_MAP.get(state_code, "未知状态"),
        "description": "",
        "tags": [],
        "confidence": 0.0,
        "duration": 0.0,
        "need_response": False,
        "suggestion": "",
        "source": [],
    }


def is_valid_state(state: dict) -> bool:
    """
    验证状态字典是否符合标准格式

    :param state: 状态字典
    :return: True 如果格式合法
    """
    required_keys = [
        "state_code", "state_name", "description", "tags",
        "confidence", "duration", "need_response", "suggestion", "source",
    ]
    return all(k in state for k in required_keys)


# TO_DO: UserStateDetector 类 - 对接到 MediaPipe 和 Qwen-VL 模块


class UserStateDetector:
    """
    用户状态检测器

    整合上游模块（MediaPipe 姿态检测、Qwen-VL 视觉理解），
    输出统一格式的用户状态字典，供桌宠状态系统和对话系统调用。

    用法示例:
        detector = UserStateDetector()
        detector.start()
        state = detector.get_state()  # 返回统一格式的状态字典
        state_code = state["state_code"]  # 例如 "distracted"
    """

    def __init__(self):
        """
        初始化检测器

        TO_DO:
        - 初始化 MediaPipe 姿态检测器
        - 初始化 Qwen-VL API 客户端（从 .env 读取 key）
        - 加载历史状态缓存
        """
        # 当前状态（初始为 unknown）
        self._current_state: dict = create_empty_state(STATE_UNKNOWN)

        # 检测器是否正在运行
        self._is_running: bool = False

        # 检测帧率控制（每秒检测次数）
        self._detect_interval: float = 2.0  # 秒

        # TO_DO: 初始化 MediaPipe 姿态检测器
        # self._pose_detector = ...

        # TO_DO: 初始化 Qwen-VL API 客户端
        # from models.vision.qwen_vl_api import QwenVLClient
        # self._vl_client = QwenVLClient(api_key=os.getenv("QWEN_VL_API_KEY"))

    # TO_DO: start() 方法 - 启动检测线程
    def start(self):
        """
        启动用户状态检测（后台循环检测）

        TO_DO:
        - 启动独立线程，定期捕获摄像头画面
        - 调用 MediaPipe 分析人体姿态
        - 必要时调用 Qwen-VL 做视觉理解
        - 综合判断用户状态并更新 _current_state
        - 异常处理：摄像头不可用时返回 camera_error
        """
        self._is_running = True
        print("[UserStateDetector] 检测器启动... (stub)")

        # TO_DO: 启动后台检测线程
        # import threading
        # self._detect_thread = threading.Thread(target=self._detect_loop, daemon=True)
        # self._detect_thread.start()

    # TO_DO: stop() 方法 - 停止检测线程
    def stop(self):
        """
        停止用户状态检测

        TO_DO:
        - 停止检测线程
        - 释放摄像头资源
        - 清理 MediaPipe 等资源
        """
        self._is_running = False
        print("[UserStateDetector] 检测器停止... (stub)")

    # TO_DO: get_state() 方法 - 获取当前用户状态
    def get_state(self) -> dict:
        """
        获取当前用户状态（统一字典格式）

        :return: 标准格式的状态字典

        返回格式:
        {
            "state_code": "distracted",    # 状态大类（见顶部常量定义）
            "state_name": "疑似分心",       # 中文名称
            "description": "用户低头时间较长，画面中疑似出现手机，注意力可能分散。",
            "tags": ["低头", "疑似看手机", "注意力分散"],
            "confidence": 0.82,            # 置信度 0.0-1.0
            "duration": 12.5,              # 该状态持续秒数
            "need_response": True,         # 是否需要桌宠主动回应
            "suggestion": "建议桌宠用轻松语气提醒用户回到学习任务。",
            "source": ["mediapipe", "qwen_vl"]  # 数据来源模块
        }
        """
        # TO_DO: 返回最新的综合状态
        # 在 demo 阶段返回模拟数据
        return self._current_state

    # TO_DO: _detect_loop() - 内部检测循环
    def _detect_loop(self):
        """
        内部检测循环（后台线程运行）

        TO_DO:
        - 定期捕获摄像头图像
        - 运行 MediaPipe 人体姿态估计
        - 根据姿态判断：是否离开/低头/疲劳等
        - 必要时调用 Qwen-VL 做进一步判断
        - 综合多个来源更新 _current_state
        - 记录状态持续时间 duration
        """
        import time
        while self._is_running:
            # TO_DO: 实际的检测逻辑
            # frame = self._capture_frame()
            # mp_result = self._run_mediapipe(frame)
            # vl_result = self._run_qwen_vl(frame) if need_vl else None
            # self._current_state = self._fuse_results(mp_result, vl_result)
            time.sleep(self._detect_interval)

    # TO_DO: set_mock_state() - 设置模拟状态（用于测试）
    def set_mock_state(self, state_code: str = STATE_DISTRACTED):
        """
        设置一个模拟用户状态（用于 demo 和测试）

        :param state_code: 要模拟的状态码
        """
        mock_states = {
            STATE_NORMAL: {
                "state_code": STATE_NORMAL,
                "state_name": "正常状态",
                "description": "用户姿态正常，正在注视屏幕。",
                "tags": ["正常", "注视屏幕"],
                "confidence": 0.95,
                "duration": 30.0,
                "need_response": False,
                "suggestion": "",
                "source": ["mediapipe"],
            },
            STATE_FOCUSED: {
                "state_code": STATE_FOCUSED,
                "state_name": "专注学习",
                "description": "用户正在专注学习，头部稳定，视线集中于屏幕。",
                "tags": ["专注", "学习", "稳定"],
                "confidence": 0.91,
                "duration": 45.0,
                "need_response": False,
                "suggestion": "保持安静，不打扰用户。",
                "source": ["mediapipe"],
            },
            STATE_DISTRACTED: {
                "state_code": STATE_DISTRACTED,
                "state_name": "疑似分心",
                "description": "用户低头时间较长，画面中疑似出现手机，注意力可能分散。",
                "tags": ["低头", "疑似看手机", "注意力分散"],
                "confidence": 0.82,
                "duration": 12.5,
                "need_response": True,
                "suggestion": "建议桌宠用轻松语气提醒用户回到学习任务。",
                "source": ["mediapipe", "qwen_vl"],
            },
            STATE_TIRED: {
                "state_code": STATE_TIRED,
                "state_name": "疑似疲劳",
                "description": "用户频繁打哈欠，眨眼频率降低，姿态松弛，疑似疲劳。",
                "tags": ["哈欠", "眨眼减少", "姿态松弛"],
                "confidence": 0.78,
                "duration": 60.0,
                "need_response": True,
                "suggestion": "建议桌宠关心用户，提醒休息或喝水。",
                "source": ["mediapipe", "qwen_vl"],
            },
            STATE_AWAY: {
                "state_code": STATE_AWAY,
                "state_name": "离开座位",
                "description": "摄像头画面中未检测到用户，已离开座位。",
                "tags": ["无人", "离开"],
                "confidence": 0.98,
                "duration": 120.0,
                "need_response": False,
                "suggestion": "桌宠可进入待机状态。",
                "source": ["mediapipe"],
            },
            STATE_RETURN: {
                "state_code": STATE_RETURN,
                "state_name": "回到座位",
                "description": "用户刚刚回到座位，姿态正在恢复。",
                "tags": ["回到座位", "欢迎"],
                "confidence": 0.85,
                "duration": 3.0,
                "need_response": True,
                "suggestion": "建议桌宠热情打招呼，表示欢迎回来。",
                "source": ["mediapipe"],
            },
            STATE_STUDY_LONG: {
                "state_code": STATE_STUDY_LONG,
                "state_name": "学习过久",
                "description": "用户已连续学习较长时间，建议适当休息。",
                "tags": ["长时间学习", "需要休息"],
                "confidence": 0.75,
                "duration": 3600.0,
                "need_response": True,
                "suggestion": "建议桌宠提醒用户休息，做眼保健操或起身活动。",
                "source": ["mediapipe"],
            },
            STATE_LOW_LIGHT: {
                "state_code": STATE_LOW_LIGHT,
                "state_name": "环境偏暗",
                "description": "环境光照不足，可能影响用户视力。",
                "tags": ["光照不足", "环境暗"],
                "confidence": 0.88,
                "duration": 10.0,
                "need_response": True,
                "suggestion": "建议桌宠提醒用户开灯或调整环境光线。",
                "source": ["qwen_vl"],
            },
            STATE_CAMERA_ERROR: {
                "state_code": STATE_CAMERA_ERROR,
                "state_name": "摄像头异常",
                "description": "无法访问摄像头，请检查摄像头连接和权限设置。",
                "tags": ["摄像头", "异常", "无法访问"],
                "confidence": 1.0,
                "duration": 0.0,
                "need_response": False,
                "suggestion": "桌宠可提示用户检查摄像头。",
                "source": ["system"],
            },
            STATE_UNKNOWN: {
                "state_code": STATE_UNKNOWN,
                "state_name": "未知状态",
                "description": "无法确定当前用户状态。",
                "tags": ["未知"],
                "confidence": 0.0,
                "duration": 0.0,
                "need_response": False,
                "suggestion": "",
                "source": [],
            },
        }

        if state_code in mock_states:
            self._current_state = mock_states[state_code]
            print(f"[UserStateDetector] 设置模拟状态: {state_code}")
        else:
            print(f"[UserStateDetector] 未知状态码: {state_code}，使用 unknown")
            self._current_state = mock_states[STATE_UNKNOWN]
