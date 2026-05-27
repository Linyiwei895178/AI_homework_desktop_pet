"""
EmotionRecognizer - 面部表情识别增强模块（保守版）

作用：
1. 使用 DeepFace 现成表情识别能力，识别用户面部表情倾向。
2. 支持 angry / disgust / fear / happy / sad / surprise / neutral 等基础表情。
3. 不新增、不修改 UserStateDetector 已固定的 state_code。
4. 表情结果只作为辅助证据，写入 tags / description / suggestion / source。

重要说明：
- 本模块识别的是“表情倾向”，不是心理诊断。
- 输出文本统一使用“疑似、倾向、可能”等保守措辞。
- 低置信度或类别分数差距太小的结果会被过滤为 unknown，避免用户明明没做表情却被强行判定。

建议用法：
    recognizer = EmotionRecognizer()
    emotion = recognizer.analyze_frame(frame)
    state = recognizer.enhance_state(state, emotion)
"""

from __future__ import annotations

import copy
import time
from collections import Counter, deque
from typing import Any, Deque, Optional


# ========== 与 user_state_detector.py 保持兼容的状态大类 ==========
STATE_NORMAL = "normal"
STATE_FOCUSED = "focused"
STATE_DISTRACTED = "distracted"
STATE_TIRED = "tired"
STATE_AWAY = "away"
STATE_RETURN = "return"
STATE_STUDY_LONG = "study_long"
STATE_LOW_LIGHT = "low_light"
STATE_CAMERA_ERROR = "camera_error"
STATE_UNKNOWN = "unknown"


class EmotionRecognizer:
    """
    DeepFace 表情识别封装类（保守版）。

    设计原则：
    - DeepFace 可能比较慢，所以默认做调用间隔控制。
    - DeepFace 可能受光线、角度、遮挡影响，所以只把结果作为“辅助证据”。
    - 低置信度或 top1/top2 差距过小的结果不影响最终状态。
    - 表情识别不直接覆盖 away / camera_error / low_light 等硬状态。
    """

    EMOTION_NAME_MAP = {
        "angry": "疑似烦躁",
        "disgust": "疑似不适",
        "fear": "疑似紧张",
        "happy": "表情积极",
        "sad": "表情低落",
        "surprise": "疑似惊讶",
        "neutral": "表情平静",
        "unknown": "未知表情",
    }

    EMOTION_TAG_MAP = {
        "angry": ["疑似烦躁", "表情紧绷", "状态波动"],
        "disgust": ["疑似不适", "状态波动"],
        "fear": ["疑似紧张", "疑似不安", "状态波动"],
        "happy": ["表情积极", "状态较轻松"],
        "sad": ["表情低落", "状态可能不佳", "需要陪伴"],
        "surprise": ["疑似惊讶", "注意力波动"],
        "neutral": ["表情平静"],
        "unknown": [],
    }

    # 表情结果映射到现有 state_code 的建议，不新增 state_code
    EMOTION_TO_STATE_HINT = {
        "happy": STATE_NORMAL,
        "neutral": STATE_NORMAL,
        "sad": STATE_TIRED,
        "angry": STATE_DISTRACTED,
        "fear": STATE_DISTRACTED,
        "surprise": STATE_DISTRACTED,
        "disgust": STATE_DISTRACTED,
        "unknown": STATE_UNKNOWN,
    }

    EMOTION_DESCRIPTION_MAP = {
        "angry": "表情识别结果显示用户面部特征偏紧绷，可能存在烦躁倾向。",
        "disgust": "表情识别结果显示用户面部特征可能存在不适或厌烦倾向。",
        "fear": "表情识别结果显示用户面部特征可能存在紧张或不安倾向。",
        "happy": "表情识别结果显示用户表情较积极，状态可能较轻松。",
        "sad": "表情识别结果显示用户表情偏低落，可能状态不佳。",
        "surprise": "表情识别结果显示用户表情有惊讶倾向，注意力可能出现波动。",
        "neutral": "表情识别结果显示用户表情较平静。",
        "unknown": "暂未获得可靠的表情识别结果。",
    }

    EMOTION_SUGGESTION_MAP = {
        "angry": "给桌宠：可切换安抚/关心表情，用轻松温和的语气缓和用户状态，不要责备。",
        "disgust": "给桌宠：可切换关心表情，温和询问用户是否需要调整状态或休息一下。",
        "fear": "给桌宠：可切换陪伴表情，用稳定、鼓励的语气降低用户紧张感。",
        "happy": "给桌宠：保持轻松陪伴，可切换开心表情，不需要频繁打扰。",
        "sad": "给桌宠：可切换温柔陪伴表情，用鼓励语气安慰用户，不要说教。",
        "surprise": "给桌宠：可切换疑惑/好奇表情，轻声询问用户是否遇到问题。",
        "neutral": "给桌宠：保持普通陪伴即可，不需要主动说话。",
        "unknown": "",
    }

    def __init__(
        self,
        enabled: bool = True,
        min_confidence: float = 0.70,
        min_margin: float = 0.18,
        analyze_interval: float = 2.0,
        smoothing_window: int = 3,
        enforce_detection: bool = False,
        detector_backend: str = "opencv",
        silent: bool = True,
    ):
        """
        enabled:
            是否启用表情识别。

        min_confidence:
            最低置信度。低于该值时，结果会被视为 unknown，避免误判。

        min_margin:
            第一名和第二名分数的最小差距。差距太小代表模型自己也不确定。
            例如 happy=0.55, angry=0.38，虽然 happy 第一，但差距不够大时不强行影响最终状态。

        analyze_interval:
            最短分析间隔，单位秒。DeepFace 比较慢，不建议每一帧都调用。

        smoothing_window:
            平滑窗口长度。越大越稳，越小反应越快。

        enforce_detection:
            DeepFace 是否强制要求检测到人脸。摄像头场景建议 False。

        detector_backend:
            DeepFace 检测后端。opencv 最轻。

        silent:
            是否减少 DeepFace 输出。
        """
        self.enabled = bool(enabled)
        self.min_confidence = float(min_confidence)
        self.min_margin = float(min_margin)
        self.analyze_interval = max(0.2, float(analyze_interval))
        self.smoothing_window = max(1, int(smoothing_window))
        self.enforce_detection = bool(enforce_detection)
        self.detector_backend = detector_backend
        self.silent = bool(silent)

        self._deepface = None
        self._deepface_import_error: Optional[str] = None

        self._last_analyze_at: float = 0.0
        self._last_result: dict = self._empty_result()
        self._history: Deque[dict] = deque(maxlen=self.smoothing_window)

    # ==================== 对外主接口 ====================

    def analyze_frame(self, frame: Any, force: bool = False) -> dict:
        """
        分析 OpenCV 摄像头帧，返回表情识别结果。
        """
        if not self.enabled:
            return self._empty_result(available=False, error="EmotionRecognizer 未启用。")

        now = time.time()
        if not force and now - self._last_analyze_at < self.analyze_interval:
            return copy.deepcopy(self._last_result)

        self._last_analyze_at = now

        if frame is None:
            result = self._empty_result(available=False, error="输入 frame 为空。")
            self._last_result = result
            return copy.deepcopy(result)

        if not self._load_deepface():
            result = self._empty_result(
                available=False,
                error=f"DeepFace 不可用：{self._deepface_import_error}",
            )
            self._last_result = result
            return copy.deepcopy(result)

        try:
            raw_result = self._deepface.analyze(
                img_path=frame,
                actions=["emotion"],
                enforce_detection=self.enforce_detection,
                detector_backend=self.detector_backend,
                silent=self.silent,
            )
            parsed = self._parse_deepface_result(raw_result)
            smoothed = self._smooth_result(parsed)
            self._last_result = smoothed
            return copy.deepcopy(smoothed)
        except Exception as exc:
            result = self._empty_result(available=False, error=str(exc))
            self._last_result = result
            return copy.deepcopy(result)

    def analyze_image(self, image_path: str, force: bool = True) -> dict:
        """
        分析图片文件路径。适合单独测试 emotion_recognizer.py。
        """
        if not self.enabled:
            return self._empty_result(available=False, error="EmotionRecognizer 未启用。")

        if not self._load_deepface():
            return self._empty_result(
                available=False,
                error=f"DeepFace 不可用：{self._deepface_import_error}",
            )

        if not force:
            now = time.time()
            if now - self._last_analyze_at < self.analyze_interval:
                return copy.deepcopy(self._last_result)
            self._last_analyze_at = now

        try:
            raw_result = self._deepface.analyze(
                img_path=image_path,
                actions=["emotion"],
                enforce_detection=self.enforce_detection,
                detector_backend=self.detector_backend,
                silent=self.silent,
            )
            parsed = self._parse_deepface_result(raw_result)
            smoothed = self._smooth_result(parsed)
            self._last_result = smoothed
            return copy.deepcopy(smoothed)
        except Exception as exc:
            return self._empty_result(available=False, error=str(exc))

    def enhance_state(self, state: dict, emotion_result: Optional[dict] = None) -> dict:
        """
        将表情识别结果融合进 UserStateDetector.get_state() 的返回字典。

        注意：
        - 不新增字段。
        - 不新增 state_code。
        - 只增强 tags / description / suggestion / source。
        - 只有高置信度且差距足够大的结果，才允许辅助影响 normal/unknown/focused。
        """
        if not isinstance(state, dict):
            state = {}

        new_state = copy.deepcopy(state)
        new_state.setdefault("state_code", STATE_UNKNOWN)
        new_state.setdefault("state_name", "未知状态")
        new_state.setdefault("description", "")
        new_state.setdefault("tags", [])
        new_state.setdefault("confidence", 0.0)
        new_state.setdefault("duration", 0.0)
        new_state.setdefault("need_response", False)
        new_state.setdefault("suggestion", "")
        new_state.setdefault("source", [])

        if emotion_result is None:
            emotion_result = copy.deepcopy(self._last_result)

        if not emotion_result or not emotion_result.get("available", False):
            return new_state

        emotion_code = emotion_result.get("emotion_code", "unknown")
        emotion_name = emotion_result.get("emotion_name", "未知表情")
        emotion_conf = float(emotion_result.get("confidence", 0.0) or 0.0)
        margin = float(emotion_result.get("margin", 0.0) or 0.0)

        if emotion_code == "unknown" or emotion_conf < self.min_confidence or margin < self.min_margin:
            return new_state

        # 1. 合并 tags
        tags = list(new_state.get("tags", []) or [])
        for tag in emotion_result.get("tags", []) or []:
            if tag not in tags:
                tags.append(tag)
        if emotion_name and emotion_name != "未知表情":
            tag = f"表情倾向:{emotion_name}"
            if tag not in tags:
                tags.append(tag)
        new_state["tags"] = tags[:10]

        # 2. 增强 description
        desc_add = emotion_result.get("description", "")
        if desc_add and desc_add not in new_state.get("description", ""):
            base_desc = str(new_state.get("description", "") or "").strip()
            new_state["description"] = f"{base_desc} {desc_add}".strip()

        # 3. 增强 suggestion
        sug_add = emotion_result.get("suggestion", "")
        if sug_add:
            base_sug = str(new_state.get("suggestion", "") or "").strip()
            if base_sug and sug_add not in base_sug:
                new_state["suggestion"] = f"{base_sug}；{sug_add}"
            elif not base_sug:
                new_state["suggestion"] = sug_add

        # 4. 合并 source
        sources = list(new_state.get("source", []) or [])
        for src in emotion_result.get("source", []) or ["deepface"]:
            if src not in sources:
                sources.append(src)
        if "emotion_fusion" not in sources:
            sources.append("emotion_fusion")
        new_state["source"] = sources

        # 5. 必要时辅助影响 state_code，但不覆盖硬状态
        current_code = str(new_state.get("state_code", STATE_UNKNOWN))
        state_hint = emotion_result.get("state_hint", STATE_UNKNOWN)
        hard_states = {STATE_AWAY, STATE_RETURN, STATE_CAMERA_ERROR, STATE_LOW_LIGHT, STATE_STUDY_LONG}

        if current_code not in hard_states:
            if state_hint in {STATE_TIRED, STATE_DISTRACTED}:
                if current_code in {STATE_NORMAL, STATE_UNKNOWN, STATE_FOCUSED}:
                    new_state["state_code"] = state_hint
                    new_state["state_name"] = self._state_name(state_hint)
                    new_state["need_response"] = True
            elif state_hint == STATE_NORMAL:
                # 积极/平静只在 unknown 时辅助恢复 normal，不覆盖 tired/distracted。
                if current_code == STATE_UNKNOWN:
                    new_state["state_code"] = STATE_NORMAL
                    new_state["state_name"] = self._state_name(STATE_NORMAL)

        # 6. 提升置信度：取二者较高
        try:
            old_conf = float(new_state.get("confidence", 0.0) or 0.0)
            new_state["confidence"] = round(min(1.0, max(old_conf, emotion_conf)), 2)
        except Exception:
            new_state["confidence"] = round(emotion_conf, 2)

        if new_state.get("state_code") in {STATE_NORMAL, STATE_FOCUSED}:
            new_state["need_response"] = False

        return new_state

    # ==================== 内部工具函数 ====================

    def _load_deepface(self) -> bool:
        if self._deepface is not None:
            return True
        if self._deepface_import_error:
            return False

        try:
            from deepface import DeepFace  # type: ignore
            self._deepface = DeepFace
            return True
        except Exception as exc:
            self._deepface_import_error = str(exc)
            self._deepface = None
            return False

    def _parse_deepface_result(self, raw_result: Any) -> dict:
        """
        DeepFace.analyze 有时返回 list，有时返回 dict，这里统一解析。
        """
        if isinstance(raw_result, list):
            if not raw_result:
                return self._empty_result(available=False, error="DeepFace 返回空列表。")
            raw = raw_result[0]
        elif isinstance(raw_result, dict):
            raw = raw_result
        else:
            return self._empty_result(available=False, error=f"DeepFace 返回类型异常：{type(raw_result)}")

        dominant = str(raw.get("dominant_emotion", "unknown") or "unknown").lower()
        scores = raw.get("emotion", {}) or {}
        if dominant not in self.EMOTION_NAME_MAP:
            dominant = "unknown"

        confidence, margin = self._extract_confidence_and_margin(scores, dominant)

        # 低置信度或分数差距小，直接保守处理为 unknown。
        if confidence < self.min_confidence or margin < self.min_margin:
            return self._build_result(
                emotion_code="unknown",
                confidence=confidence,
                raw=scores,
                available=True,
                error="表情识别置信度不足或类别差距过小，已保守忽略。",
                margin=margin,
            )

        return self._build_result(
            emotion_code=dominant,
            confidence=confidence,
            raw=scores,
            available=True,
            error="",
            margin=margin,
        )

    def _smooth_result(self, result: dict) -> dict:
        """
        简单平滑：
        - 只平滑可用且非 unknown 的结果；
        - 最近窗口中多数表情作为最终输出；
        - 如果当前结果非常高置信度，允许快速响应。
        """
        if not result.get("available", False):
            return result

        emotion_code = result.get("emotion_code", "unknown")
        if emotion_code == "unknown":
            return result

        self._history.append(copy.deepcopy(result))
        if len(self._history) < 2:
            return result

        codes = [r.get("emotion_code", "unknown") for r in self._history]
        most_common_code, _ = Counter(codes).most_common(1)[0]
        related = [r for r in self._history if r.get("emotion_code") == most_common_code]
        if not related:
            return result

        avg_conf = sum(float(r.get("confidence", 0.0) or 0.0) for r in related) / len(related)
        avg_margin = sum(float(r.get("margin", 0.0) or 0.0) for r in related) / len(related)

        smoothed = self._build_result(
            emotion_code=most_common_code,
            confidence=avg_conf,
            raw=result.get("raw", {}),
            available=True,
            error="",
            margin=avg_margin,
        )

        current_conf = float(result.get("confidence", 0.0) or 0.0)
        current_margin = float(result.get("margin", 0.0) or 0.0)
        if current_conf >= 0.90 and current_margin >= 0.30:
            return result

        return smoothed

    def _build_result(
        self,
        emotion_code: str,
        confidence: float,
        raw: Optional[dict] = None,
        available: bool = True,
        error: str = "",
        margin: float = 0.0,
    ) -> dict:
        emotion_code = str(emotion_code or "unknown").lower()
        if emotion_code not in self.EMOTION_NAME_MAP:
            emotion_code = "unknown"

        confidence = self._normalize_confidence(confidence)
        margin = self._normalize_confidence(margin)
        emotion_name = self.EMOTION_NAME_MAP.get(emotion_code, "未知表情")
        state_hint = self.EMOTION_TO_STATE_HINT.get(emotion_code, STATE_UNKNOWN)

        need_response_hint = emotion_code in {"angry", "disgust", "fear", "sad"} and confidence >= self.min_confidence
        if emotion_code == "surprise" and confidence >= 0.80:
            need_response_hint = True
        if emotion_code in {"happy", "neutral", "unknown"}:
            need_response_hint = False

        return {
            "emotion_code": emotion_code,
            "emotion_name": emotion_name,
            "confidence": confidence,
            "margin": margin,
            "state_hint": state_hint,
            "tags": list(self.EMOTION_TAG_MAP.get(emotion_code, [])),
            "description": self.EMOTION_DESCRIPTION_MAP.get(emotion_code, ""),
            "suggestion": self.EMOTION_SUGGESTION_MAP.get(emotion_code, ""),
            "need_response_hint": need_response_hint,
            "available": bool(available),
            "source": ["deepface"],
            "raw": raw or {},
            "error": error or "",
        }

    def _empty_result(
        self,
        emotion_code: str = "unknown",
        available: bool = False,
        error: str = "",
    ) -> dict:
        return self._build_result(
            emotion_code=emotion_code,
            confidence=0.0,
            raw={},
            available=available,
            error=error,
            margin=0.0,
        )

    @staticmethod
    def _extract_confidence_and_margin(scores: Any, dominant: str) -> tuple[float, float]:
        if not isinstance(scores, dict):
            return 0.0, 0.0

        normalized_scores = []
        for _, value in scores.items():
            conf = EmotionRecognizer._normalize_confidence(value)
            normalized_scores.append(conf)

        if not normalized_scores:
            return 0.0, 0.0

        normalized_scores.sort(reverse=True)
        top1 = EmotionRecognizer._normalize_confidence(scores.get(dominant, 0.0))
        top2 = normalized_scores[1] if len(normalized_scores) >= 2 else 0.0
        margin = max(0.0, top1 - top2)
        return top1, margin

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            conf = float(value)
            if conf > 1.0:
                conf /= 100.0
            return round(max(0.0, min(1.0, conf)), 2)
        except Exception:
            return 0.0

    @staticmethod
    def _state_name(state_code: str) -> str:
        mapping = {
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
        return mapping.get(state_code, "未知状态")


if __name__ == "__main__":
    recognizer = EmotionRecognizer()
    print("EmotionRecognizer 初始化完成。")
    print("DeepFace 可用状态：", recognizer._load_deepface())
    if recognizer._deepface_import_error:
        print("DeepFace 导入错误：", recognizer._deepface_import_error)
