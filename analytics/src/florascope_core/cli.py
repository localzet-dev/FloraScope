from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .inspect import inspect_dataset
from .model import RecoveryBundle
from .pipeline import benchmark, benchmark_many, infer, run_competition
from .smoke import generate_competition_fixture
from .submission import validate_submission


def main() -> None:
    parser = argparse.ArgumentParser(prog="florascope-core")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--dataset", required=True)

    bench = sub.add_parser("benchmark")
    bench.add_argument("--train", required=True)
    bench.add_argument("--seed", type=int, default=9901)
    bench.add_argument("--fast", action="store_true")
    bench.add_argument(
        "--three-seeds",
        action="store_true",
        help="Дольше: 9901/10039/10177 вместо одного фиксированного split",
    )

    competition = sub.add_parser("competition")
    competition.add_argument("--train", required=True)
    competition.add_argument("--input", required=True)
    competition.add_argument("--output", required=True)
    competition.add_argument("--artifacts", required=True)
    competition.add_argument("--fast", action="store_true")
    competition.add_argument("--no-cv", action="store_true")
    competition.add_argument(
        "--calibration",
        help="JSON CVReport. Удобно вместе с --no-cv для быстрого production run",
    )

    inference = sub.add_parser("infer")
    inference.add_argument("--model", required=True)
    inference.add_argument("--input", required=True)
    inference.add_argument("--output", required=True)

    validate = sub.add_parser("validate-submission")
    validate.add_argument("--test", required=True)
    validate.add_argument("--submission", required=True)

    smoke = sub.add_parser("smoke")
    smoke.add_argument("--root", default="./data/smoke")

    sub.add_parser("version")

    args = parser.parse_args()
    if args.command == "inspect":
        result = inspect_dataset(args.dataset)
    elif args.command == "benchmark":
        if args.three_seeds:
            result = benchmark_many(args.train, fast=args.fast)
        else:
            result = asdict(benchmark(args.train, seed=args.seed, fast=args.fast))
    elif args.command == "competition":
        result = run_competition(
            args.train,
            args.input,
            args.artifacts,
            args.output,
            fast=args.fast,
            run_cv=not args.no_cv,
            calibration_path=args.calibration,
        )
    elif args.command == "infer":
        bundle = RecoveryBundle.load(args.model)
        result = infer(args.input, bundle, args.output)
    elif args.command == "validate-submission":
        result = validate_submission(args.test, args.submission)
    elif args.command == "smoke":
        root = Path(args.root)
        train, test = generate_competition_fixture(root / "input")
        result = run_competition(train, test, root / "artifacts", root / "output", fast=True)
    else:
        result = {"version": __version__}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
