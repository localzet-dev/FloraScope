import pandas as pd
from pathlib import Path

from florascope_core.anomaly import analyze_vegetation


def _frame() -> pd.DataFrame:
    rows = []
    seasons = {
        2021: [0.30, 0.50, 0.70, 0.60],
        2022: [0.31, 0.51, 0.69, 0.61],
        2023: [0.29, 0.49, 0.71, 0.59],
        2024: [0.30, 0.50, 0.35, 0.30],
    }
    for year, values in seasons.items():
        for doy, value in zip([150, 160, 170, 180], values):
            day = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=doy - 1)
            rows.append(
                {
                    "anon_polygon_id": "A",
                    "date": day,
                    "year": year,
                    "doy": doy,
                    "primary_ndvi_filled": value,
                    "era5_temp_c": 20.0,
                    "era5_precip_mm": 0.2,
                }
            )
    return pd.DataFrame(rows)


def test_negative_period_becomes_event(tmp_path: Path) -> None:
    points_path, events_path = analyze_vegetation(_frame(), tmp_path)
    points = pd.read_csv(points_path)
    events = pd.read_csv(events_path)

    assert not events.empty
    assert "interpretation" in events.columns
    assert "confidence" in events.columns
    assert (events["kind"] == "NEGATIVE_DEVIATION").any()

    bad_season = points.loc[points["year"] == 2024]
    assert bad_season["reference_years_calc"].min() == 3
    assert bad_season["climatology_calc"].max() > 0.65
    assert bad_season["ndvi_zscore_calc"].min() < -2.0


def test_reference_excludes_current_year(tmp_path: Path) -> None:
    frame = _frame()
    points_path, _ = analyze_vegetation(frame, tmp_path)
    points = pd.read_csv(points_path)

    row = points.loc[(points["year"] == 2024) & (points["doy"] == 170)].iloc[0]
    # Норма должна остаться около нормальных 2021-2023, а не подтянуться к 0.35.
    assert 0.68 <= row["climatology_calc"] <= 0.72


def test_normal_point_breaks_persistence():
    from florascope_core.anomaly import _negative_events
    frame = pd.DataFrame({
        'anon_polygon_id': ['A'] * 3, 'year': [2024] * 3,
        'date': pd.to_datetime(['2024-06-01', '2024-06-06', '2024-06-11']),
        'ndvi_zscore_calc': [-3, 0, -3], 'primary_ndvi_filled': [.2, .6, .2],
    })
    assert _negative_events(frame) == []


def test_missing_reference_is_unknown(tmp_path):
    frame = _frame().query('year == 2024')
    points, events = analyze_vegetation(frame, tmp_path)
    assert set(pd.read_csv(points).status_calc) == {'UNKNOWN'}
    assert pd.read_csv(events).empty


def test_phenology_uses_days_and_requires_improvement():
    import numpy as np
    from florascope_core.anomaly import phenology_shift
    days = np.array([80, 91, 102, 115, 132, 146, 160, 180, 201, 220, 240])
    t = np.arange(1, 367)
    expected = .2 + .6 * np.exp(-((t - 155) / 32) ** 2)
    delayed = .2 + .6 * np.exp(-((t - 170) / 32) ** 2)
    assert phenology_shift(expected, expected, days) is None
    assert phenology_shift(delayed, expected, days)[0] == 15
    linear = np.linspace(.1, .8, 366)
    assert phenology_shift(linear, linear + .1, days) is None


def test_live_interpolation_cannot_create_event_support():
    from florascope_core.eo.temporal import _negative_events
    series = [{'date': f'2024-06-{day:02}', 'zscore': -3, 'observed': .2 if day == 1 else None}
              for day in [1, 6, 11, 16]]
    assert _negative_events(series) == []


def test_live_weather_evidence_uses_full_calendar_window():
    from datetime import date, timedelta
    from florascope_core.eo.temporal import _attach_evidence
    from florascope_core.eo.models import Observation
    weather = {}
    for year, rain in [(2022, 3.), (2023, 4.), (2024, 0.)]:
        end = date(year, 6, 30)
        for offset in range(30):
            weather[str(end - timedelta(days=offset))] = {'precipitation_mm': rain, 'temperature_c': 20.}
    current = [Observation('sentinel-2', 'now', '2024-06-30', .9, {'ndvi': .3, 'ndmi': .1})]
    history = [Observation('sentinel-2', str(year), f'{year}-06-30', .9, {'ndvi': .6, 'ndmi': .4}) for year in
               (2022, 2023)]
    series = [{'date': '2024-06-30', 'temperature_c': 20.}]
    _attach_evidence(series, current, history, weather, 2024)
    assert series[0]['precip_30_z'] < -2
    assert series[0]['ndmi_z'] < -2
    del weather['2024-06-10']
    _attach_evidence(series, current, history, weather, 2024)
    assert series[0]['precip_30_z'] is None


def test_live_does_not_extrapolate_reference_outside_history():
    import json
    from florascope_core.eo.models import Observation
    from florascope_core.eo.temporal import analyze_temporal
    history = [Observation('sentinel-2', str((year, day)), f'{year}-07-{day:02}', .9, {'ndvi': .6})
               for year in (2022, 2023) for day in (10, 15, 20)]
    current = [Observation('sentinel-2', str(day), f'2024-07-{day:02}', .9, {'ndvi': .3})
               for day in (1, 10, 15, 20, 30)]
    result = analyze_temporal(current, history, {}, 2024)
    assert result['series'][0]['status'] == 'UNKNOWN'
    assert result['series'][0]['expected'] is None
    assert result['state']['latest_expected'] is None
    assert any(point['expected'] is not None for point in result['series'])
    json.dumps(result, allow_nan=False)
