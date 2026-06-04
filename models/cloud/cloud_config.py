"""
Cloud configuration: reads SUPABASE_URL and SUPABASE_ANON_KEY from env.

Usage:
    from models.cloud.cloud_config import load_cloud_config
    cfg = load_cloud_config()
    if cfg["configured"]:
        print(f"Supabase URL: {cfg['url'][:8]}...")
"""

from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv


def load_cloud_config() -> Dict[str, Any]:
    """
    Load Supabase configuration from environment variables.

    Reads SUPABASE_URL and SUPABASE_ANON_KEY from:
      1. os.environ (set by .env or system env)
      2. .env file via python-dotenv (fallback)

    Returns:
        {
            "url": str,
            "anon_key": str,
            "configured": bool
        }
    """
    # Ensure .env is loaded (idempotent)
    load_dotenv()

    url = (os.getenv("SUPABASE_URL") or "").strip()
    anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()

    configured = bool(url and anon_key)

    # Debug hint: only show first 6 chars of key
    if configured:
        _safe = f"{url[:12]}... / anon_key={anon_key[:6]}..."
    else:
        _safe = "missing SUPABASE_URL or SUPABASE_ANON_KEY in environment"
    return {
        "url": url,
        "anon_key": anon_key,
        "configured": configured,
        "_debug_hint": _safe,
    }
