#!/usr/bin/env python3
"""
Supabase 连通性检查脚本

功能：
    1. 读取 SUPABASE_URL 和 SUPABASE_ANON_KEY（从 .env 或系统环境变量）
    2. 如果缺失，提示用户创建 .env
    3. 如果存在，初始化 SupabaseCloudService
    4. 输出 is_configured 状态
    5. 不打印完整 key

用法：
    python scripts/check_supabase_config.py
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv


def main():
    print("=" * 50)
    print("  Supabase 配置检查")
    print("=" * 50)

    # Load .env from project root
    env_path = os.path.join(_project_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"  ✅ 已加载 .env 文件")
    else:
        print("  ⚠️  未找到 .env 文件")

    url = (os.getenv("SUPABASE_URL") or "").strip()
    anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()

    if not url:
        print("  ❌ SUPABASE_URL 未设置")
    else:
        print(f"  ✅ SUPABASE_URL = {url[:12]}...")

    if not anon_key:
        print("  ❌ SUPABASE_ANON_KEY 未设置")
    else:
        print(f"  ✅ SUPABASE_ANON_KEY = {anon_key[:6]}...")

    if not url or not anon_key:
        print()
        print("  ── 配置指南 ──")
        print("  1. 在项目根目录创建 .env 文件（参考 .env.example）")
        print("  2. 添加以下内容：")
        print("     SUPABASE_URL=https://your-project.supabase.co")
        print("     SUPABASE_ANON_KEY=your-anon-key")
        print("  3. 重新运行此脚本")
        sys.exit(1)

    # Try to initialize cloud service
    print()
    print("  ── 初始化 SupabaseCloudService ──")

    try:
        from models.cloud.cloud_service import SupabaseCloudService

        svc = SupabaseCloudService(url=url, anon_key=anon_key)

        if svc.is_configured():
            print("  ✅ SupabaseCloudService 已配置")
        else:
            print("  ❌ SupabaseCloudService 未配置")

        # Check supabase package
        try:
            import supabase  # noqa: F401
            print("  ✅ supabase Python 包已安装")
        except ImportError:
            print("  ⚠️  supabase Python 包未安装")
            print("     执行: pip install supabase")

    except Exception as exc:
        print(f"  ❌ 初始化失败: {exc}")
        sys.exit(1)

    print()
    print("  ── 检查完成 ──")


if __name__ == "__main__":
    main()
