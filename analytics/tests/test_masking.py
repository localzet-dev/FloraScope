from pathlib import Path

from florascope_core.dataset import load_csv
from florascope_core.masking import synthetic_mask
from florascope_core.smoke import generate_competition_fixture


def test_mask_is_deterministic_and_grouped(tmp_path: Path) -> None:
    train, _ = generate_competition_fixture(tmp_path)
    frame = load_csv(train)
    first = synthetic_mask(frame, seed=123)
    second = synthetic_mask(frame, seed=123)
    assert first == second
    assert len(first) > 0
