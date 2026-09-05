from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Iterable

from .schema import (
    CROP,
    DATE,
    DYNAMIC_COLUMNS,
    ID,
    SENSOR_COLUMNS,
    SOURCE_NDVI,
    TARGET,
    WEATHER_COLUMNS,
)
from .smoothing import whittaker_curve


@dataclass(slots=True)
class FeatureBatch:
    x: pd.DataFrame
    y: np.ndarray | None
    indices: list[int]


class FeatureBuilder:
    """Строит признаки только из контекста, который реально остаётся у target row."""

    def __init__(self, frame: pd.DataFrame, crop_categories: list[str] | None = None) -> None:
        self.frame = frame
        self.crop_categories = crop_categories or sorted(frame[CROP].unique().tolist())

    def build(self, targets: Iterable[int], context_mask: set[int]) -> FeatureBatch:
        indices = [int(index) for index in targets]
        work = self.frame.copy()
        dynamic = [column for column in DYNAMIC_COLUMNS if column in work]

        # В test synthetic row очищена почти целиком. Если на CV маскировать только
        # primary_ndvi, модель увидит скрытые S2/Landsat/MODIS признаки и CV соврёт.
        if context_mask:
            work.loc[list(context_mask), dynamic] = np.nan

        work = work.sort_values([ID, "year", DATE])
        features = pd.DataFrame(index=work.index)
        group_keys = [work[ID], work["year"]]

        self._date_and_crop(work, features)
        self._temporal_channels(work, features, group_keys)
        self._primary_neighbours(work, features, group_keys)
        self._season_stats(work, features, group_keys)
        self._climatology(work, features, group_keys)
        # После десятков transform/insert pandas фрагментирует DataFrame. Копия здесь
        # дешевле, чем таскать PerformanceWarning по всем benchmark-прогонам.
        features = features.copy()
        self._whittaker(work, features)
        self._sensor_consensus(features)

        selected = features.loc[indices].replace([np.inf, -np.inf], np.nan)
        labels = self.frame.loc[indices, TARGET]
        y = labels.to_numpy(dtype=float) if labels.notna().all() else None
        return FeatureBatch(selected.reset_index(drop=True), y, indices)

    def _date_and_crop(self, work: pd.DataFrame, features: pd.DataFrame) -> None:
        features["doy"] = work["doy"].astype(float)
        features["sin_doy"] = np.sin(2 * np.pi * work["doy"] / 365.25)
        features["cos_doy"] = np.cos(2 * np.pi * work["doy"] / 365.25)
        features["year"] = work["year"].astype(float) - 2010.0
        for category in self.crop_categories:
            features[f"crop__{category}"] = (work[CROP] == category).astype(float)

    def _temporal_channels(
        self,
        work: pd.DataFrame,
        features: pd.DataFrame,
        group_keys: list[pd.Series],
    ) -> None:
        for column in [TARGET, *SENSOR_COLUMNS, *WEATHER_COLUMNS]:
            if column not in work:
                continue

            series = pd.to_numeric(work[column], errors="coerce")
            grouped = series.groupby(group_keys, sort=False)
            features[f"{column}__prev"] = grouped.ffill()
            features[f"{column}__next"] = grouped.bfill()
            features[f"{column}__interp"] = grouped.transform(
                lambda values: values.interpolate(limit_direction="both")
            )
            features[f"{column}__count"] = grouped.transform("count").astype(float)

            observed_date = work[DATE].where(series.notna())
            prev_date = observed_date.groupby(group_keys, sort=False).ffill()
            next_date = observed_date.groupby(group_keys, sort=False).bfill()
            features[f"{column}__prev_gap"] = (work[DATE] - prev_date).dt.days.astype(float)
            features[f"{column}__next_gap"] = (next_date - work[DATE]).dt.days.astype(float)

        prev_gap = features.get("primary_ndvi__prev_gap")
        next_gap = features.get("primary_ndvi__next_gap")
        prev = features.get("primary_ndvi__prev")
        nxt = features.get("primary_ndvi__next")
        if prev_gap is not None and next_gap is not None and prev is not None and nxt is not None:
            denom = (prev_gap + next_gap).replace(0, np.nan)
            features["primary_slope"] = (nxt - prev) / denom
            features["primary_gap_span"] = prev_gap + next_gap

    def _primary_neighbours(
        self,
        work: pd.DataFrame,
        features: pd.DataFrame,
        group_keys: list[pd.Series],
    ) -> None:
        primary = pd.to_numeric(work[TARGET], errors="coerce")
        # shift работает по уже очищенному ряду, поэтому эти значения тоже leak-safe.
        grouped = primary.groupby(group_keys, sort=False)
        for offset in range(1, 5):
            features[f"primary_prev_{offset}"] = grouped.shift(offset)
            features[f"primary_next_{offset}"] = grouped.shift(-offset)

    def _season_stats(
        self,
        work: pd.DataFrame,
        features: pd.DataFrame,
        group_keys: list[pd.Series],
    ) -> None:
        primary = pd.to_numeric(work[TARGET], errors="coerce")
        season = primary.groupby(group_keys, sort=False)
        features["season_mean"] = season.transform("mean")
        features["season_std"] = season.transform("std")
        features["season_min"] = season.transform("min")
        features["season_max"] = season.transform("max")
        features["season_count"] = season.transform("count").astype(float)
        features["season_amplitude"] = features["season_max"] - features["season_min"]

    def _climatology(
        self,
        work: pd.DataFrame,
        features: pd.DataFrame,
        group_keys: list[pd.Series],
    ) -> None:
        primary = pd.to_numeric(work[TARGET], errors="coerce")
        aoi_doy = primary.groupby([work[ID], work["doy"]], sort=False)
        features["aoi_climatology"] = aoi_doy.transform("median")
        features["aoi_climatology_std"] = aoi_doy.transform("std")

        crop_doy = primary.groupby([work[CROP], work["doy"]], sort=False)
        features["crop_climatology"] = crop_doy.transform("median")
        features["crop_climatology_std"] = crop_doy.transform("std")

        residual = primary - features["aoi_climatology"]
        residual_group = residual.groupby(group_keys, sort=False)
        features["clim_residual_prev"] = residual_group.ffill()
        features["clim_residual_next"] = residual_group.bfill()
        features["clim_corrected"] = features["aoi_climatology"] + 0.5 * (
            features["clim_residual_prev"] + features["clim_residual_next"]
        )

        # Эти organizer columns на hidden row отсутствуют. Берём только интерполяцию
        # видимых соседей, чтобы условия train/test оставались одинаковыми.
        for column in ("ndvi_climatology_mean", "ndvi_climatology_std", "n_reference_years"):
            if column not in work:
                continue
            grouped = pd.to_numeric(work[column], errors="coerce").groupby(group_keys, sort=False)
            features[f"{column}__interp"] = grouped.transform(
                lambda values: values.interpolate(limit_direction="both")
            )

    def _whittaker(self, work: pd.DataFrame, features: pd.DataFrame) -> None:
        result = pd.Series(np.nan, index=work.index, dtype=float)
        for _, group in work.groupby([ID, "year"], sort=False):
            visible = group[TARGET].notna()
            if visible.sum() < 2:
                continue
            days = group.loc[visible, "doy"].to_numpy(dtype=int)
            values = group.loc[visible, TARGET].to_numpy(dtype=float)
            curve = whittaker_curve(days, values)
            result.loc[group.index] = curve[group["doy"].to_numpy(dtype=int) - 1]
        features["whittaker"] = result

    def _sensor_consensus(self, features: pd.DataFrame) -> None:
        columns = [
            f"{column}__interp"
            for column in SOURCE_NDVI
            if f"{column}__interp" in features
        ]
        if not columns:
            return
        features["sensor_ndvi_median"] = features[columns].median(axis=1, skipna=True)
        features["sensor_ndvi_spread"] = features[columns].std(axis=1, skipna=True)
