from __future__ import annotations

import json
import numpy as np
import pandas as pd
import warnings
from pathlib import Path

from .schema import DATE, ID
from .smoothing import linear_curve

MIN_REFERENCE_YEARS = 2


def analyze_vegetation(frame: pd.DataFrame, output_dir: str | Path) -> tuple[Path, Path]:
    """Строит baseline аномалий и простой evidence layer для объяснений.

    Ключевой момент: норма для сезона считается только по другим годам этого
    полигона. Текущий год в reference не попадает, иначе сильная аномалия сама
    подтянет к себе climatology и станет выглядеть слабее.
    """

    work = frame.sort_values([ID, DATE]).copy()
    climatology, spread, reference_years = _historical_reference(
        work,
        "primary_ndvi_filled",
        min_spread=0.035,
    )
    work["climatology_calc"] = climatology
    work["climatology_std_calc"] = spread
    work["reference_years_calc"] = reference_years
    work["ndvi_zscore_calc"] = (
                                   work["primary_ndvi_filled"] - work["climatology_calc"]
                               ) / work["climatology_std_calc"]
    work["status_calc"] = np.select(
        [work["ndvi_zscore_calc"] < -2.0, work["ndvi_zscore_calc"] < -1.0],
        ["CRITICAL", "STRESSED"],
        default="NORMAL",
    )

    work.loc[work["ndvi_zscore_calc"].isna(), "status_calc"] = "UNKNOWN"

    _context_features(work)
    events = _negative_events(work)
    events.extend(_phenology_events(work))

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    points_path = root / "analysis_points.csv"
    events_path = root / "events.csv"
    work.to_csv(points_path, index=False)

    event_columns = [
        ID,
        "kind",
        "severity",
        "start",
        "end",
        "observations",
        "min_zscore",
        "confidence",
        "interpretation",
        "evidence_json",
    ]
    pd.DataFrame(events, columns=event_columns).to_csv(events_path, index=False)
    return points_path, events_path


def _historical_reference(
    frame: pd.DataFrame,
    column: str,
    *,
    min_spread: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """DOY-норма по другим сезонам того же AOI.

    У спутников даты съёмок по годам чуть гуляют, поэтому сравнивать только
    одинаковый day-of-year слишком хрупко. Сначала интерполируем каждый сезон
    на суточную сетку, затем для года берём median/std остальных сезонов.
    """

    mean_result = pd.Series(np.nan, index=frame.index, dtype=float)
    std_result = pd.Series(np.nan, index=frame.index, dtype=float)
    count_result = pd.Series(0.0, index=frame.index, dtype=float)

    if column not in frame:
        return mean_result, std_result, count_result

    for _, aoi in frame.groupby(ID, sort=False):
        curves: dict[int, np.ndarray] = {}
        for year, season in aoi.groupby("year", sort=False):
            visible = season[["doy", column]].dropna()
            if len(visible) < 2:
                continue
            curves[int(year)] = linear_curve(
                visible["doy"].to_numpy(dtype=int),
                visible[column].to_numpy(dtype=float),
            )
            curves[int(year)][:int(visible["doy"].min()) - 1] = np.nan
            curves[int(year)][int(visible["doy"].max()):] = np.nan

        for year, season in aoi.groupby("year", sort=False):
            references = [curve for ref_year, curve in curves.items() if ref_year != int(year)]
            if len(references) < MIN_REFERENCE_YEARS:
                continue
            stack = np.stack(references)
            counts = np.isfinite(stack).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                median = np.nanmedian(stack, axis=0)
                spread = np.nanstd(stack, axis=0)
            median[counts < MIN_REFERENCE_YEARS] = np.nan
            spread[counts < MIN_REFERENCE_YEARS] = np.nan
            spread = np.maximum(spread, min_spread)
            days = season["doy"].to_numpy(dtype=int) - 1
            mean_result.loc[season.index] = median[days]
            std_result.loc[season.index] = spread[days]
            count_result.loc[season.index] = counts[days]

    return mean_result, std_result, count_result


def _context_features(work: pd.DataFrame) -> None:
    ndwi_columns = [column for column in ("s2_ndwi", "landsat_ndwi") if column in work]
    if ndwi_columns:
        work["water_index"] = work[ndwi_columns].median(axis=1, skipna=True)
        normal, spread, _ = _historical_reference(work, "water_index", min_spread=0.03)
        work["water_zscore"] = (work["water_index"] - normal) / spread

    if "era5_precip_mm" in work:
        precip = pd.to_numeric(work["era5_precip_mm"], errors="coerce")
        work["precip_30_proxy"] = precip.groupby(
            [work[ID], work["year"]], sort=False
        ).transform(lambda values: values.rolling(6, min_periods=2).sum())
        normal, spread, _ = _historical_reference(
            work,
            "precip_30_proxy",
            min_spread=1.0,
        )
        work["precip_zscore"] = (work["precip_30_proxy"] - normal) / spread

    if "era5_temp_c" in work:
        work["temp_value"] = pd.to_numeric(work["era5_temp_c"], errors="coerce")
        normal, spread, _ = _historical_reference(work, "temp_value", min_spread=0.8)
        work["temp_zscore"] = (work["temp_value"] - normal) / spread


def _negative_events(work: pd.DataFrame) -> list[dict]:
    events: list[dict] = []
    for (aoi, _), group in work.groupby([ID, "year"], sort=False):
        block = []
        last_date = None
        for _, row in group.sort_values(DATE).iterrows():
            negative = pd.notna(row["ndvi_zscore_calc"]) and row["ndvi_zscore_calc"] < -1.0
            if not negative or (last_date is not None and (row[DATE] - last_date).days > 20):
                if _supported_block(block):
                    events.append(_event(str(aoi), block))
                block = []
            if negative:
                block.append(row)
            last_date = row[DATE]
        if _supported_block(block):
            events.append(_event(str(aoi), block))
    return events


def _supported_block(rows: list[pd.Series]) -> bool:
    if len(rows) < 2 or (rows[-1][DATE] - rows[0][DATE]).days < 5:
        return False
    # Интерполяция даёт траекторию, но не независимые подтверждения события.
    return sum(pd.notna(row.get("primary_ndvi", row["primary_ndvi_filled"])) for row in rows) >= 2


def _event(aoi: str, rows: list[pd.Series]) -> dict:
    frame = pd.DataFrame(rows)
    min_z = float(frame["ndvi_zscore_calc"].min())
    severity = "CRITICAL" if min_z < -2.0 else "STRESSED"

    evidence: dict[str, float] = {"ndvi_min_z": min_z}
    water = _median_if_exists(frame, "water_zscore")
    precip = _median_if_exists(frame, "precip_zscore")
    temp = _median_if_exists(frame, "temp_zscore")
    if water is not None:
        evidence["water_z"] = water
    if precip is not None:
        evidence["precip_z"] = precip
    if temp is not None:
        evidence["temp_z"] = temp

    cause = "устойчивое снижение зелёной биомассы относительно сезонной нормы"
    if water is not None and water < -1.0 and precip is not None and precip < -0.8:
        cause = (
            "сигналы совместимы с дефицитом влаги: NDVI и водный индекс "
            "снижены, осадков меньше нормы"
        )
    elif temp is not None and temp > 1.2 and precip is not None and precip < -0.8:
        cause = "сигналы совместимы с жарким/сухим периодом; это гипотеза, а не диагноз"
    elif water is not None and water < -1.0:
        cause = "вместе с NDVI просел водный индекс; возможен водный стресс"

    confidence_score = 0
    observed_count = int(frame.get("primary_ndvi", frame["primary_ndvi_filled"]).notna().sum())
    evidence["observed_points"] = observed_count
    confidence_score += 1 if observed_count >= 3 else 0
    confidence_score += 1 if min_z < -2.0 else 0
    confidence_score += 1 if (water is not None and water < -1) or (precip is not None and precip < -0.8) else 0
    confidence = ["LOW", "MEDIUM", "HIGH", "HIGH"][confidence_score]

    return {
        ID: aoi,
        "kind": "NEGATIVE_DEVIATION",
        "severity": severity,
        "start": frame[DATE].min().strftime("%Y-%m-%d"),
        "end": frame[DATE].max().strftime("%Y-%m-%d"),
        "observations": int(len(frame)),
        "min_zscore": min_z,
        "confidence": confidence,
        "interpretation": cause,
        "evidence_json": json.dumps(evidence, ensure_ascii=False),
    }


def _phenology_events(work: pd.DataFrame) -> list[dict]:
    events: list[dict] = []
    for (aoi, year), group in work.groupby([ID, "year"], sort=False):
        visible = group[["doy", "primary_ndvi_filled", "climatology_calc"]].dropna()
        if len(visible) < 8:
            continue

        days = visible["doy"].to_numpy(dtype=int)
        shift = phenology_shift(
            linear_curve(days, visible["primary_ndvi_filled"].to_numpy(dtype=float)),
            linear_curve(days, visible["climatology_calc"].to_numpy(dtype=float)),
            days,
        )
        if shift is None:
            continue
        lag_days, best_corr, zero_corr = shift
        direction = "позже" if lag_days > 0 else "раньше"
        events.append(
            {
                ID: str(aoi),
                "kind": "PHENOLOGY_SHIFT",
                "severity": "INFO",
                "start": f"{int(year)}-01-01",
                "end": f"{int(year)}-12-31",
                "observations": int(len(visible)),
                "min_zscore": np.nan,
                "confidence": "MEDIUM" if best_corr < 0.9 else "HIGH",
                "interpretation": (
                    f"сезонная кривая сдвинута примерно на {abs(lag_days)} дней "
                    f"{direction} исторического сценария"
                ),
                "evidence_json": json.dumps(
                    {"lag_days": lag_days, "shape_corr": best_corr, "unshifted_corr": zero_corr},
                    ensure_ascii=False,
                ),
            }
        )
    return events


def _median_if_exists(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.median())


def phenology_shift(current_curve: np.ndarray, expected_curve: np.ndarray, days: np.ndarray):
    """Сдвиг в календарных днях, с проверкой выигрыша над нулевым лагом.

    Почти линейный склон даёт высокую корреляцию при любом лаге: это ещё
    не фенологический сдвиг. Сравниваем одинаковый интервал для всех лагов.
    """
    start, end = int(days.min()) - 1, int(days.max())
    if len(days) < 8 or end - start < 60:
        return None
    positions = np.arange(start + 15, end - 15)
    current = current_curve[positions]
    if np.ptp(current) < 0.1:
        return None
    correlations = {}
    for lag in range(-15, 16, 5):
        expected = expected_curve[positions - lag]
        if np.std(expected) < 1e-5 or np.std(current) < 1e-5:
            continue
        corr = float(np.corrcoef(current, expected)[0, 1])
        if np.isfinite(corr):
            correlations[lag] = corr
    if 0 not in correlations:
        return None
    lag = max(correlations, key=lambda value: (correlations[value], -abs(value)))
    if abs(lag) < 10 or correlations[lag] < 0.75 or correlations[lag] - correlations[0] < 0.05:
        return None
    return lag, correlations[lag], correlations[0]
