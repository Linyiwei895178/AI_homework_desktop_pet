"""Collect offline user-state feature samples from a webcam.

Keys:
    n = normal
    f = focused
    d = distracted
    t = tired
    q = quit

Output:
    data/user_state_dataset/user_state_samples.csv
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.vision.user_state_detector import FACE_LANDMARKER_MODEL_PATH  # noqa: E402
from models.vision.user_state_features import (  # noqa: E402
    USER_STATE_FEATURE_FIELDS,
    UserStateFeatureExtractor,
)


DATASET_PATH = PROJECT_ROOT / "data" / "user_state_dataset" / "user_state_samples.csv"
LABEL_BY_KEY = {
    ord("n"): "normal",
    ord("f"): "focused",
    ord("d"): "distracted",
    ord("t"): "tired",
}


def _create_face_landmarker() -> tuple[Any, Any, Any]:
    if not FACE_LANDMARKER_MODEL_PATH.exists():
        raise FileNotFoundError(
            "face_landmarker.task not found: "
            f"{FACE_LANDMARKER_MODEL_PATH}. Put the model there before collecting."
        )

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
    return mp, vision, vision.FaceLandmarker.create_from_options(options)


def _timestamp_ms(last_timestamp_ms: int) -> int:
    value = int(time.time() * 1000)
    if value <= last_timestamp_ms:
        value = last_timestamp_ms + 1
    return value


def _write_sample(path: Path, features: dict[str, float], label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    fieldnames = ["timestamp"] + [field for field in USER_STATE_FEATURE_FIELDS if field != "timestamp"] + ["label"]
    row = {"timestamp": features.get("timestamp", time.time()), "label": label}
    for field in USER_STATE_FEATURE_FIELDS:
        if field == "timestamp":
            continue
        row[field] = features.get(field, 0.0)

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _draw_overlay(frame: Any, label: str, sample_count: int, last_saved: float) -> Any:
    import cv2  # type: ignore

    text = [
        f"label: {label}",
        f"samples: {sample_count}",
        "keys: n normal | f focused | d distracted | t tired | q quit",
        f"last_save_age: {max(0.0, time.time() - last_saved):.1f}s",
    ]
    y = 28
    for line in text:
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 255), 2, cv2.LINE_AA)
        y += 28
    return frame


def main() -> int:
    try:
        import cv2  # type: ignore
    except Exception as exc:
        print(f"[CollectUserStateDataset] OpenCV unavailable: {exc}")
        return 1

    try:
        mp, _vision, face_landmarker = _create_face_landmarker()
    except Exception as exc:
        print(f"[CollectUserStateDataset] MediaPipe FaceLandmarker unavailable: {exc}")
        return 1

    camera_index = int(os.getenv("DESKTOP_PET_CAMERA_INDEX", "0") or 0)
    sample_interval = float(os.getenv("USER_STATE_SAMPLE_INTERVAL", "0.3") or 0.3)
    current_label = "normal"
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    sample_count = 0
    last_saved_at = 0.0
    last_timestamp_ms = 0

    cap = cv2.VideoCapture(camera_index)
    if not cap or not cap.isOpened():
        print("[CollectUserStateDataset] Camera unavailable.")
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

    print(f"[CollectUserStateDataset] Saving to: {DATASET_PATH}")
    print("[CollectUserStateDataset] Press n/f/d/t to switch labels, q to quit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[CollectUserStateDataset] Failed to read camera frame.")
                time.sleep(0.1)
                continue

            result = None
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                last_timestamp_ms = _timestamp_ms(last_timestamp_ms)
                result = face_landmarker.detect_for_video(mp_image, last_timestamp_ms)
            except Exception as exc:
                print(f"[CollectUserStateDataset] FaceLandmarker detect failed: {exc}")

            now = time.time()
            features = extractor.update(frame, result, timestamp=now)
            if now - last_saved_at >= sample_interval:
                _write_sample(DATASET_PATH, features, current_label)
                sample_count += 1
                last_saved_at = now

            preview = _draw_overlay(frame.copy(), current_label, sample_count, last_saved_at)
            cv2.imshow("User State Dataset Collector", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key in LABEL_BY_KEY:
                current_label = LABEL_BY_KEY[key]
                print(f"[CollectUserStateDataset] label -> {current_label}")
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

    print(f"[CollectUserStateDataset] Done. samples={sample_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
