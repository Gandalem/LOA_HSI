from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOSTARK_API_KEY = os.getenv("LOSTARK_API_KEY", "").strip()
LOSTARK_API_BASE = os.getenv("LOSTARK_API_BASE", "https://developer-lostark.game.onstove.com").rstrip("/")
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
if not DATA_DIR.exists():
    DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PARQUET_DIR = DATA_DIR / "parquet"

for directory in (RAW_DIR, PROCESSED_DIR, PARQUET_DIR):
    directory.mkdir(parents=True, exist_ok=True)
