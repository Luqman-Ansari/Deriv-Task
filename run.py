"""
CLI entry point for the AI Evaluation Pipeline.

Usage:
    python run.py evaluate   # Run the full pipeline and generate all artifacts
    python run.py validate   # Validate existing artifacts without re-running
"""
import argparse
import sys


def _cmd_evaluate(_args: argparse.Namespace) -> None:
    from pipeline.pipeline import run
    success = run()
    sys.exit(0 if success else 1)


def _cmd_validate(_args: argparse.Namespace) -> None:
    from validate import run_validation
    passed = run_validation(silent=False)
    sys.exit(0 if passed else 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="AI task evaluation pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("evaluate", help="Run the full evaluation pipeline")
    sub.add_parser("validate", help="Validate existing pipeline artifacts")

    args = parser.parse_args()
    if args.command == "evaluate":
        _cmd_evaluate(args)
    elif args.command == "validate":
        _cmd_validate(args)


if __name__ == "__main__":
    main()
