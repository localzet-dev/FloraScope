from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AssetRef:
    href: str
    scale: float | None = None
    offset: float | None = None


@dataclass(frozen=True, slots=True)
class SceneRef:
    id: str
    source: str
    acquired_at: datetime
    cloud_cover: float | None
    assets: dict[str, AssetRef]
    collection: str | None = None


@dataclass(slots=True)
class Observation:
    source: str
    scene_id: str
    date: str
    valid_fraction: float
    indices: dict[str, float]
    rasters: dict[str, np.ndarray] | None = None
