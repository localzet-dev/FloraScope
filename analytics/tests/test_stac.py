import httpx
from datetime import date

from florascope_core.eo.stac import StacClient


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "features": [
                {
                    "id": "scene-1",
                    "properties": {"datetime": "2026-06-01T10:00:00Z", "eo:cloud_cover": 4.0},
                    "assets": {
                        "red": {"href": "https://example/red.tif", "raster:bands": [{"scale": 0.1, "offset": 1.0}]}},
                }
            ]
        }


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, url: str):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        assert parsed.path == "/search"
        assert parse_qs(parsed.query)["collections"] == ["sentinel-2-c1-l2a"]
        return FakeResponse()


def test_stac_search_normalizes_scene(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", FakeClient)
    scenes = StacClient("https://stac.example").search(
        collection="sentinel-2-c1-l2a",
        source="sentinel-2",
        bbox=(39.0, 45.0, 39.1, 45.1),
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        max_cloud_cover=20,
    )
    assert len(scenes) == 1
    assert scenes[0].assets["red"].scale == 0.1
    assert scenes[0].cloud_cover == 4.0


def test_search_follows_next_page(monkeypatch):
    class Response(FakeResponse):
        def __init__(self, page):
            self.page = page

        def json(self):
            data = super().json()
            data['features'][0]['id'] = f'scene-{self.page}'
            if self.page == 1:
                data['links'] = [{'rel': 'next', 'href': '/search?page=2'}]
            return data

    class Client(FakeClient):
        def post(self, url, json):
            return Response(1)

        def get(self, url):
            return Response(2 if url.endswith('page=2') else 1)

    monkeypatch.setattr(httpx, 'Client', Client)
    scenes = StacClient('https://stac.example').search(
        collection='s2', source='s2', bbox=(0, 0, 1, 1),
        date_from=date(2024, 1, 1), date_to=date(2024, 12, 31), max_cloud_cover=35)
    assert [scene.id for scene in scenes] == ['scene-1', 'scene-2']


def test_scene_budget_covers_end_of_season():
    from datetime import datetime, timedelta
    from florascope_core.eo.models import SceneRef
    from florascope_core.eo.stac import choose_scenes
    scenes = [SceneRef(str(i), 's2', datetime(2024, 1, 1) + timedelta(days=10 * i), 1, {}) for i in range(30)]
    selected = choose_scenes(scenes, min_gap_days=7, limit=5)
    assert len(selected) == 5
    assert selected[0] == scenes[0] and selected[-1] == scenes[-1]


def test_improving_cloud_cover_does_not_collapse_season():
    from datetime import datetime, timedelta
    from florascope_core.eo.models import SceneRef
    from florascope_core.eo.stac import choose_scenes
    scenes = [SceneRef(str(i), 's2', datetime(2024, 1, 1) + timedelta(days=5 * i), 30 - i, {}) for i in range(12)]
    selected = choose_scenes(scenes, min_gap_days=7, limit=18)
    assert len(selected) >= 5
    assert (selected[-1].acquired_at - selected[0].acquired_at).days >= 40


def test_sentinel_falls_back_to_legacy_archive(monkeypatch):
    from datetime import datetime
    from florascope_core.eo.models import SceneRef, AssetRef
    from florascope_core.eo.sentinel2 import Sentinel2Provider, ASSET_NAMES, COLLECTION, ARCHIVE_COLLECTION
    provider = Sentinel2Provider('unused')
    calls = []
    scene = SceneRef('legacy', 'sentinel-2', datetime(2022, 7, 1), 1,
                     {name: AssetRef(name, .0001, 0.) for name in ASSET_NAMES}, ARCHIVE_COLLECTION)

    def search(**kwargs):
        calls.append(kwargs['collection'])
        return [] if kwargs['collection'] == COLLECTION else [scene]

    monkeypatch.setattr(provider.client, 'search', search)
    result = provider.search(bbox=(0, 0, 1, 1), date_from=date(2022, 6, 1),
                             date_to=date(2022, 7, 31), max_cloud_cover=35)
    assert calls == [COLLECTION, ARCHIVE_COLLECTION]
    assert result == [scene]
    assert provider.search_notes
