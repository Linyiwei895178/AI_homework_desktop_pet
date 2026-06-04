from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ACTION_PRESET_FORMAT = "pet_buddy_live2d_action_preset_catalog_v1"
OUT_FILE = Path("assets/live2d_modeling/pose_study/live2d_action_presets.json")

PARAM_RANGES: dict[str, tuple[float, float]] = {
    "ParamAngleX": (-30.0, 30.0),
    "ParamAngleY": (-20.0, 20.0),
    "ParamAngleZ": (-18.0, 18.0),
    "ParamBodyAngleX": (-18.0, 18.0),
    "ParamBodyAngleY": (-14.0, 14.0),
    "ParamBodyAngleZ": (-16.0, 16.0),
    "ParamHipShiftX": (-1.0, 1.0),
    "ParamHipTiltZ": (-1.0, 1.0),
    "ParamShoulderTiltZ": (-1.0, 1.0),
    "ParamSpineCurve": (-1.0, 1.0),
    "ParamArmLRaise": (0.0, 1.0),
    "ParamArmRRaise": (0.0, 1.0),
    "ParamElbowLBend": (0.0, 1.0),
    "ParamElbowRBend": (0.0, 1.0),
    "ParamLegLStep": (-1.0, 1.0),
    "ParamLegRStep": (-1.0, 1.0),
    "ParamKneeLBend": (0.0, 1.0),
    "ParamKneeRBend": (0.0, 1.0),
    "ParamMuscleDefinition": (0.0, 1.0),
    "ParamConstructionLines": (0.0, 1.0),
}

CATEGORIES = [
    {
        "id": "upright_front_or_back",
        "label": "正立与背面",
        "description": "从 PDF 正面/背面站姿提炼，适合作为待机、呼吸、轻微重心切换。",
        "source_count": 12,
    },
    {
        "id": "side_profile",
        "label": "侧身与回望",
        "description": "从侧面人体线稿提炼，强调头胸胯的转向层级。",
        "source_count": 12,
    },
    {
        "id": "contrapposto_lean",
        "label": "重心与 S 曲线",
        "description": "从斜倚、坐球、单脚支撑等姿态提炼，适合表现松弛和情绪。",
        "source_count": 12,
    },
    {
        "id": "arms_raised_or_overhead",
        "label": "举手与抱头",
        "description": "从手臂上举、抱头、舞蹈式手势提炼，要求肩腋遮挡层。",
        "source_count": 12,
    },
    {
        "id": "wide_action_or_limbs_out",
        "label": "外扩动作",
        "description": "从跳跃、开架、战斗和夸张四肢外扩姿态提炼。",
        "source_count": 12,
    },
    {
        "id": "crouch_low_pose",
        "label": "下蹲跪坐",
        "description": "从跪姿、蹲姿、低重心姿态提炼；深蹲类需要替换腿部和衣摆素材。",
        "source_count": 12,
    },
    {
        "id": "walking_step",
        "label": "走跑步伐",
        "description": "从迈步、跑步和前后腿分离姿态提炼，适合循环动作。",
        "source_count": 12,
    },
    {
        "id": "extra_diversity",
        "label": "互动与表演",
        "description": "结合 zip 动漫线稿中常见互动姿势，补足直播常用动作。",
        "source_count": 12,
    },
]

ACTION_NAMES: dict[str, list[str]] = {
    "upright_front_or_back": [
        "标准正立呼吸",
        "背手正立",
        "单肩放松",
        "低头待机",
        "抬下巴看镜头",
        "脚尖内扣",
        "脚尖外开",
        "手贴侧腰",
        "双手自然垂落",
        "轻微后仰",
        "背面待机",
        "背面回头",
        "肩线微摆",
        "髋部轻摆",
        "上身前探",
        "上身收回",
        "视线左扫",
        "视线右扫",
        "微笑点头",
        "认真站定",
        "紧张缩肩",
        "自信挺胸",
        "脚跟轻踮",
        "轻轻鞠躬",
        "直播开场站姿",
    ],
    "side_profile": [
        "侧身静立",
        "侧身回望",
        "侧身低头",
        "侧身抬头",
        "侧身抱臂",
        "侧身伸手",
        "侧身退步",
        "侧身前倾",
        "侧身后靠",
        "侧身听讲",
        "半侧脸招呼",
        "半侧脸害羞",
        "侧身叉腰",
        "侧身扶脸",
        "侧身轻笑",
        "侧身观察",
        "侧身准备转回",
        "侧身背影",
        "侧身踮脚",
        "侧身垂手",
        "侧身摆裙",
        "侧身握拳",
        "侧身抬臂",
        "侧身入场",
        "侧身退场",
    ],
    "contrapposto_lean": [
        "左重心 S 站姿",
        "右重心 S 站姿",
        "手扶腰斜倚",
        "单脚交叉站",
        "一腿屈膝站",
        "肩胯反向摆",
        "懒散靠边",
        "元气歪身",
        "害羞缩身",
        "自信压胯",
        "手插口袋感",
        "单手托腮站",
        "单膝抬起平衡",
        "舞步收势",
        "轻坐斜倚",
        "坐姿回望",
        "坐球斜倚",
        "跪坐上身弯",
        "背面扭腰",
        "前倾伸肩",
        "侧腰拉伸",
        "肩部回旋",
        "胯部摆动循环",
        "胸胯波浪",
        "收尾定格",
    ],
    "arms_raised_or_overhead": [
        "双手抱头",
        "双手伸懒腰",
        "单手高举",
        "另一手叉腰",
        "双臂圆弧举起",
        "猫耳手势",
        "挥手过头",
        "双手比心上举",
        "整理头发",
        "手搭后脑",
        "舞蹈上扬",
        "投降式玩笑",
        "胜利举臂",
        "单手遮光",
        "侧身举臂",
        "抱头害羞",
        "向上指路",
        "拉伸肩颈",
        "双手绕头",
        "一手扶帽",
        "偶像应援",
        "高位挥拍",
        "魔法起手",
        "直播庆祝",
        "落手缓冲",
    ],
    "wide_action_or_limbs_out": [
        "战斗开架",
        "跳跃展开",
        "侧跳伸臂",
        "单腿外踢",
        "双臂打开",
        "大步跨出",
        "飞身侧摆",
        "开场亮相",
        "转身甩手",
        "快速闪避",
        "踢腿收势",
        "冲刺准备",
        "伸手邀请",
        "护住胸前",
        "双手推开",
        "惊讶后撤",
        "欢呼外展",
        "舞蹈展开",
        "武器想象架势",
        "魔法释放",
        "前扑接住",
        "侧摆平衡",
        "大幅招手",
        "旋转定格",
        "收回待机",
    ],
    "crouch_low_pose": [
        "半蹲观察",
        "低身准备",
        "单膝跪地",
        "双膝跪坐",
        "抱膝蹲下",
        "蹲姿回望",
        "蹲姿挥手",
        "蹲姿捡物",
        "蹲姿护头",
        "蹲姿歪身",
        "跪坐托腮",
        "跪姿伸手",
        "跪姿祈愿",
        "低位转身",
        "低位起身",
        "盘腿坐姿",
        "侧坐回头",
        "蜷缩休息",
        "战斗低伏",
        "落地缓冲",
        "趴低前探",
        "单腿跪撑",
        "低位比心",
        "蹲姿猫步",
        "起身回正",
    ],
    "walking_step": [
        "左脚前迈",
        "右脚前迈",
        "小步靠近",
        "小步后退",
        "轻快踏步",
        "原地走路循环 A",
        "原地走路循环 B",
        "跑步预备",
        "跑步摆臂",
        "急停站稳",
        "踮脚靠近",
        "转身迈步",
        "侧步左移",
        "侧步右移",
        "交叉步",
        "舞步一拍",
        "舞步二拍",
        "轻跳落步",
        "走近打招呼",
        "退后害羞",
        "向前探步",
        "向后收步",
        "绕场展示",
        "跟随镜头",
        "回到中心",
    ],
    "extra_diversity": [
        "轻挥手",
        "敬礼",
        "比心",
        "鼓掌",
        "点头答应",
        "摇头拒绝",
        "眨眼卖萌",
        "托腮思考",
        "捂嘴笑",
        "双手合十",
        "加油握拳",
        "生气叉腰",
        "害羞遮脸",
        "惊讶捂脸",
        "伸手摸头",
        "拿麦克风",
        "举杯庆祝",
        "查看手机",
        "递出礼物",
        "抱住自己",
        "安慰拍胸",
        "打哈欠",
        "困倦低头",
        "直播谢幕",
        "回到待机",
    ],
}


def clamp_param(name: str, value: float) -> float:
    lo, hi = PARAM_RANGES[name]
    return round(max(lo, min(hi, value)), 3)


def params(**values: float) -> dict[str, float]:
    out: dict[str, float] = {
        "ParamMuscleDefinition": 0.58,
        "ParamConstructionLines": 0.74,
    }
    out.update(values)
    return {key: clamp_param(key, value) for key, value in out.items()}


def intensity(index: int) -> float:
    return 0.28 + (index % 5) * 0.14


def side(index: int) -> int:
    return -1 if index % 2 else 1


def build_parameters(category: str, index: int) -> dict[str, float]:
    s = side(index)
    t = intensity(index)
    phase = index % 5
    if category == "upright_front_or_back":
        return params(
            ParamAngleX=s * (2 + phase),
            ParamAngleY=(-3 + phase * 1.4),
            ParamAngleZ=s * (1.5 + t * 3.0),
            ParamBodyAngleZ=-s * (1.2 + t * 2.2),
            ParamHipShiftX=s * (0.08 + t * 0.13),
            ParamHipTiltZ=-s * (0.08 + t * 0.12),
            ParamShoulderTiltZ=s * (0.06 + t * 0.10),
            ParamSpineCurve=s * (0.04 + t * 0.08),
            ParamKneeLBend=0.04 + (phase % 2) * 0.06,
            ParamKneeRBend=0.05 + ((phase + 1) % 2) * 0.05,
        )
    if category == "side_profile":
        return params(
            ParamAngleX=s * (13 + t * 12),
            ParamAngleY=-2 + phase,
            ParamAngleZ=-s * (1 + t * 4),
            ParamBodyAngleX=s * (9 + t * 8),
            ParamBodyAngleY=-1.5 + phase * 0.6,
            ParamBodyAngleZ=-s * (2 + t * 4),
            ParamHipShiftX=s * (0.12 + t * 0.18),
            ParamHipTiltZ=-s * (0.12 + t * 0.16),
            ParamArmLRaise=0.08 + (phase in (1, 3)) * 0.18,
            ParamArmRRaise=0.08 + (phase in (2, 4)) * 0.18,
            ParamLegLStep=s * (0.05 + t * 0.22),
            ParamLegRStep=-s * (0.04 + t * 0.18),
            ParamKneeLBend=0.05 + t * 0.12,
            ParamKneeRBend=0.04 + t * 0.10,
        )
    if category == "contrapposto_lean":
        return params(
            ParamAngleX=s * (2 + t * 5),
            ParamAngleY=-1 + phase * 0.5,
            ParamAngleZ=s * (2 + t * 8),
            ParamBodyAngleX=s * (1 + t * 5),
            ParamBodyAngleY=-1 + t * 3,
            ParamBodyAngleZ=-s * (4 + t * 9),
            ParamHipShiftX=s * (0.22 + t * 0.42),
            ParamHipTiltZ=-s * (0.20 + t * 0.42),
            ParamShoulderTiltZ=s * (0.18 + t * 0.38),
            ParamSpineCurve=s * (0.18 + t * 0.48),
            ParamArmLRaise=0.08 + (phase in (2, 4)) * 0.24,
            ParamArmRRaise=0.08 + (phase in (1, 3)) * 0.24,
            ParamElbowLBend=0.08 + (phase in (0, 2, 4)) * 0.24,
            ParamElbowRBend=0.08 + (phase in (1, 3)) * 0.24,
            ParamLegLStep=s * (0.08 + t * 0.20),
            ParamLegRStep=-s * (0.02 + t * 0.18),
            ParamKneeLBend=0.08 + t * 0.22,
            ParamKneeRBend=0.04 + t * 0.18,
        )
    if category == "arms_raised_or_overhead":
        return params(
            ParamAngleX=s * (1 + t * 4),
            ParamAngleY=2 + t * 4,
            ParamAngleZ=s * (2 + t * 5),
            ParamBodyAngleY=1 + t * 3,
            ParamBodyAngleZ=-s * (1.5 + t * 5),
            ParamHipShiftX=s * (0.05 + t * 0.12),
            ParamHipTiltZ=-s * (0.06 + t * 0.14),
            ParamShoulderTiltZ=s * (0.10 + t * 0.18),
            ParamSpineCurve=0.10 + t * 0.24,
            ParamArmLRaise=0.58 + t * 0.42,
            ParamArmRRaise=0.54 + (1.0 - t * 0.20),
            ParamElbowLBend=0.18 + ((phase + 1) % 5) * 0.12,
            ParamElbowRBend=0.18 + phase * 0.12,
            ParamLegLStep=s * (0.03 + t * 0.10),
            ParamLegRStep=-s * (0.03 + t * 0.10),
            ParamKneeLBend=0.04 + t * 0.08,
            ParamKneeRBend=0.04 + t * 0.08,
        )
    if category == "wide_action_or_limbs_out":
        return params(
            ParamAngleX=s * (4 + t * 8),
            ParamAngleY=-2 + phase * 1.2,
            ParamAngleZ=s * (4 + t * 10),
            ParamBodyAngleX=s * (2 + t * 6),
            ParamBodyAngleY=-3 + t * 4,
            ParamBodyAngleZ=s * (4 + t * 9),
            ParamHipShiftX=s * (0.10 + t * 0.28),
            ParamHipTiltZ=-s * (0.10 + t * 0.26),
            ParamShoulderTiltZ=-s * (0.14 + t * 0.30),
            ParamSpineCurve=s * (0.12 + t * 0.28),
            ParamArmLRaise=0.25 + ((phase + 1) % 5) * 0.13,
            ParamArmRRaise=0.30 + phase * 0.12,
            ParamElbowLBend=0.10 + phase * 0.10,
            ParamElbowRBend=0.12 + ((phase + 2) % 5) * 0.10,
            ParamLegLStep=s * (0.30 + t * 0.44),
            ParamLegRStep=-s * (0.28 + t * 0.40),
            ParamKneeLBend=0.12 + t * 0.34,
            ParamKneeRBend=0.10 + t * 0.32,
        )
    if category == "crouch_low_pose":
        return params(
            ParamAngleX=s * (2 + t * 5),
            ParamAngleY=-4 - t * 5,
            ParamAngleZ=s * (2 + t * 6),
            ParamBodyAngleX=s * (1 + t * 4),
            ParamBodyAngleY=-5 - t * 8,
            ParamBodyAngleZ=s * (2 + t * 6),
            ParamHipShiftX=s * (0.08 + t * 0.22),
            ParamHipTiltZ=-s * (0.12 + t * 0.30),
            ParamShoulderTiltZ=s * (0.12 + t * 0.24),
            ParamSpineCurve=-0.18 - t * 0.42,
            ParamArmLRaise=0.12 + (phase in (1, 3, 4)) * 0.20,
            ParamArmRRaise=0.10 + (phase in (0, 2, 4)) * 0.20,
            ParamElbowLBend=0.20 + t * 0.35,
            ParamElbowRBend=0.18 + t * 0.34,
            ParamLegLStep=s * (0.18 + t * 0.20),
            ParamLegRStep=-s * (0.16 + t * 0.20),
            ParamKneeLBend=0.42 + t * 0.48,
            ParamKneeRBend=0.38 + t * 0.46,
        )
    if category == "walking_step":
        return params(
            ParamAngleX=s * (1 + t * 3),
            ParamAngleY=-1 + phase * 0.4,
            ParamAngleZ=-s * (1 + t * 4),
            ParamBodyAngleX=s * (1 + t * 3),
            ParamBodyAngleY=-1 + t * 2,
            ParamBodyAngleZ=s * (1.5 + t * 4),
            ParamHipShiftX=s * (0.10 + t * 0.18),
            ParamHipTiltZ=-s * (0.08 + t * 0.22),
            ParamShoulderTiltZ=s * (0.10 + t * 0.24),
            ParamSpineCurve=s * (0.06 + t * 0.18),
            ParamArmLRaise=0.08 + phase * 0.04,
            ParamArmRRaise=0.08 + (4 - phase) * 0.04,
            ParamElbowLBend=0.10 + phase * 0.08,
            ParamElbowRBend=0.12 + (4 - phase) * 0.07,
            ParamLegLStep=s * (0.25 + t * 0.38),
            ParamLegRStep=-s * (0.22 + t * 0.36),
            ParamKneeLBend=0.12 + t * 0.30,
            ParamKneeRBend=0.10 + t * 0.28,
        )
    return params(
        ParamAngleX=s * (2 + t * 6),
        ParamAngleY=-2 + phase,
        ParamAngleZ=s * (1 + t * 8),
        ParamBodyAngleX=s * (1 + t * 5),
        ParamBodyAngleY=-1 + t * 4,
        ParamBodyAngleZ=-s * (2 + t * 7),
        ParamHipShiftX=s * (0.08 + t * 0.22),
        ParamHipTiltZ=-s * (0.08 + t * 0.22),
        ParamShoulderTiltZ=s * (0.10 + t * 0.30),
        ParamSpineCurve=s * (0.06 + t * 0.28),
        ParamArmLRaise=0.10 + ((index + 1) % 5) * 0.12,
        ParamArmRRaise=0.08 + (index % 5) * 0.12,
        ParamElbowLBend=0.10 + ((index + 2) % 5) * 0.10,
        ParamElbowRBend=0.10 + ((index + 3) % 5) * 0.10,
        ParamLegLStep=s * (0.04 + t * 0.24),
        ParamLegRStep=-s * (0.04 + t * 0.22),
        ParamKneeLBend=0.06 + t * 0.18,
        ParamKneeRBend=0.05 + t * 0.18,
    )


def needs_alternate_art(category: str, index: int, label: str) -> bool:
    hard_words = ("跪", "坐", "趴", "飞身", "跳跃", "侧跳", "盘腿", "蜷缩", "低伏")
    if any(word in label for word in hard_words):
        return True
    if category == "crouch_low_pose":
        return index % 5 in (2, 3, 4)
    if category == "wide_action_or_limbs_out":
        return index % 5 == 1
    if category == "side_profile":
        return index in {6, 17, 24}
    return False


def difficulty_for(category: str, index: int, alternate_art: bool) -> str:
    if alternate_art:
        return "high"
    if category in {"wide_action_or_limbs_out", "arms_raised_or_overhead", "crouch_low_pose"}:
        return "medium" if index % 5 < 3 else "high"
    if category in {"side_profile", "contrapposto_lean", "walking_step"}:
        return "medium"
    return "low" if index % 5 < 3 else "medium"


def duration_for(category: str, index: int) -> float:
    if category == "walking_step":
        return round(0.9 + (index % 4) * 0.12, 2)
    if category in {"wide_action_or_limbs_out", "crouch_low_pose"}:
        return round(1.2 + (index % 5) * 0.18, 2)
    if category == "arms_raised_or_overhead":
        return round(1.1 + (index % 5) * 0.14, 2)
    return round(1.0 + (index % 5) * 0.10, 2)


def make_action(serial: int, category: dict[str, Any], index: int) -> dict[str, Any]:
    category_id = str(category["id"])
    category_label = str(category["label"])
    label = ACTION_NAMES[category_id][index]
    alternate_art = needs_alternate_art(category_id, index, label)
    loop = category_id in {"upright_front_or_back", "walking_step"} or label.endswith("循环 A") or label.endswith("循环 B")
    action_id = f"live2d_pose_{serial:03d}_{category_id}_{index + 1:02d}"
    rig_notes = (
        "需要额外替换手臂/腿部遮挡素材，作为 Live2D 替换姿态或短镜头使用。"
        if alternate_art
        else "可由基础切层、旋转枢轴和参数关键帧完成。"
    )
    tags = [category_label, "线稿提炼", "Live2D"]
    if loop:
        tags.append("可循环")
    if alternate_art:
        tags.append("替换素材")
    action = {
        "id": action_id,
        "label": label,
        "category": category_id,
        "category_label": category_label,
        "difficulty": difficulty_for(category_id, index, alternate_art),
        "duration": duration_for(category_id, index),
        "loop": loop,
        "requires_alternate_art": alternate_art,
        "source_basis": {
            "pdf_pose_family": category_id,
            "selected_reference_pool": f"assets/live2d_modeling/pose_study/selected_pages/*_{category_id}.png",
            "zip_reference_notes": "动漫线稿 zip 用于补充直播互动手势、表情姿态和人物轮廓节奏。",
        },
        "description": f"{category_label}动作：{label}。按线稿的肩、胸、胯和四肢节奏抽象成 Live2D 参数预设。",
        "rig_notes": rig_notes,
        "tags": tags,
        "parameters": build_parameters(category_id, index),
    }
    if alternate_art:
        action["requires"] = ["overlap_paint", "alternate_limb_art", "occlusion_covers"]
    return action


def build_catalog() -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    serial = 1
    for category in CATEGORIES:
        names = ACTION_NAMES[str(category["id"])]
        if len(names) != 25:
            raise ValueError(f"{category['id']} must contain exactly 25 action names")
        for index in range(25):
            actions.append(make_action(serial, category, index))
            serial += 1
    return {
        "format": ACTION_PRESET_FORMAT,
        "version": 1,
        "generated_from": {
            "zip_entries": 13399,
            "zip_images": 13371,
            "pdf_pose_records": 472,
            "balanced_selected_references": 96,
            "method": "pose-family abstraction from line-art PDFs plus interaction expansion from anime line-art zip samples",
        },
        "parameter_ranges": {key: list(value) for key, value in PARAM_RANGES.items()},
        "categories": CATEGORIES,
        "actions": actions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT_FILE)
    args = parser.parse_args()
    catalog = build_catalog()
    if len(catalog["actions"]) != 200:
        raise ValueError("expected 200 action presets")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(catalog['actions'])} action presets to {args.out}")


if __name__ == "__main__":
    main()
