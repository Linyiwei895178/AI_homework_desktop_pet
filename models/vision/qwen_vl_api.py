"""
Qwen-VL 多模态 API 封装（优化版）

作用：
- 输入图片路径或 OpenCV 帧；
- 调用 Qwen-VL / DashScope OpenAI-compatible 接口；
- 输出严格兼容 UserStateDetector.get_state() 的状态 dict。

注意：
- 本文件会自动 load_dotenv()，读取项目根目录 .env。
- 优先读取 QWEN_VL_API_KEY，其次读取 DASHSCOPE_API_KEY。
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

try:
    import requests  # type: ignore
except Exception:
    requests = None

try:
    from models.vision.user_state_detector import (
        STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
        STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
        STATE_CAMERA_ERROR, STATE_UNKNOWN, ALL_STATE_CODES,
        create_empty_state, is_valid_state,
    )
except Exception:
    # 兜底，避免单独复制文件时导入失败
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
    ALL_STATE_CODES = [
        STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
        STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
        STATE_CAMERA_ERROR, STATE_UNKNOWN,
    ]

    def create_empty_state(state_code: str = STATE_UNKNOWN) -> dict:
        return {
            "state_code": state_code,
            "state_name": state_code,
            "description": "",
            "tags": [],
            "confidence": 0.0,
            "duration": 0.0,
            "need_response": False,
            "suggestion": "",
            "source": [],
        }

    def is_valid_state(state: dict) -> bool:
        required = ["state_code", "state_name", "description", "tags", "confidence", "duration", "need_response", "suggestion", "source"]
        return isinstance(state, dict) and all(k in state for k in required)


STATE_NAME_MAP_LOCAL = {
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

DEFAULT_QWEN_PROMPT = """
你是桌面AI宠物项目中的“用户状态感知模块”。
你的任务是根据摄像头画面判断用户当前状态，并生成一个方便 A/C/D 模块调用的结构化状态结果。

请只输出一个 JSON 对象，不要输出 Markdown，不要输出解释性前后缀。

只能从以下 state_code 中选择一个：
normal, focused, distracted, tired, away, return, study_long, low_light, camera_error, unknown

字段必须严格包含：
{
  "state_code": "normal/focused/distracted/tired/away/return/study_long/low_light/camera_error/unknown 中的一个",
  "state_name": "中文状态名",
  "description": "用一句话描述你在画面中看到的具体用户状态",
  "tags": ["中文短标签1", "中文短标签2", "中文短标签3"],
  "confidence": 0.0到1.0之间的小数,
  "need_response": true或false,
  "suggestion": "给桌宠系统看的具体提示词，包括建议表情、动作、语气、是否主动说话、可以说什么类型的话"
}

判断规则：
1. 如果用户正常坐在电脑前，选择 normal，need_response=false。
2. 如果用户认真看屏幕、看书、写字、记笔记，选择 focused，need_response=false。
3. 如果用户低头看手机、频繁偏离屏幕、明显注意力不在学习任务上，选择 distracted。
4. 如果用户闭眼、趴着、捂脸、揉眼睛、困倦、疲惫，选择 tired。
5. 如果画面中没有用户，选择 away。
6. 如果环境明显昏暗，选择 low_light。
7. 如果无法判断，选择 unknown。
8. 如果用户低头、手挡脸、闭眼，但身体或头部仍在画面中，不要判断为 away，应优先判断为 tired 或 distracted。
9. 不要编造无法从画面判断的信息。

need_response 规则：
- normal 和 focused 通常 need_response=false，避免打扰用户。
- tired、distracted、study_long、low_light 通常 need_response=true。
- away 一般 need_response=false，除非画面明确是用户刚离开。
- unknown 默认 need_response=false。

suggestion 写法要求：
- suggestion 是写给 A/C/D 模块看的，不是直接写给用户看的。
- 要具体说明桌宠应该怎么做。
- 可以包含：表情、动作、语气、是否说话、回应方向。
- 不要写空泛的话。

不同状态的 suggestion 示例：
- tired：给桌宠：切换关心/担忧表情，用温柔语气提醒用户休息，不要责备。可以说“你看起来有点累啦，要不要休息两分钟？”
- distracted：给桌宠：切换提醒/疑惑表情，用轻松语气提醒用户回到学习任务，可以轻度玩梗但不要冒犯。
- focused：给桌宠：保持安静陪伴，不主动打扰，可切换为安静/陪伴动作。
- normal：给桌宠：保持普通陪伴即可，不需要主动说话。
- low_light：给桌宠：切换关心表情，提醒用户开灯或调整光线，保护眼睛。
- away：给桌宠：进入等待或待机状态，不要频繁说话。
- return：给桌宠：切换开心表情，欢迎用户回来，并鼓励继续学习。

输出示例：
{
  "state_code": "tired",
  "state_name": "疑似疲劳",
  "description": "用户用手捂脸，眼睛附近被遮挡，看起来比较疲惫。",
  "tags": ["疲惫", "捂脸", "需要休息"],
  "confidence": 0.9,
  "need_response": true,
  "suggestion": "给桌宠：切换关心表情，用温柔语气提醒用户休息，不要责备。可以生成一句不超过30字的轻松关怀语。"
}
""".strip()


class QwenVLClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 25.0,
        max_retries: int = 1,
    ):
        # 再 load 一次，保证从测试文件直接创建 client 时也能读到 .env
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except Exception:
            pass

        self.api_key = (
            api_key
            or os.getenv("QWEN_VL_API_KEY", "")
            or os.getenv("DASHSCOPE_API_KEY", "")
        )
        self.api_url = api_url or os.getenv(
            "QWEN_VL_API_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.model = model or os.getenv("QWEN_VL_MODEL", "qwen-vl-plus")
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))

    def analyze_image(self, image_path: str) -> dict:
        return self.analyze_image_with_prompt(image_path, DEFAULT_QWEN_PROMPT)

    def analyze_image_with_prompt(self, image_path: str, prompt: str) -> dict:
        image_file = Path(image_path)
        if not image_file.exists():
            return self._fallback_state(
                STATE_CAMERA_ERROR,
                description=f"图片文件不存在：{image_path}",
                tags=["图片不存在", "qwen_vl"],
                confidence=1.0,
                suggestion="请检查截图保存路径。",
            )

        if requests is None:
            return self._fallback_state(
                STATE_UNKNOWN,
                description="未安装 requests，无法调用 Qwen-VL。",
                tags=["缺少依赖", "requests"],
                confidence=1.0,
                suggestion="请先执行 pip install requests。",
            )

        if not self.api_key:
            return self._fallback_state(
                STATE_UNKNOWN,
                description="未配置 Qwen-VL API Key，跳过多模态分析。",
                tags=["未配置APIKey", "qwen_vl"],
                confidence=0.0,
                suggestion="如需启用视觉大模型，请在 .env 中配置 QWEN_VL_API_KEY。",
            )

        try:
            data_url = self._image_to_data_url(str(image_file))
            payload = self._build_payload(data_url=data_url, prompt=prompt)
            headers = self._build_headers()
        except Exception as exc:
            return self._fallback_state(
                STATE_CAMERA_ERROR,
                description=f"图片编码失败：{exc}",
                tags=["图片编码失败"],
                confidence=1.0,
                suggestion="请检查图片格式或重新截图。",
            )

        last_error: Optional[Exception] = None
        for retry in range(self.max_retries + 1):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
                response.raise_for_status()
                raw_json = response.json()
                raw_text = self._extract_text_from_response(raw_json)
                state = self._parse_model_text(raw_text)
                state["source"] = self._merge_source(state.get("source", []), "qwen_vl")
                return self._normalize_state(state)
            except Exception as exc:
                last_error = exc
                if retry < self.max_retries:
                    time.sleep(0.8 * (retry + 1))

        return self._fallback_state(
            STATE_UNKNOWN,
            description=f"Qwen-VL 调用失败：{last_error}",
            tags=["qwen_vl失败"],
            confidence=0.0,
            suggestion="可先使用本地规则检测结果，稍后重试视觉大模型。",
        )

    def analyze_frame(self, frame: Any, prompt: str = DEFAULT_QWEN_PROMPT) -> dict:
        try:
            import cv2  # type: ignore
        except Exception:
            return self._fallback_state(
                STATE_UNKNOWN,
                description="未安装 opencv-python，无法保存摄像头帧给 Qwen-VL。",
                tags=["缺少依赖", "opencv"],
                confidence=1.0,
                suggestion="请先执行 pip install opencv-python。",
            )

        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp_path = tmp.name
            # 压缩图片，降低 API 开销和上传耗时
            cv2.imwrite(tmp_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            return self.analyze_image_with_prompt(tmp_path, prompt)
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, data_url: str, prompt: str) -> dict:
        if "compatible-mode" in self.api_url or "chat/completions" in self.api_url:
            return {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "temperature": 0.2,
            }

        return {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": data_url},
                            {"text": prompt},
                        ],
                    }
                ]
            },
            "parameters": {"temperature": 0.2},
        }

    @staticmethod
    def _image_to_data_url(image_path: str) -> str:
        suffix = Path(image_path).suffix.lower()
        mime = "image/jpeg"
        if suffix == ".png":
            mime = "image/png"
        elif suffix in {".webp"}:
            mime = "image/webp"
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    @staticmethod
    def _extract_text_from_response(raw_json: dict) -> str:
        # OpenAI-compatible
        try:
            content = raw_json["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        texts.append(str(item.get("text", "")))
                    else:
                        texts.append(str(item))
                return "\n".join(t for t in texts if t)
        except Exception:
            pass

        # DashScope old style
        try:
            output = raw_json.get("output", {})
            choices = output.get("choices", [])
            if choices:
                msg_content = choices[0].get("message", {}).get("content", [])
                if isinstance(msg_content, str):
                    return msg_content
                if isinstance(msg_content, list):
                    texts = []
                    for item in msg_content:
                        if isinstance(item, dict):
                            texts.append(str(item.get("text", "")))
                    return "\n".join(t for t in texts if t)
        except Exception:
            pass

        return json.dumps(raw_json, ensure_ascii=False)

    def _parse_model_text(self, text: str) -> dict:
        text = text.strip()
        data: Optional[dict] = None

        # 去掉 markdown 代码块
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except Exception:
            # 从文本中抠第一个 JSON 对象
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception:
                    data = None

        if not isinstance(data, dict):
            return self._fallback_state(
                STATE_UNKNOWN,
                description=f"Qwen-VL 返回内容无法解析：{text[:120]}",
                tags=["解析失败"],
                confidence=0.0,
                suggestion="可继续使用本地规则检测结果。",
            )

        return self._normalize_state(data)

    def _normalize_state(self, state: dict) -> dict:
        code = str(state.get("state_code", STATE_UNKNOWN)).strip()
        code = self._map_state_code(code)
        normalized = create_empty_state(code)
        normalized.update({
            "state_code": code,
            "state_name": STATE_NAME_MAP_LOCAL.get(code, state.get("state_name", "未知状态")),
            "description": str(state.get("description", "") or ""),
            "tags": self._normalize_tags(state.get("tags", [])),
            "confidence": self._normalize_confidence(state.get("confidence", 0.0)),
            "duration": 0.0,
            "need_response": bool(state.get("need_response", False)),
            "suggestion": str(state.get("suggestion", "") or ""),
            "source": self._merge_source([], state.get("source", [])),
        })

        # 正常/专注默认不主动打扰，避免桌宠话太多
        if normalized["state_code"] in {STATE_NORMAL, STATE_FOCUSED}:
            normalized["need_response"] = False
        return normalized

    @staticmethod
    def _map_state_code(code: str) -> str:
        lower = code.lower().strip()
        alias = {
            "正常": STATE_NORMAL,
            "正常状态": STATE_NORMAL,
            "专注": STATE_FOCUSED,
            "专注学习": STATE_FOCUSED,
            "分心": STATE_DISTRACTED,
            "疑似分心": STATE_DISTRACTED,
            "疲惫": STATE_TIRED,
            "疲劳": STATE_TIRED,
            "疑似疲劳": STATE_TIRED,
            "离开": STATE_AWAY,
            "离开座位": STATE_AWAY,
            "回来": STATE_RETURN,
            "回到座位": STATE_RETURN,
            "学习过久": STATE_STUDY_LONG,
            "环境偏暗": STATE_LOW_LIGHT,
            "摄像头异常": STATE_CAMERA_ERROR,
            "未知": STATE_UNKNOWN,
            "未知状态": STATE_UNKNOWN,
        }
        if lower in ALL_STATE_CODES:
            return lower
        return alias.get(code, STATE_UNKNOWN)

    @staticmethod
    def _normalize_tags(tags: Any) -> list:
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            return []
        result = []
        for tag in tags:
            t = str(tag).strip()
            if t and t not in result:
                result.append(t)
        return result[:8]

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            conf = float(value)
            if conf > 1.0:
                conf /= 100.0
            return round(max(0.0, min(1.0, conf)), 2)
        except Exception:
            return 0.0

    def _fallback_state(
        self,
        state_code: str,
        description: str,
        tags: Optional[list] = None,
        confidence: float = 0.0,
        suggestion: str = "",
    ) -> dict:
        state = create_empty_state(state_code if state_code in ALL_STATE_CODES else STATE_UNKNOWN)
        state.update({
            "description": description,
            "tags": list(tags or []),
            "confidence": self._normalize_confidence(confidence),
            "duration": 0.0,
            "need_response": False,
            "suggestion": suggestion,
            "source": ["qwen_vl"],
        })
        return self._normalize_state(state)

    @staticmethod
    def _merge_source(existing: Any, new_item: Any) -> list:
        result = []
        items = []
        if isinstance(existing, list):
            items.extend(existing)
        elif existing:
            items.append(existing)
        if isinstance(new_item, list):
            items.extend(new_item)
        elif new_item:
            items.append(new_item)
        for item in items:
            text = str(item)
            if text and text not in result:
                result.append(text)
        return result


# 兼容旧接口：如果其他模块临时调用这些函数，也不会炸

def get_user_expression(image_path: str) -> dict:
    client = QwenVLClient()
    return client.analyze_image(image_path)


def get_user_state(image_path: str) -> dict:
    client = QwenVLClient()
    return client.analyze_image(image_path)
