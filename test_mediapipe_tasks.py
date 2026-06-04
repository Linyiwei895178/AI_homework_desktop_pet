from __future__ import annotations

import sys
from pathlib import Path


MODEL_PATH = Path(__file__).resolve().parent / "models" / "vision" / "mediapipe_models" / "face_landmarker.task"


def main() -> int:
    print(f"[MediaPipe Tasks Check] python={sys.version.split()[0]}")

    try:
        import mediapipe as mp  # type: ignore
    except Exception as exc:
        print(f"[MediaPipe Tasks Check] mediapipe 导入失败：{exc}")
        return 0

    print(f"[MediaPipe Tasks Check] mediapipe={getattr(mp, '__version__', 'unknown')}")
    print(f"[MediaPipe Tasks Check] mediapipe_file={getattr(mp, '__file__', 'unknown')}")
    print(f"[MediaPipe Tasks Check] has_mp_solutions={hasattr(mp, 'solutions')}")

    try:
        from mediapipe.tasks import python as mp_tasks_python  # type: ignore
        from mediapipe.tasks.python import vision  # type: ignore
        from mediapipe.tasks.python.core.base_options import BaseOptions  # type: ignore
        _ = mp_tasks_python
    except Exception as exc:
        print(f"[MediaPipe Tasks Check] tasks.vision 不可导入：{exc}")
        return 0

    print("[MediaPipe Tasks Check] tasks.vision 可导入。")
    print(f"[MediaPipe Tasks Check] model_path={MODEL_PATH}")
    print(f"[MediaPipe Tasks Check] model_exists={MODEL_PATH.exists()}")

    if not MODEL_PATH.exists():
        print("[MediaPipe Tasks Check] 模型文件不存在，UserStateDetector 会降级到 OpenCV Haar。")
        return 0

    landmarker = None
    try:
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)
        print("[MediaPipe Tasks Check] FaceLandmarker 创建成功。")
    except Exception as exc:
        print(f"[MediaPipe Tasks Check] FaceLandmarker 创建失败：{exc}")
    finally:
        try:
            if landmarker is not None:
                landmarker.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
