from __future__ import annotations

from pathlib import Path

from .dataset import dataset_summary, load_csv, source_priority_audit


def inspect_dataset(path: str | Path) -> dict:
    frame = load_csv(path)
    return {
        **dataset_summary(frame),
        "source_priority": source_priority_audit(frame),
        "columns": [column for column in frame.columns],
    }
