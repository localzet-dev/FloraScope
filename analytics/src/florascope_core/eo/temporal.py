from __future__ import annotations

import numpy as np
import warnings
from datetime import date, timedelta

from .models import Observation
from ..anomaly import phenology_shift
from ..smoothing import linear_curve, whittaker_curve


def merge_same_day(observations: list[Observation]) -> list[Observation]:
    """На совпавшей дате Sentinel имеет приоритет, затем Landsat."""

    priority = {"sentinel-2": 0, "landsat": 1}
    by_date: dict[str, list[Observation]] = {}
    for observation in observations:
        by_date.setdefault(observation.date, []).append(observation)
    return [
        sorted(items, key=lambda item: priority.get(item.source, 99))[0]
        for _, items in sorted(by_date.items())
    ]


def analyze_temporal(
    current: list[Observation],
    history: list[Observation],
    weather: dict[str, dict],
    current_year: int,
) -> dict:
    history_curves = []
    for year in sorted({date.fromisoformat(item.date).year for item in history}):
        if year == current_year:
            continue
        rows = [item for item in history if date.fromisoformat(item.date).year == year]
        if len(rows) < 3:
            continue
        days = np.asarray(
            [date.fromisoformat(item.date).timetuple().tm_yday for item in rows],
            dtype=int,
        )
        values = np.asarray([item.indices["ndvi"] for item in rows], dtype=float)
        curve = linear_curve(days, values)
        # Наблюдения в июле не доказывают норму для апреля: без экстраполяции.
        curve[:int(days.min()) - 1] = np.nan
        curve[int(days.max()):] = np.nan
        history_curves.append(curve)
    if len(history_curves) < 2:
        raise ValueError("Для baseline нужны минимум два исторических сезона с тремя наблюдениями")

    history_stack = np.stack(history_curves)
    reference_count = np.isfinite(history_stack).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = np.nanmedian(history_stack, axis=0)
        spread = np.maximum(np.nanstd(history_stack, axis=0), 0.035)
    expected[reference_count < 2] = np.nan
    spread[reference_count < 2] = np.nan
    current_days = np.asarray(
        [date.fromisoformat(item.date).timetuple().tm_yday for item in current],
        dtype=int,
    )
    current_values = np.asarray([item.indices["ndvi"] for item in current], dtype=float)
    restored = whittaker_curve(current_days, current_values)
    observed = {item.date: item for item in current}

    timeline_days = sorted(
        set(range(int(current_days.min()), int(current_days.max()) + 1, 5))
        | set(current_days.tolist())
    )
    series: list[dict] = []
    for doy in timeline_days:
        day = date(current_year, 1, 1) + timedelta(days=doy - 1)
        zscore = _finite((restored[doy - 1] - expected[doy - 1]) / spread[doy - 1])
        point = observed.get(day.isoformat())
        series.append(
            {
                "date": day.isoformat(),
                "source": point.source if point else None,
                "observed": point.indices["ndvi"] if point else None,
                "restored": float(restored[doy - 1]),
                "expected": _finite(expected[doy - 1]),
                "reference_years": int(reference_count[doy - 1]),
                "lower": _finite(expected[doy - 1] - 1.96 * spread[doy - 1]),
                "upper": _finite(expected[doy - 1] + 1.96 * spread[doy - 1]),
                "zscore": zscore,
                "status": _status(zscore),
                **weather.get(day.isoformat(), {}),
            }
        )

    _attach_evidence(series, current, history, weather, current_year)
    events = _negative_events(series)
    phenology = _phenology_shift(restored, expected, current_days, current_year)
    if phenology is not None:
        events.append(phenology)

    scores = [point["zscore"] for point in series if point["zscore"] is not None]
    minimum = min(scores) if scores else None
    return {
        "series": series,
        "events": events,
        "state": {
            "condition": _status(minimum),
            "min_zscore": minimum,
            "latest_ndvi": float(current_values[-1]),
            "latest_expected": _finite(expected[current_days[-1] - 1]),
        },
    }


def same_day(value: date, year: int) -> date:
    day = value.day
    while day > 28:
        try:
            return date(year, value.month, day)
        except ValueError:
            day -= 1
    return date(year, value.month, day)


def _negative_events(series: list[dict]) -> list[dict]:
    result: list[dict] = []
    block: list[dict] = []
    for point in series:
        if point["zscore"] is not None and point["zscore"] < -1.0:
            block.append(point)
            continue
        if _supported(block):
            result.append(_live_event(block, series[-1]["date"]))
        block = []
    if _supported(block):
        result.append(_live_event(block, series[-1]["date"]))
    return result


def _supported(points: list[dict]) -> bool:
    return (len(points) >= 2
            and (date.fromisoformat(points[-1]["date"]) - date.fromisoformat(points[0]["date"])).days >= 5
            and sum(point["observed"] is not None for point in points) >= 2)


def _live_event(points: list[dict], series_end: str) -> dict:
    min_z = float(min(point["zscore"] for point in points))

    def median(key):
        values = [point[key] for point in points if point.get(key) is not None]
        return float(np.median(values)) if values else None

    precip, temperature, water = median("precip_30_z"), median("temperature_z"), median("ndmi_z")
    observed_count = sum(point["observed"] is not None for point in points)
    reference_years = min(point.get("reference_years", 0) for point in points)
    quality = median("valid_fraction")
    detail = "устойчивое отрицательное отклонение от исторического сценария"
    if water is not None and water < -1 and precip is not None and precip < -1:
        detail += "; снижение NDMI и осадков относительно нормы совместимо с дефицитом влаги"
    elif temperature is not None and temperature > 1 and precip is not None and precip < -1:
        detail += "; жаркий и сухой относительно нормы период — возможный фактор, не диагноз"
    elif water is not None and water < -1:
        detail += "; NDMI также ниже своей исторической нормы"
    evidence = {"ndvi_min_z": min_z, "observed_points": observed_count,
                "trajectory_points": len(points), "reference_years": reference_years}
    for key, value in (("ndmi_z", water), ("precip_30_z", precip), ("temperature_z", temperature),
                       ("valid_fraction", quality)):
        if value is not None:
            evidence[key] = value
    corroborated = ((water is not None and water < -1) or (precip is not None and precip < -1))
    confidence = "LOW"
    if observed_count >= 3 and reference_years >= 2:
        confidence = "MEDIUM"
    if observed_count >= 3 and reference_years >= 3 and corroborated and quality is not None and quality >= .5:
        confidence = "HIGH"
    return {
        "kind": "NEGATIVE_DEVIATION",
        "start": points[0]["date"],
        "end": points[-1]["date"],
        "severity": "CRITICAL" if min_z < -2 else "STRESSED",
        "min_zscore": min_z,
        "active": points[-1]["date"] == series_end,
        "confidence": confidence,
        "evidence": evidence,
        "interpretation": detail,
    }


def _phenology_shift(
    restored: np.ndarray,
    expected: np.ndarray,
    current_days: np.ndarray,
    current_year: int,
) -> dict | None:
    """Ищет сдвиг формы сезона, не меняя им основной anomaly score."""

    shift = phenology_shift(restored, expected, current_days)
    if shift is None:
        return None
    best_lag, best_corr, zero_corr = shift
    direction = "позже" if best_lag > 0 else "раньше"
    return {
        "kind": "PHENOLOGY_SHIFT",
        "start": f"{current_year}-01-01",
        "end": f"{current_year}-12-31",
        "severity": "INFO",
        "min_zscore": None,
        "active": False,
        "confidence": "HIGH" if best_corr >= 0.9 else "MEDIUM",
        "interpretation": (
            f"форма сезона похожа на историческую, но сдвинута примерно на "
            f"{abs(best_lag)} дней {direction}"
        ),
        "evidence": {"lag_days": best_lag, "shape_corr": best_corr, "unshifted_corr": zero_corr},
    }


def _finite(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _status(zscore: float | None) -> str:
    if zscore is None:
        return "UNKNOWN"
    if zscore < -2.0:
        return "CRITICAL"
    if zscore < -1.0:
        return "STRESSED"
    return "NORMAL"


def _attach_evidence(series, current, history, weather, current_year):
    observed = {item.date: item for item in current}
    years = sorted({date.fromisoformat(item.date).year for item in history})

    def precipitation_30(day):
        values = [weather.get(str(day - timedelta(days=offset)), {}).get("precipitation_mm") for offset in range(30)]
        # Сумма по редким спутниковым датам не является осадками за 30 дней.
        return float(sum(values)) if all(value is not None and np.isfinite(value) for value in values) else None

    def standardized(value, references, floor):
        finite = [item for item in references if item is not None and np.isfinite(item)]
        if value is None or len(finite) < 2:
            return None
        return float((value - np.median(finite)) / max(float(np.std(finite)), floor))

    for point in series:
        day = date.fromisoformat(point["date"])
        item = observed.get(point["date"])
        point.setdefault("reference_years", sum(
            sum(date.fromisoformat(ref.date).year == year for ref in history) >= 3 for year in years if
            year != current_year))
        point["valid_fraction"] = item.valid_fraction if item else None
        historical_days = [same_day(day, year) for year in years if year != current_year]
        point["temperature_z"] = standardized(
            point.get("temperature_c"),
            [weather.get(str(ref), {}).get("temperature_c") for ref in historical_days], .8)
        point["precip_30_z"] = standardized(
            precipitation_30(day), [precipitation_30(ref) for ref in historical_days], 5.0)
        point["ndmi_z"] = None
        if item and "ndmi" in item.indices:
            references = []
            for year in years:
                values = [ref.indices["ndmi"] for ref in history
                          if ref.source == item.source and "ndmi" in ref.indices
                          and date.fromisoformat(ref.date).year == year
                          and abs(date.fromisoformat(ref.date).timetuple().tm_yday - day.timetuple().tm_yday) <= 20]
                if values:
                    references.append(float(np.median(values)))
            point["ndmi_z"] = standardized(item.indices["ndmi"], references, .03)
