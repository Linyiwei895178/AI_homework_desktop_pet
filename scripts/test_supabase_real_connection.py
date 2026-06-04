#!/usr/bin/env python3
"""
测试 Supabase 真实连通性。

用法：
    python scripts/test_supabase_real_connection.py

要求：
    - 项目根目录 .env 文件包含 SUPABASE_URL 和 SUPABASE_ANON_KEY
    - 可选安装 httpx（如未安装将使用 mock 模式）
    - Supabase 项目需创建以下表：pet_rooms, cloud_pets, pet_events
      （无表时会返回 HTTP 错误，此时会打印错误详情）

安全：
    - 全程不打印完整 SUPABASE_ANON_KEY（仅显示前 6 位）
    - 不上传聊天记录 / AI memory / 用户隐私数据
"""

from __future__ import annotations

import os
import sys

# ── 确保项目根目录在 sys.path 中 ──
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(_project_root, ".env"))


def print_sep(title: str = "") -> None:
    """Print a section separator."""
    print()
    print("=" * 58)
    if title:
        print(f"  {title}")
        print("=" * 58)


def main():
    print_sep("SUPABASE 真实连通性测试")
    print(f"  项目根目录: {_project_root}")
    print()

    # ── 1. 检查配置 ──
    print("  [1/8] 读取 SUPABASE_URL / SUPABASE_ANON_KEY ...")
    url = (os.getenv("SUPABASE_URL") or "").strip()
    anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()

    if url:
        print(f"    [OK] SUPABASE_URL    = {url[:12]}...")
    else:
        print("    [FAIL] SUPABASE_URL 未设置")

    if anon_key:
        print(f"    [OK] SUPABASE_ANON_KEY = {anon_key[:6]}... (仅显示前6位)")
    else:
        print("    [FAIL] SUPABASE_ANON_KEY 未设置")

    if not url or not anon_key:
        print()
        print("  [WARN]  Supabase 未配置，跳过后续测试。")
        print("  如需测试，请在 .env 中添加：")
        print("    SUPABASE_URL=https://your-project.supabase.co")
        print("    SUPABASE_ANON_KEY=your-anon-key")
        sys.exit(1)

    # ── 2. 检查 httpx ──
    print()
    print("  [2/8] 检查 httpx 包是否可用 ...")
    try:
        import httpx  # noqa: F401
        print("    [OK] httpx 已安装")
    except ImportError:
        print("    [WARN]  httpx 未安装 → 将使用 mock 模式")
        print("    [INFO] 运行: pip install httpx")
        httpx_available = False
    else:
        httpx_available = True

    # ── 3. 初始化 SupabaseCloudService ──
    print()
    print("  [3/8] 初始化 SupabaseCloudService ...")
    try:
        from models.cloud.cloud_service import SupabaseCloudService
        svc = SupabaseCloudService(url=url, anon_key=anon_key)
        if svc.is_configured():
            print("    [OK] SupabaseCloudService 已配置")
        else:
            print("    [FAIL] SupabaseCloudService 未配置")
            sys.exit(1)
    except Exception as exc:
        print(f"    [FAIL] 初始化失败: {exc}")
        sys.exit(1)

    # ── 4. create_or_join_room ──
    print()
    print("  [4/8] create_or_join_room('TEAMROOM001', pet_name='Echo') ...")
    try:
        result = svc.create_or_join_room("TEAMROOM001", pet_name="Echo")
        if result["ok"]:
            print(f"    [OK] ok: True")
            room = result["data"].get("room", {})
            pet = result["data"].get("pet", {})
            print(f"       room_code   = {room.get('room_code')}")
            print(f"       pet_name    = {pet.get('pet_name')}")
            note = result["data"].get("note", "")
            if note:
                print(f"       [WARN]  注意: {note}")
        else:
            print(f"    [FAIL] ok: False  error: {result['error']}")
    except Exception as exc:
        print(f"    [FAIL] 异常: {exc}")

    # ── 5. fetch_cloud_pet_state ──
    print()
    print("  [5/8] fetch_cloud_pet_state('TEAMROOM001') ...")
    try:
        result = svc.fetch_cloud_pet_state("TEAMROOM001")
        if result["ok"]:
            print(f"    [OK] ok: True")
            pet = result["data"].get("pet", {})
            if pet:
                print(f"       pet_name    = {pet.get('pet_name')}")
                print(f"       pet_id      = {pet.get('pet_id')}")
                print(f"       mood        = {pet.get('mood')}")
                print(f"       energy      = {pet.get('energy')}")
                print(f"       level       = {pet.get('level')}")
            else:
                print(f"       (无数据)")
        else:
            print(f"    [FAIL] ok: False  error: {result['error']}")
    except Exception as exc:
        print(f"    [FAIL] 异常: {exc}")

    # ── 6. save_cloud_pet_state ──
    print()
    print("  [6/8] save_cloud_pet_state('TEAMROOM001', {...}) ...")
    try:
        state = {
            "pet_name": "Echo",
            "pet_id": "cat",
            "mood": "happy",
            "energy": 88,
            "intimacy": 66,
            "level": 2,
            "exp": 30,
            "coins": 15,
            "hunger": 40,
            "bond_score": 5,
        }
        result = svc.save_cloud_pet_state("TEAMROOM001", state)
        if result["ok"]:
            print(f"    [OK] ok: True")
            if result["data"].get("updated"):
                print(f"       updated = True")
        else:
            print(f"    [FAIL] ok: False  error: {result['error']}")
    except Exception as exc:
        print(f"    [FAIL] 异常: {exc}")

    # ── 7. append_pet_event ──
    print()
    print("  [7/8] append_pet_event('TEAMROOM001', {...}) ...")
    try:
        event_data = {
            "event_type": "interaction",
            "action_type": "test_feed",
            "actor_name": "队长测试",
            "message": "测试投喂",
            "delta": {"exp": 5, "coins": 1},
        }
        result = svc.append_pet_event("TEAMROOM001", event_data)
        if result["ok"]:
            print(f"    [OK] ok: True")
            if result["data"].get("inserted"):
                print(f"       inserted = True")
        else:
            print(f"    [FAIL] ok: False  error: {result['error']}")
    except Exception as exc:
        print(f"    [FAIL] 异常: {exc}")

    # ── 8. fetch_recent_pet_events ──
    print()
    print("  [8/8] fetch_recent_pet_events('TEAMROOM001', limit=5) ...")
    try:
        result = svc.fetch_recent_pet_events("TEAMROOM001", limit=5)
        if result["ok"]:
            events = result["data"].get("events", [])
            print(f"    [OK] ok: True  事件数: {len(events)}")
            for i, ev in enumerate(events, 1):
                print(f"       [{i}] {ev.get('event_type')} / {ev.get('action_type')} "
                      f"by {ev.get('actor_name')} @ {ev.get('created_at', '?')}")
        else:
            print(f"    [FAIL] ok: False  error: {result['error']}")
    except Exception as exc:
        print(f"    [FAIL] 异常: {exc}")

    # ── 最终总结 ──
    print()
    print_sep("测试完成")
    if httpx_available:
        print("  [OK] httpx 已安装 → REST API 调用已执行")
        print("  [INFO] 如果所有步骤返回 ok=True，则 Supabase 真实连通性正常。")
        print("  [INFO] 如果某些步骤返回 ok=False + error，请检查：")
        print("     1. Supabase 项目是否已创建 pet_rooms, cloud_pets, pet_events 表")
        print("     2. RLS 策略是否允许 anon key 执行 UPSERT / SELECT / INSERT")
        print("     3. 网络是否能连接到 Supabase URL")
    else:
        print("  [WARN]  httpx 未安装，当前仍为 mock 模式，尚未真实写入 Supabase。")
        print("  [INFO] 安装 httpx 后重新运行: pip install httpx")

    print()


if __name__ == "__main__":
    main()
