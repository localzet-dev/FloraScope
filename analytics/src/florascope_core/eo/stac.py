from __future__ import annotations

import httpx
import json
import numpy as np
from datetime import date, datetime
from urllib.parse import urljoin, urlencode

from .models import AssetRef, SceneRef


class StacClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")

    def search(
        self,
        *,
        collection: str,
        source: str,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        max_cloud_cover: float,
        limit: int = 80,
    ) -> list[SceneRef]:
        body = {
            "collections": [collection],
            "bbox": list(bbox),
            "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
            "limit": min(limit, 20),
        }
        items = []
        # GET не требует тела запроса; следующие страницы читаем методом
        # из STAC link. Cloud cover остаётся prefilter перед pixel quality mask.
        params = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, dict)
        else ",".join(map(str, value)) if isinstance(value, list) else value
                  for key, value in body.items()}
        url = f"{self.endpoint}/search?{urlencode(params)}"
        method = "GET"
        request_body = body
        seen = set()
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            for _ in range(50):
                marker = (url, method, repr(request_body))
                if marker in seen:
                    raise ValueError("STAC повторяет страницу результатов")
                seen.add(marker)
                response = client.post(url, json=request_body) if method == "POST" else client.get(url)
                response.raise_for_status()
                payload = response.json()
                items.extend(payload.get("features", []))
                next_link = next((link for link in payload.get("links", []) if link.get("rel") == "next"), None)
                if not next_link:
                    break
                url = urljoin(url, next_link["href"])
                method = next_link.get("method", "GET").upper()
                request_body = ({**body, **next_link.get("body", {})}
                                if next_link.get("merge") else next_link.get("body", {}))
            else:
                raise ValueError("STAC: больше 50 страниц, уменьшите период или AOI")

        scenes: list[SceneRef] = []
        for item in items:
            properties = item.get("properties") or {}
            cloud_cover = _float_or_none(properties.get("eo:cloud_cover"))
            if cloud_cover is not None and cloud_cover > max_cloud_cover:
                continue
            timestamp = properties.get("datetime") or properties.get("start_datetime")
            if not timestamp:
                continue
            acquired_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            assets: dict[str, AssetRef] = {}
            for key, raw in (item.get("assets") or {}).items():
                if not raw.get("href"):
                    continue
                raster_bands = raw.get("raster:bands") or []
                raster = raster_bands[0] if raster_bands else {}
                assets[str(key)] = AssetRef(
                    href=str(raw["href"]),
                    scale=_float_or_none(raster.get("scale")),
                    offset=_float_or_none(raster.get("offset")),
                )
            scenes.append(
                SceneRef(
                    id=str(item.get("id")),
                    source=source,
                    acquired_at=acquired_at,
                    cloud_cover=_float_or_none(properties.get("eo:cloud_cover")),
                    assets=assets,
                    collection=str(item.get("collection", collection)),
                )
            )
        return sorted(scenes, key=lambda scene: scene.acquired_at)


def choose_scenes(
    scenes: list[SceneRef],
    *,
    min_gap_days: int,
    limit: int,
) -> list[SceneRef]:
    """Не тащим пять почти одинаковых съёмок подряд - берём более чистую."""

    chosen: list[SceneRef] = []
    # Выбор по качеству с запретом близких дат не позволяет последовательным
    # заменам «более чистой» сценой сдвинуть одну корзину через весь сезон.
    for scene in sorted(scenes, key=lambda item: (_cloud(item), item.acquired_at)):
        if all(abs((scene.acquired_at.date() - item.acquired_at.date()).days) >= min_gap_days for item in chosen):
            chosen.append(scene)
    chosen.sort(key=lambda item: item.acquired_at)
    # Ограничение бюджета не должно оставлять только начало сезона.
    if len(chosen) > limit:
        indices = np.linspace(0, len(chosen) - 1, limit, dtype=int)
        chosen = [chosen[index] for index in indices]
    return chosen


def _cloud(scene: SceneRef) -> float:
    return float(scene.cloud_cover) if scene.cloud_cover is not None else 101.0


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
