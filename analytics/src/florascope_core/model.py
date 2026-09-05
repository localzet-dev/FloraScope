from __future__ import annotations

import joblib
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass
from lightgbm import LGBMClassifier, LGBMRegressor
from pathlib import Path

SOURCE_NAMES = ["s2", "landsat", "modis"]


@dataclass(slots=True)
class RecoveryBundle:
    general_models: list[LGBMRegressor]
    source_classifier: LGBMClassifier | None
    source_models: dict[str, list[LGBMRegressor]]
    feature_names: list[str]
    crop_categories: list[str]
    general_weight: float = 1.0
    baseline: str | None = None
    model_weight: float = 1.0

    def predict_components(self, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
        aligned = x.reindex(columns=self.feature_names)
        general = _mean_prediction(self.general_models, aligned)

        if self.source_classifier is None or not self.source_models:
            return general, None

        probabilities = self.source_classifier.predict_proba(aligned)
        source_stack = []
        for source in SOURCE_NAMES:
            models = self.source_models.get(source)
            if not models:
                source_stack.append(general)
            else:
                source_stack.append(_mean_prediction(models, aligned))

        source_predictions = np.column_stack(source_stack)
        weighted = np.sum(source_predictions * probabilities, axis=1)
        return general, weighted

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        aligned = x.reindex(columns=self.feature_names)
        general, source_aware = self.predict_components(aligned)
        model_prediction = general
        if source_aware is not None:
            model_prediction = self.general_weight * general + (1.0 - self.general_weight) * source_aware

        prediction = model_prediction
        if self.baseline and self.baseline in aligned:
            baseline = aligned[self.baseline].to_numpy(dtype=float)
            baseline = np.where(np.isfinite(baseline), baseline, model_prediction)
            prediction = self.model_weight * model_prediction + (1.0 - self.model_weight) * baseline
        return np.clip(prediction, -1.0, 1.0)

    def save(self, root: str | Path) -> None:
        path = Path(root)
        path.mkdir(parents=True, exist_ok=True)

        for index, model in enumerate(self.general_models):
            joblib.dump(model, path / f"general_{index}.joblib")
        if self.source_classifier is not None:
            joblib.dump(self.source_classifier, path / "source_classifier.joblib")
        for source, models in self.source_models.items():
            for index, model in enumerate(models):
                joblib.dump(model, path / f"source_{source}_{index}.joblib")

        metadata = {
            "general_models": len(self.general_models),
            "source_models": {source: len(models) for source, models in self.source_models.items()},
            "has_source_classifier": self.source_classifier is not None,
            "feature_names": self.feature_names,
            "crop_categories": self.crop_categories,
            "general_weight": self.general_weight,
            "baseline": self.baseline,
            "model_weight": self.model_weight,
        }
        (path / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, root: str | Path) -> "RecoveryBundle":
        path = Path(root)
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        general_models = [
            joblib.load(path / f"general_{index}.joblib")
            for index in range(int(metadata["general_models"]))
        ]
        classifier = None
        if metadata.get("has_source_classifier"):
            classifier = joblib.load(path / "source_classifier.joblib")

        source_models: dict[str, list[LGBMRegressor]] = {}
        for source, count in metadata.get("source_models", {}).items():
            source_models[source] = [
                joblib.load(path / f"source_{source}_{index}.joblib")
                for index in range(int(count))
            ]
        return cls(
            general_models=general_models,
            source_classifier=classifier,
            source_models=source_models,
            feature_names=list(metadata["feature_names"]),
            crop_categories=list(metadata["crop_categories"]),
            general_weight=float(metadata.get("general_weight", 1.0)),
            baseline=metadata.get("baseline"),
            model_weight=float(metadata.get("model_weight", 1.0)),
        )


def fit_recovery_model(
    x: pd.DataFrame,
    y: np.ndarray,
    source_labels: np.ndarray,
    *,
    fast: bool = False,
) -> RecoveryBundle:
    params = _regression_params(fast)
    seeds = (17,)

    general_models: list[LGBMRegressor] = []
    for seed in seeds:
        model = LGBMRegressor(**params, random_state=seed)
        model.fit(x, y)
        general_models.append(model)

    classifier = LGBMClassifier(
        n_estimators=220 if fast else 300,
        learning_rate=0.04 if fast else 0.03,
        num_leaves=47 if fast else 63,
        min_child_samples=12,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        verbosity=-1,
        n_jobs=-1,
        random_state=19,
        objective="multiclass",
        num_class=3,
    )
    classifier.fit(x, source_labels)

    source_models: dict[str, list[LGBMRegressor]] = {}
    for source_index, source_name in enumerate(SOURCE_NAMES):
        mask = source_labels == source_index
        if int(mask.sum()) < 100:
            continue
        models: list[LGBMRegressor] = []
        for seed in seeds:
            model = LGBMRegressor(**params, random_state=seed + source_index * 101)
            model.fit(x.loc[mask], y[mask])
            models.append(model)
        source_models[source_name] = models

    return RecoveryBundle(
        general_models=general_models,
        source_classifier=classifier,
        source_models=source_models,
        feature_names=list(x.columns),
        crop_categories=[],
    )


def _regression_params(fast: bool) -> dict:
    return {
        "n_estimators": 320 if fast else 400,
        "learning_rate": 0.04 if fast else 0.035,
        "num_leaves": 55 if fast else 63,
        "min_child_samples": 12,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "reg_lambda": 1.2,
        "reg_alpha": 0.03,
        "verbosity": -1,
        "n_jobs": -1,
    }


def _mean_prediction(models: list[LGBMRegressor], x: pd.DataFrame) -> np.ndarray:
    stack = np.stack([model.predict(x) for model in models])
    return stack.mean(axis=0)
