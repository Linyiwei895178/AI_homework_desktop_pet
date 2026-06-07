"""
Manual Face Mimic test for Team B vision output.

Run:
    python scripts/test_face_mimic.py

This script does not start the desktop pet UI, TTS, DeepSeek, or Qwen-VL.
"""

from __future__ import annotations

import os
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.vision.user_state_detector import UserStateDetector  # noqa: E402


def _fmt(value: object) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return str(value)


def main() -> None:
    detector = UserStateDetector(
        enable_vlm=False,
        enable_deepface=False,
        enable_face_mimic=True,
        show_preview=False,
    )
    detector.start()
    print("[FaceMimicTest] Started. Press Ctrl+C to stop.")

    try:
        while True:
            mimic = detector.get_face_mimic_state()
            print(
                "expression={expression} "
                "mouth_open={mouth_open} "
                "smile={smile} "
                "eye_blink_left={eye_blink_left} "
                "eye_blink_right={eye_blink_right} "
                "brow_raise={brow_raise} "
                "head_yaw={head_yaw} "
                "head_pitch={head_pitch} "
                "head_roll={head_roll} "
                "source={source}".format(
                    expression=mimic.get("expression", "unknown"),
                    mouth_open=_fmt(mimic.get("mouth_open", 0.0)),
                    smile=_fmt(mimic.get("smile", 0.0)),
                    eye_blink_left=_fmt(mimic.get("eye_blink_left", 0.0)),
                    eye_blink_right=_fmt(mimic.get("eye_blink_right", 0.0)),
                    brow_raise=_fmt(mimic.get("brow_raise", 0.0)),
                    head_yaw=_fmt(mimic.get("head_yaw", 0.0)),
                    head_pitch=_fmt(mimic.get("head_pitch", 0.0)),
                    head_roll=_fmt(mimic.get("head_roll", 0.0)),
                    source=mimic.get("source", []),
                )
            )
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n[FaceMimicTest] Stopping...")
    finally:
        detector.stop()
        print("[FaceMimicTest] Stopped.")


if __name__ == "__main__":
    main()
