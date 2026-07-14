from __future__ import annotations

import math
from pathlib import Path

import yaml

# Repo root = parent of the src/ directory this file lives in.
ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path = "config.yaml") -> dict:
    """Load config.yaml from the repo root and return it as a dict."""
    cfg_path = ROOT / path if not Path(path).is_absolute() else Path(path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(path: str | Path) -> Path:
    """Resolve a config-relative path against the repo root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def log(msg: str) -> None:
    """Uniform, greppable stdout logging."""
    print(f"[clearpath] {msg}", flush=True)
