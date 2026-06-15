"""Live debug script for the lightweight user-state classifier.

This script does not start the desktop pet UI and does not call DeepFace,
Qwen-VL, DeepSeek, or TTS.

Run:
    set DESKTOP_PET_STATE_DEBUG=true
    python scripts/test_user_state_live_classifier.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.vision.user_state_classifier import UserStateClassifier  # noqa: E402
from models.vision.user_state_detector import FACE_LANDMARKER_MODEL_PATH  # noqa: E402
from models.vision.user_state_features import UserStateFeatureExtractor  # noqa: E402
from models.vision.user_state_smoother import UserStateSmoother  # noqa: E402


KEY_FEATURES = [
    "head_yaw_mean",
    "head_pitch_mean",
    "eye_closed_ratio",
    "looking_down_ratio",
    "face_missing_ratio",
    "brightness_mean",
]


def _create_face_landmarker() -> tuple[Any, Any]:
    if not FACE_LANDMARKER_MODEL_PATH.exists():
        raise FileNotFoundError(f"FaceLandmarker model not found: {FACE_LANDMARKER_MODEL_PATH}")

    import mediapipe as mp  # type: ignore
    from mediapipe.tasks.python import vision  # type: ignore
    from mediapipe.tasks.python.core.base_options import BaseOptions  # type: ignore

    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(FACE_LANDMARKER_MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
        min_face_detection_confidence=0.45,
        min_face_presence_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    return mp, vision.FaceLandmarker.create_from_options(options)


def _next_timestamp_ms(last_timestamp_ms: int) -> int:
    timestamp_ms = int(time.monotonic() * 1000)
    if timestamp_ms <= last_timestamp_ms:
        timestamp_ms = last_timestamp_ms + 1
    return timestamp_ms


def _format_probs(probs: dict[str, Any]) -> str:
    if not probs:
        return "{}"
    return "{" + ", ".join(f"{key}:{float(value):.2f}" for key, value in sorted(probs.items())) + "}"


def _format_features(features: dict[str, Any]) -> str:
    return ", ".join(f"{key}={float(features.get(key, 0.0) or 0.0):.3f}" for key in KEY_FEATURES)


def _draw_overlay(frame: Any, classifier_result: dict, smoother_result: dict) -> Any:
    import cv2  # type: ignore

    debug = classifier_result.get("debug_info", {}) if isinstance(classifier_result, dict) else {}
    lines = [
        f"raw: {debug.get('raw_top_label', 'unknown')}({float(debug.get('raw_top_confidence', 0.0) or 0.0):.2f})",
        f"threshold: {classifier_result.get('state_code', 'unknown')}  reason: {debug.get('threshold_reason', '')}",
        f"smooth: {smoother_result.get('state_code', 'unknown')}  candidate: {smoother_result.get('candidate_state')}",
        "press q to quit",
    ]
    y = 28
    for line in lines:
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (0, 255, 255), 2, cv2.LINE_AA)
        y += 26
    return frame


def main() -> int:
    try:
        import cv2  # type: ignore
    except Exception as exc:
        print(f"[LiveUserStateClassifier] OpenCV unavailable: {exc}")
        return 1

    try:
        mp, face_landmarker = _create_face_landmarker()
    except Exception as exc:
        print(f"[LiveUserStateClassifier] MediaPipe FaceLandmarker unavailable: {exc}")
        return 1

    camera_index = int(os.getenv("DESKTOP_PET_CAMERA_INDEX", "0") or 0)
    cap = cv2.VideoCapture(camera_index)
    if not cap or not cap.isOpened():
        print("[LiveUserStateClassifier] Camera unavailable.")
        try:
            face_landmarker.close()
        except Exception:
            pass
        return 1

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    classifier = UserStateClassifier()
    smoother = UserStateSmoother()
    last_timestamp_ms = 0
    last_print_at = 0.0

    print("[LiveUserStateClassifier] Started. Press q to quit.")
    print(
        "[LiveUserStateClassifier] thresholds: "
        f"min={classifier.min_conf}, focused={classifier.focused_conf}, "
        f"distracted={classifier.distracted_conf}, tired={classifier.tired_conf}"
    )
    print(f"[LiveUserStateClassifier] classifier_available={classifier.available}, features={len(classifier.feature_names)}")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            result = None
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                last_timestamp_ms = _next_timestamp_ms(last_timestamp_ms)
                result = face_landmarker.detect_for_video(mp_image, last_timestamp_ms)
            except Exception as exc:
                print(f"[LiveUserStateClassifier] detect failed: {exc}")

            now = time.time()
            features = extractor.update(frame=frame, face_landmarker_result=result, timestamp=now)
            classifier_result = classifier.predict(features)
            smoother_result = smoother.update(classifier_result.get("state_code", "normal"), now=now)

            if now - last_print_at >= 0.5:
                last_print_at = now
                debug = classifier_result.get("debug_info", {})
                print(
                    "[LiveUserStateClassifier] "
                    f"probs={_format_probs(debug.get('raw_probs', {}))} "
                    f"top={debug.get('raw_top_label', 'unknown')}({float(debug.get('raw_top_confidence', 0.0) or 0.0):.2f}) "
                    f"threshold={classifier_result.get('state_code')} "
                    f"smooth={smoother_result.get('state_code')} "
                    f"reason={debug.get('threshold_reason', classifier_result.get('reason'))} "
                    f"features: {_format_features(features)}"
                )

            preview = _draw_overlay(frame.copy(), classifier_result, smoother_result)
            cv2.imshow("Live User State Classifier Debug", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        cap.release()
        try:
            face_landmarker.close()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    print("[LiveUserStateClassifier] Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
