from __future__ import annotations

import json
import numpy as np
import pandas as pd
from dataclasses import asdict, dataclass
from pathlib import Path
from sklearn.metrics import accuracy_score, mean_squared_error
from time import perf_counter

from .anomaly import analyze_vegetation
from .dataset import dataset_summary, load_csv, primary_source
from .features import FeatureBuilder
from .masking import synthetic_mask
from .model import RecoveryBundle, fit_recovery_model
from .schema import DATE, ID, SYNTHETIC, TARGET
from .submission import validate_submission

SOURCE_TO_INDEX = {"s2": 0, "landsat": 1, "modis": 2}


@dataclass(slots=True)
class CVReport:
    rmse: float
    general_rmse: float
    source_aware_rmse: float | None
    organizer_score_estimate: float
    validation_targets: int
    baselines: dict[str, float]
    general_weight: float
    selected_baseline: str | None
    model_weight: float
    source_classifier_accuracy: float | None
    source_breakdown: dict[str, dict[str, float | int]]
    protocol: str = "legacy_outer_tuned"
    seed: int = 9901
    calibration_targets: int = 0


def load_cv_report(path: str | Path) -> CVReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CVReport(**payload)


def benchmark(
    train_path: str | Path,
    *,
    seed: int = 9901,
    fast: bool = False,
) -> CVReport:
    frame = load_csv(train_path)
    outer = synthetic_mask(frame, seed=seed)
    eligible = set(frame.index[frame[TARGET].notna()]) - outer
    builder = FeatureBuilder(frame)

    source_series = primary_source(frame)

    # Веса ансамбля тоже обучаемые параметры. Outer labels не должны выбирать
    # ни blend, ни baseline; для этого выделен отдельный mask внутри remaining.
    calibration_mask = synthetic_mask(frame, seed=seed + 50, eligible=eligible)
    calibration_bundle = _fit_masked(frame, builder, source_series, outer | calibration_mask, seed, fast)
    calibration_batch = builder.build(sorted(calibration_mask), outer | calibration_mask)
    general_weight, selected_baseline, model_weight = _calibrate(calibration_bundle, calibration_batch)

    # После выбора весов возвращаем calibration observations в обучение.
    # Основной outer mask и старые inner seeds остаются прежними.
    bundle = _fit_masked(frame, builder, source_series, outer, seed, fast)
    bundle.general_weight = general_weight
    bundle.baseline = selected_baseline
    bundle.model_weight = model_weight
    validation = builder.build(sorted(outer), outer)
    general, source_aware = bundle.predict_components(validation.x)
    general_rmse = _rmse(validation.y, general)
    source_rmse = _rmse(validation.y, source_aware) if source_aware is not None else None
    validation_source = _source_labels(source_series, validation.indices)
    source_accuracy = None
    if bundle.source_classifier is not None:
        source_accuracy = float(accuracy_score(validation_source, bundle.source_classifier.predict(validation.x)))
    final_prediction = bundle.predict(validation.x)
    final_rmse = _rmse(validation.y, final_prediction)
    baselines = {}
    for name in BASELINES:
        raw = validation.x[name].to_numpy(dtype=float)
        finite = np.isfinite(raw)
        if finite.any():
            baselines[name] = _rmse(validation.y[finite], raw[finite])

    breakdown: dict[str, dict[str, float | int]] = {}
    for source_name, source_index in SOURCE_TO_INDEX.items():
        mask = validation_source == source_index
        if not mask.any():
            continue
        breakdown[source_name] = {
            "rows": int(mask.sum()),
            "rmse": _rmse(validation.y[mask], final_prediction[mask]),
        }

    return CVReport(
        rmse=final_rmse,
        general_rmse=general_rmse,
        source_aware_rmse=source_rmse,
        organizer_score_estimate=round(30 * max(0.0, 1.0 - final_rmse / 0.10), 2),
        validation_targets=len(outer),
        baselines=baselines,
        general_weight=general_weight,
        selected_baseline=selected_baseline,
        model_weight=model_weight,
        source_classifier_accuracy=source_accuracy,
        source_breakdown=breakdown,
        protocol="nested_calibration_v1",
        seed=seed,
        calibration_targets=len(calibration_mask),
    )


BASELINES = ["primary_ndvi__interp", "whittaker", "sensor_ndvi_median", "clim_corrected", "aoi_climatology"]


def _fit_masked(frame, builder, source_series, excluded: set[int], seed: int, fast: bool):
    eligible = set(frame.index[frame[TARGET].notna()]) - excluded
    batches = []
    for offset in range(2 if fast else 3):
        inner = synthetic_mask(frame, seed=seed + 100 + offset, eligible=eligible)
        batches.append(builder.build(sorted(inner), excluded | inner))
    bundle = fit_recovery_model(
        pd.concat([batch.x for batch in batches], ignore_index=True),
        np.concatenate([batch.y for batch in batches]),
        np.concatenate([_source_labels(source_series, batch.indices) for batch in batches]),
        fast=fast,
    )
    bundle.crop_categories = builder.crop_categories
    return bundle


def _calibrate(bundle, batch) -> tuple[float, str | None, float]:
    general, source = bundle.predict_components(batch.x)
    general_weight = 1.0
    best = general
    if source is not None:
        general_weight = float(min(
            np.linspace(0, 1, 21),
            key=lambda weight: _rmse(batch.y, weight * general + (1 - weight) * source),
        ))
        best = general_weight * general + (1 - general_weight) * source
    score = _rmse(batch.y, np.clip(best, -1, 1))
    baseline, model_weight = None, 1.0
    for name in BASELINES:
        raw = batch.x[name].to_numpy(dtype=float)
        safe = np.where(np.isfinite(raw), raw, best)
        for weight in np.linspace(0, 1, 11):
            candidate = _rmse(batch.y, np.clip(weight * best + (1 - weight) * safe, -1, 1))
            if candidate < score:
                score, baseline, model_weight = candidate, name, float(weight)
    return general_weight, baseline, model_weight


def benchmark_many(
    train_path: str | Path,
    *,
    seeds: tuple[int, ...] = (9901, 10039, 10177),
    fast: bool = False,
) -> dict:
    reports = [benchmark(train_path, seed=seed, fast=fast) for seed in seeds]
    rmses = np.asarray([report.rmse for report in reports], dtype=float)
    return {
        "folds": [asdict(report) for report in reports],
        "rmse_mean": float(rmses.mean()),
        "rmse_std": float(rmses.std()),
        "score_mean": float(
            np.mean([report.organizer_score_estimate for report in reports])
        ),
    }


def train_production(
    train_path: str | Path,
    artifacts_dir: str | Path,
    *,
    calibration: CVReport | None,
    fast: bool = False,
) -> tuple[RecoveryBundle, dict]:
    started = perf_counter()
    frame = load_csv(train_path)
    builder = FeatureBuilder(frame)
    source_series = primary_source(frame)

    train_x: list[pd.DataFrame] = []
    train_y: list[np.ndarray] = []
    train_source: list[np.ndarray] = []
    for offset in range(2 if fast else 3):
        mask = synthetic_mask(frame, seed=15001 + offset)
        batch = builder.build(sorted(mask), mask)
        train_x.append(batch.x)
        train_y.append(batch.y)
        train_source.append(_source_labels(source_series, batch.indices))

    x = pd.concat(train_x, ignore_index=True)
    y = np.concatenate(train_y)
    source_labels = np.concatenate(train_source)
    bundle = fit_recovery_model(x, y, source_labels, fast=fast)
    bundle.crop_categories = builder.crop_categories

    if calibration is not None:
        bundle.general_weight = calibration.general_weight
        bundle.baseline = calibration.selected_baseline
        bundle.model_weight = calibration.model_weight
    bundle.save(artifacts_dir)

    return bundle, {
        "dataset": dataset_summary(frame),
        "training_examples": int(len(y)),
        "features": int(x.shape[1]),
        "general_models": len(bundle.general_models),
        "source_models": {
            source: len(models) for source, models in bundle.source_models.items()
        },
        "seconds": round(perf_counter() - started, 2),
    }


def infer(
    test_path: str | Path,
    bundle: RecoveryBundle,
    output_dir: str | Path,
) -> dict:
    frame = load_csv(test_path)
    targets = frame.index[frame[SYNTHETIC]].tolist()
    if not targets:
        raise ValueError("В test/private нет строк is_synthetic_gap=True")

    builder = FeatureBuilder(frame, crop_categories=bundle.crop_categories)
    batch = builder.build(targets, set(targets))
    prediction = bundle.predict(batch.x)

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    submission = pd.DataFrame(
        {
            ID: frame.loc[targets, ID].to_numpy(),
            DATE: frame.loc[targets, DATE].dt.strftime("%Y-%m-%d").to_numpy(),
            "primary_ndvi_pred": prediction,
        }
    )
    submission_path = root / "submission.csv"
    submission.to_csv(submission_path, index=False)
    validate_submission(test_path, submission_path)

    filled = frame.copy()
    filled["primary_ndvi_pred"] = np.nan
    filled.loc[targets, "primary_ndvi_pred"] = prediction
    filled["primary_ndvi_filled"] = filled[TARGET].where(
        filled[TARGET].notna(),
        filled["primary_ndvi_pred"],
    )

    # Natural gaps не относятся к метрике. Заполняем их только для непрерывного
    # графика и anomaly layer, в submission они не попадают.
    ordered = filled.sort_values([ID, "year", DATE])
    ordered["primary_ndvi_filled"] = ordered.groupby(
        [ID, "year"], sort=False
    )["primary_ndvi_filled"].transform(
        lambda values: values.interpolate(limit_direction="both")
    )
    points, events = analyze_vegetation(ordered, root)
    return {
        "dataset": dataset_summary(frame),
        "submission_rows": int(len(submission)),
        "submission": str(submission_path),
        "analysis_points": str(points),
        "events": str(events),
    }


def run_competition(
    train_path: str | Path,
    test_path: str | Path,
    artifacts_dir: str | Path,
    output_dir: str | Path,
    *,
    fast: bool = False,
    run_cv: bool = True,
    calibration_path: str | Path | None = None,
    progress=None,
) -> dict:
    def emit(percent: int, stage: str, message: str) -> None:
        if progress:
            progress(percent, stage, message)

    report: dict = {}
    validation = None
    if run_cv:
        emit(5, "VALIDATION", "Проверяем synthetic-gap CV без подглядывания")
        validation = benchmark(train_path, fast=fast)
        report["validation"] = asdict(validation)
    elif calibration_path is not None:
        # Для технического прогона можно использовать уже зафиксированный CV.
        # Так inference воспроизводит тот же blend без повторного 20-секундного benchmark.
        validation = load_cv_report(calibration_path)
        report["validation"] = asdict(validation)

    emit(40, "TRAINING", "Обучаем production-модель")
    bundle, training = train_production(
        train_path,
        artifacts_dir,
        calibration=validation,
        fast=fast,
    )
    report["training"] = training

    emit(78, "INFERENCE", "Восстанавливаем private synthetic gaps")
    report["inference"] = infer(test_path, bundle, output_dir)

    emit(94, "SUBMISSION", "Проверяем ключи и NaN в submission")
    report["submission_validation"] = validate_submission(
        test_path,
        Path(output_dir) / "submission.csv",
    )

    path = Path(output_dir) / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(100, "DONE", "Готово")
    return report


def _source_labels(source: pd.Series, indices: list[int]) -> np.ndarray:
    labels = source.loc[indices].map(SOURCE_TO_INDEX)
    if labels.isna().any():
        raise ValueError("Не удалось определить source label для части training targets")
    return labels.to_numpy(dtype=int)


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))
