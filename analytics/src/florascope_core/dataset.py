from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from .schema import CROP, DATE, ID, SYNTHETIC, TARGET, ensure_base


def load_csv(path: str | Path) -> pd.DataFrame:
    """Читает organizer CSV и приводит минимальный набор полей к общей схеме."""

    frame = pd.read_csv(path, low_memory=False).reset_index(drop=True)
    ensure_base(frame.columns.tolist())

    frame[ID] = frame[ID].astype(str)
    frame[DATE] = pd.to_datetime(frame[DATE], errors="raise")
    frame[CROP] = frame[CROP].fillna("UNKNOWN").astype(str)

    # В private_features target может отсутствовать целиком. Для core удобнее,
    # когда схема train/test после чтения одинаковая.
    if TARGET not in frame:
        frame[TARGET] = np.nan
    if SYNTHETIC not in frame:
        frame[SYNTHETIC] = False

    frame[SYNTHETIC] = (
        frame[SYNTHETIC]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes"})
    )

    date_year = frame[DATE].dt.year
    date_doy = frame[DATE].dt.dayofyear
    if "year" in frame:
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").fillna(date_year).astype(int)
    else:
        frame["year"] = date_year.astype(int)
    if "doy" in frame:
        frame["doy"] = pd.to_numeric(frame["doy"], errors="coerce").fillna(date_doy).astype(int)
    else:
        frame["doy"] = date_doy.astype(int)
    return frame


def dataset_summary(frame: pd.DataFrame) -> dict:
    return {
        "rows": int(len(frame)),
        "polygons": int(frame[ID].nunique()),
        "years": [int(frame["year"].min()), int(frame["year"].max())],
        "primary_known": int(frame[TARGET].notna().sum()),
        "synthetic_gaps": int(frame[SYNTHETIC].sum()),
        "crops": sorted(frame[CROP].unique().tolist()),
    }


def primary_source(frame: pd.DataFrame) -> pd.Series:
    """Источник primary_ndvi по фактически найденному в train приоритету."""

    source = pd.Series("unknown", index=frame.index, dtype="object")
    source.loc[frame.get("modis_ndvi", pd.Series(index=frame.index, dtype=float)).notna()] = "modis"
    source.loc[frame.get("landsat_ndvi", pd.Series(index=frame.index, dtype=float)).notna()] = "landsat"
    source.loc[frame.get("s2_ndvi", pd.Series(index=frame.index, dtype=float)).notna()] = "s2"
    return source


def source_priority_audit(frame: pd.DataFrame) -> dict:
    known = frame.loc[frame[TARGET].notna()]
    if known.empty:
        return {"checked": 0, "matches": 0, "match_rate": None, "source_counts": {}}

    expected = np.full(len(known), np.nan, dtype=float)
    chosen = np.full(len(known), "unknown", dtype=object)
    for column, name in (("modis_ndvi", "modis"), ("landsat_ndvi", "landsat"), ("s2_ndvi", "s2")):
        if column not in known:
            continue
        values = pd.to_numeric(known[column], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(values)
        expected[mask] = values[mask]
        chosen[mask] = name

    target = known[TARGET].to_numpy(dtype=float)
    comparable = np.isfinite(expected)
    matches = np.isclose(target[comparable], expected[comparable], atol=1e-10, rtol=0)
    counts = pd.Series(chosen[comparable]).value_counts().to_dict()
    return {
        "checked": int(comparable.sum()),
        "matches": int(matches.sum()),
        "match_rate": float(matches.mean()) if matches.size else None,
        "source_counts": {str(key): int(value) for key, value in counts.items()},
    }
