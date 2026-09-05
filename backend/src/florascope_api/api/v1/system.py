from __future__ import annotations

from fastapi import APIRouter, Depends

from ... import __version__
from ...container import Container, container
from ...services.competition import test_path as _test_path

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/system")
def system(state: Container = Depends(container)) -> dict:
    input_dir = state.settings.data_dir / "input"
    test = _test_path(input_dir)
    return {
        "version": __version__,
        "files": {
            "train": (input_dir / "train_dataset.csv").exists(),
            "test": test is not None,
            "report": (state.settings.data_dir / "output" / "report.json").exists(),
            "submission": (state.settings.data_dir / "output" / "submission.csv").exists(),
        },
        "fields": len(state.fields.list()),
        "analyses": len(state.analyses.list()),
        "analysis_resolution_m": state.settings.analysis_resolution_m,
    }
