#!/usr/bin/env python3
"""
生成最简单的 Live2D 走路动作 walk.motion3.json（Cubism 4.0+ / motion3.json Version 3）。

曲线：ParamAngleX、ParamBodyAngleZ 在 1 秒内 -5 → 5 → -5 三角波，循环播放。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MOTION_VERSION = 3
DURATION = 1.0
FPS = 30.0
VALUE_MIN = -5.0
VALUE_MAX = 5.0

# 三角波关键帧：t=0 → -5，t=0.5 → 5，t=1.0 → -5（与起点相同，便于 Loop）
TRIANGLE_KEYFRAMES: tuple[tuple[float, float], ...] = (
    (0.0, VALUE_MIN),
    (0.5, VALUE_MAX),
    (1.0, VALUE_MIN),
)


def build_linear_segments(keyframes: tuple[tuple[float, float], ...]) -> list[float]:
    """
    将关键帧序列编码为 motion3.json 的 Segments 扁平数组。

    格式（CubismSpecs）：
      [t0, v0, segType, t1, v1, segType, t2, v2, ...]
    segType 0 = 线性段。
    """
    if len(keyframes) < 2:
        raise ValueError("至少需要两个关键帧")

    segments: list[float] = [keyframes[0][0], keyframes[0][1]]
    for t, v in keyframes[1:]:
        segments.extend([0, t, v])
    return segments


def build_parameter_curve(param_id: str) -> dict[str, Any]:
    return {
        "Target": "Parameter",
        "Id": param_id,
        "Segments": build_linear_segments(TRIANGLE_KEYFRAMES),
    }


def count_segments_and_points(curves: list[dict[str, Any]]) -> tuple[int, int]:
    """统计 Meta.TotalSegmentCount 与 Meta.TotalPointCount。"""
    total_segments = 0
    total_points = 0
    for curve in curves:
        segs = curve["Segments"]
        curve_segments = 0
        i = 2
        while i < len(segs):
            seg_type = int(segs[i])
            if seg_type == 1:
                i += 7
            else:
                i += 3
            curve_segments += 1
        total_segments += curve_segments
        total_points += 1 + curve_segments
    return total_segments, total_points


def build_walk_motion3() -> dict[str, Any]:
    curves = [
        build_parameter_curve("ParamAngleX"),
        build_parameter_curve("ParamBodyAngleZ"),
    ]
    total_segment_count, total_point_count = count_segments_and_points(curves)

    return {
        "Version": MOTION_VERSION,
        "Meta": {
            "Duration": DURATION,
            "Fps": FPS,
            "Loop": True,
            "AreBeziersRestricted": True,
            "FadeInTime": 0.0,
            "FadeOutTime": 0.0,
            "CurveCount": len(curves),
            "TotalSegmentCount": total_segment_count,
            "TotalPointCount": total_point_count,
            "UserDataCount": 0,
            "TotalUserDataSize": 0,
        },
        "Curves": curves,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="生成 Live2D walk.motion3.json（ParamAngleX / ParamBodyAngleZ 三角波循环）"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "assets"
        / "models"
        / "mao_pro_zh"
        / "mao_pro_zh"
        / "runtime"
        / "motions"
        / "walk.motion3.json",
        help="输出文件路径（默认: mao_pro_zh runtime/motions/walk.motion3.json）",
    )
    args = parser.parse_args()

    motion = build_walk_motion3()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(motion, ensure_ascii=False, indent="\t") + "\n",
        encoding="utf-8",
    )
    print(f"已写入: {args.output.resolve()}")
    print(
        f"  Duration={DURATION}s, Loop=True, "
        f"curves=ParamAngleX & ParamBodyAngleZ ({VALUE_MIN} → {VALUE_MAX} → {VALUE_MIN})"
    )


if __name__ == "__main__":
    main()
