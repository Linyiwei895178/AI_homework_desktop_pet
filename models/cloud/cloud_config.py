"""
Cloud configuration: reads SUPABASE_URL and SUPABASE_ANON_KEY from env.

Usage:
    from models.cloud.cloud_config import CloudConfig
    cfg = CloudConfig()
    if cfg.is_configured:
        print(f"Supabase URL: {cfg.supabase_url}")
"""

from __future__ import annotations

import os
from typing import Optional


class CloudConfig:
    """
    Supabase connection configuration.

    Reads from environment variables:
        SUPABASE_URL
        SUPABASE_ANON_KEY

    May also check .env via the project's utils.config.
    """

    def __init__(self):
        # Try env first
        self.supabase_url: str = (os.getenv("SUPABASE_URL") or "").strip()
        self.supabase_anon_key: str = (os.getenv("SUPABASE_ANON_KEY") or "").strip()

        # Fallback to project config singleton
        if not self.supabase_url or not self.supabase_anon_key:
            try:
                from utils.config import config
                url = config.get("SUPABASE_URL", "")
                key = config.get("SUPABASE_ANON_KEY", "")
                if url:
                    self.supabase_url = str(url).strip()
                if key:
                    self.supabase_anon_key = str(key).strip()
            except ImportError:
                pass

    @property
    def is_configured(self) -> bool:
        """True if both URL and anon key are non-empty."""
        return bool(self.supabase_url and self.supabase_anon_key)

    def get_headers(self) -> dict:
        """Return standard Supabase REST headers."""
        return {
            "apikey": self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    def get_table_url(self, table: str) -> str:
        """Get the REST URL for a given table."""
        base = self.supabase_url.rstrip("/")
        return f"{base}/rest/v1/{table}"
