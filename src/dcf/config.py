"""Load config.yaml (defaults, bounds, thresholds). No finance logic here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config.yaml"


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict[str, Any]:
    """Read the YAML config (cached). Pass a path to load a different file."""
    cfg: dict[str, Any] = yaml.safe_load(Path(path or CONFIG_PATH).read_text())
    return cfg


def bounds() -> dict[str, list[float]]:
    return dict(load_config()["bounds"])
