from __future__ import annotations

from florascope_core.pipeline import run_competition
from pathlib import Path


class CompetitionService:
    def __init__(self, *, data_dir: Path, artifacts_dir: Path) -> None:
        self.data_dir = data_dir
        self.artifacts_dir = artifacts_dir

    def run(self, *, train: Path, test: Path, fast: bool, progress) -> dict:
        return run_competition(
            train,
            test,
            self.artifacts_dir / "competition_model",
            self.data_dir / "output",
            fast=fast,
            progress=progress,
        )


def test_path(input_dir: Path) -> Path | None:
    for name in ("private_features.csv", "test_dataset.csv", "test.csv"):
        path = input_dir / name
        if path.exists():
            return path
    return None
