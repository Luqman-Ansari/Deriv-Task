"""
Pipeline orchestrator.

Drives tasks through every stage in order, enforcing the stage state machine.
Call run() to execute the full pipeline end-to-end.
"""
import pathlib

from pipeline.llm_logger import init_log_file
from pipeline.state import PipelineState, Stage
from pipeline.stages import (
    stage_00_parse,
    stage_01_quality,
    stage_02_safety,
    stage_03_retry,
    stage_04_report,
    stage_05_consistency,
)

BASE = pathlib.Path(".")

_SUITE_PATH = BASE / "task_suite.json"
_POLICIES_DIR = BASE / "policies"
_PARSED_DIR = BASE / "parsed_tasks"
_QUALITY_OUT = BASE / "quality_eval.json"
_SAFETY_OUT = BASE / "safety_review.json"
_RETRY_OUT = BASE / "retry_instructions.json"
_SUMMARY_OUT = BASE / "summary.json"
_REPORT_OUT = BASE / "final_report.md"
_CONSISTENCY_OUT = BASE / "consistency_check.json"


def run() -> bool:
    """Execute the evaluation pipeline. Returns True if validation passes."""
    state = PipelineState()
    init_log_file()

    print("\n========================================")
    print(" AI Evaluation Pipeline")
    print("========================================\n")

    # ── INIT → INPUTS_LOADED ──────────────────────────────────────────────
    print(f"Loading inputs from {_SUITE_PATH}")
    state.advance(Stage.INPUTS_LOADED)

    # ── INPUTS_LOADED → TASKS_PARSED ─────────────────────────────────────
    print("\nStage 0: Parsing tasks (deterministic)...")
    parsed_tasks = stage_00_parse.run(_SUITE_PATH, _PARSED_DIR)
    print(f"  Parsed {len(parsed_tasks)} task(s) → {_PARSED_DIR / 'tasks.json'}")
    state.advance(Stage.TASKS_PARSED)

    # ── TASKS_PARSED → QUALITY_EVALUATED ─────────────────────────────────
    print("\nStage 1: Quality Evaluation (LLM)...")
    quality_results = stage_01_quality.run(parsed_tasks, _QUALITY_OUT)
    print(f"  Evaluated {len(quality_results)} task(s) → {_QUALITY_OUT}")
    state.advance(Stage.QUALITY_EVALUATED)

    # ── QUALITY_EVALUATED → SAFETY_REVIEWED ──────────────────────────────
    print("\nStage 2: Safety Review (LLM)...")
    safety_results = stage_02_safety.run(parsed_tasks, _SAFETY_OUT, _POLICIES_DIR)
    print(f"  Reviewed {len(safety_results)} task(s) → {_SAFETY_OUT}")
    state.advance(Stage.SAFETY_REVIEWED)

    # ── SAFETY_REVIEWED → RETRY_INSTRUCTIONS_GENERATED ───────────────────
    print("\nStage 3: Retry Instruction Generation (LLM, scores excluded)...")
    retry_results = stage_03_retry.run(parsed_tasks, _RETRY_OUT)
    print(f"  Generated {len(retry_results)} instruction(s) → {_RETRY_OUT}")
    state.advance(Stage.RETRY_INSTRUCTIONS_GENERATED)

    # ── RETRY_INSTRUCTIONS_GENERATED → FINAL_REPORT_COMPUTED ─────────────
    print("\nStage 4: Final Report (deterministic)...")
    summaries = stage_04_report.run(
        quality_results, safety_results, retry_results, _SUMMARY_OUT, _REPORT_OUT
    )
    print(f"  Summary → {_SUMMARY_OUT}")
    print(f"  Report  → {_REPORT_OUT}")

    print("\nStage 5: Consistency Check (LLM)...")
    stage_05_consistency.run(quality_results, _CONSISTENCY_OUT)
    state.advance(Stage.FINAL_REPORT_COMPUTED)

    # ── FINAL_REPORT_COMPUTED → VALIDATION_COMPLETE ───────────────────────
    print("\nValidating all artifacts...")
    from validate import run_validation
    passed = run_validation(silent=False)
    state.advance(Stage.VALIDATION_COMPLETE)

    if not passed:
        print("\n[PIPELINE] Validation FAILED — artifacts written but pipeline halted.")
        return False

    # ── VALIDATION_COMPLETE → RESULTS_FINALISED ───────────────────────────
    state.advance(Stage.RESULTS_FINALISED)

    # Print summary table
    print("\n========================================")
    print(" Results Summary")
    print("========================================")
    print(f"{'Task ID':<12} {'IFS':>4} {'TSS':>4} {'Violations':>12} {'Verdict':<8}")
    print("-" * 46)
    for sm in summaries:
        print(
            f"{sm.task_id:<12} {sm.instruction_following_score:>4} "
            f"{sm.task_success_score:>4} {sm.violation_count:>12} "
            f"{sm.final_verdict.upper():<8}"
        )
    print("========================================\n")

    return True
