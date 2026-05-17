"""
Validation script for the evaluation pipeline artifacts.

Can be run standalone:
    python validate.py

Or imported and called programmatically:
    from validate import run_validation
    passed = run_validation(silent=False)
"""
import json
import pathlib
import sys
from typing import Any

BASE = pathlib.Path(".")

_REQUIRED_FILES = [
    BASE / "parsed_tasks" / "tasks.json",
    BASE / "quality_eval.json",
    BASE / "safety_review.json",
    BASE / "retry_instructions.json",
    BASE / "summary.json",
    BASE / "final_report.md",
    BASE / "llm_calls.jsonl",
    BASE / "consistency_check.json",
]

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_HIGH_CRITICAL = {"high", "critical"}


def _load_json(path: pathlib.Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _recompute_verdict(quality: dict, safety: dict) -> str:
    """Mirror of stage_04_report.compute_verdict — must stay in sync."""
    violations = safety.get("violations", [])
    if any(v["severity"] in _HIGH_CRITICAL for v in violations):
        return "fail"

    low_score = (
        quality["instruction_following_score"] < 3
        or quality["task_success_score"] < 3
    )
    failed_constraint = any(
        cr["status"] == "fail" for cr in quality.get("constraint_results", [])
    )
    if low_score or failed_constraint:
        return "review"

    return "pass"


def run_validation(*, silent: bool = False) -> bool:
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)
        if not silent:
            print(f"  [FAIL] {msg}")

    def ok(msg: str) -> None:
        if not silent:
            print(f"  [ OK ] {msg}")

    if not silent:
        print("\n=== Artifact Validation ===\n")

    # ── Check 1: Required artifacts exist ────────────────────────────────
    for path in _REQUIRED_FILES:
        if path.exists():
            ok(f"Exists: {path}")
        else:
            fail(f"Missing artifact: {path}")

    # ── Check 2: JSON files are valid ────────────────────────────────────
    tasks_data = _load_json(BASE / "parsed_tasks" / "tasks.json")
    quality_data = _load_json(BASE / "quality_eval.json")
    safety_data = _load_json(BASE / "safety_review.json")
    retry_data = _load_json(BASE / "retry_instructions.json")
    summary_data = _load_json(BASE / "summary.json")
    consistency_data = _load_json(BASE / "consistency_check.json")

    for name, data in [
        ("parsed_tasks/tasks.json", tasks_data),
        ("quality_eval.json", quality_data),
        ("safety_review.json", safety_data),
        ("retry_instructions.json", retry_data),
        ("summary.json", summary_data),
        ("consistency_check.json", consistency_data),
    ]:
        if data is None:
            fail(f"Invalid or unreadable JSON: {name}")
        else:
            ok(f"Valid JSON: {name}")

    if any(d is None for d in [tasks_data, quality_data, safety_data, retry_data, summary_data]):
        if not silent:
            print("\nCannot continue: one or more required JSON files are missing or invalid.")
        return False

    task_ids: set[str] = {t["task_id"] for t in tasks_data}

    # ── Check 3: parsed_tasks/tasks.json exists before LLM outputs ───────
    parsed_mtime = (BASE / "parsed_tasks" / "tasks.json").stat().st_mtime
    for llm_file in ["quality_eval.json", "safety_review.json", "retry_instructions.json"]:
        p = BASE / llm_file
        if p.exists() and p.stat().st_mtime < parsed_mtime:
            fail(f"Ordering violation: {llm_file} is older than parsed_tasks/tasks.json")
        else:
            ok(f"File ordering OK: {llm_file}")

    # ── Check 4 & 5: llm_calls.jsonl — stage records + scores_included ───
    stage1_ids: set[str] = set()
    stage2_ids: set[str] = set()
    stage3_ids: set[str] = set()
    stage3_with_scores: list[str] = []

    jsonl_path = BASE / "llm_calls.jsonl"
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                fail(f"Invalid JSONL line: {line[:80]}")
                continue
            stage = entry.get("stage")
            tid = entry.get("task_id")
            if stage == "quality_eval" and tid:
                stage1_ids.add(tid)
            elif stage == "safety_review" and tid:
                stage2_ids.add(tid)
            elif stage == "retry_gen" and tid:
                stage3_ids.add(tid)
                if entry.get("scores_included", True):
                    stage3_with_scores.append(tid)

    for tid in task_ids:
        if tid in stage1_ids:
            ok(f"Stage 1 log: {tid}")
        else:
            fail(f"Missing Stage 1 (quality_eval) log for {tid}")
        if tid in stage2_ids:
            ok(f"Stage 2 log: {tid}")
        else:
            fail(f"Missing Stage 2 (safety_review) log for {tid}")
        if tid in stage3_ids:
            ok(f"Stage 3 log: {tid}")
        else:
            fail(f"Missing Stage 3 (retry_gen) log for {tid}")

    if stage3_with_scores:
        fail(f"Stage 3 records have scores_included=true: {stage3_with_scores}")
    else:
        ok("All Stage 3 records have scores_included=false")

    # ── Check 6: summary.json has a row for every task ───────────────────
    summary_ids: set[str] = {row["task_id"] for row in summary_data}
    for tid in task_ids:
        if tid in summary_ids:
            ok(f"Summary row exists: {tid}")
        else:
            fail(f"summary.json missing row for {tid}")

    # ── Check 7: Verdicts match deterministic rules ───────────────────────
    quality_by_id = {r["task_id"]: r for r in quality_data}
    safety_by_id = {r["task_id"]: r for r in safety_data}

    for row in summary_data:
        tid = row["task_id"]
        if tid not in quality_by_id or tid not in safety_by_id:
            fail(f"Cannot verify verdict for {tid}: missing quality or safety data")
            continue
        expected = _recompute_verdict(quality_by_id[tid], safety_by_id[tid])
        actual = row["final_verdict"]
        if actual == expected:
            ok(f"Verdict correct: {tid} → {actual}")
        else:
            fail(f"Verdict mismatch {tid}: stored='{actual}', recomputed='{expected}'")

    # ── Check 8: Quality scores are integers in 0–5 ──────────────────────
    for q in quality_data:
        for field in ["instruction_following_score", "task_success_score"]:
            val = q.get(field)
            if isinstance(val, int) and 0 <= val <= 5:
                ok(f"Score valid: {q['task_id']}.{field} = {val}")
            else:
                fail(f"Invalid score: {q['task_id']}.{field} = {val!r} (must be int 0–5)")

    # ── Check 9: retry_instructions.json has entry for every task ────────
    retry_ids: set[str] = {r["task_id"] for r in retry_data}
    for tid in task_ids:
        if tid in retry_ids:
            ok(f"Retry entry exists: {tid}")
        else:
            fail(f"retry_instructions.json missing entry for {tid}")

    # ── Check 10: Evidence quotes present AND verbatim for failures/violations
    # Build a lookup of task_id → model_output for substring verification
    model_output_by_id: dict[str, str] = {
        t["task_id"]: t["model_output"] for t in tasks_data
    }
    # Sentinel allowed for absent content in constraint checks (not for violations)
    _ABSENT_SENTINEL = "[Not present in output]"

    for s in safety_data:
        model_out = model_output_by_id.get(s["task_id"], "")
        for v in s.get("violations", []):
            evidence = (v.get("evidence") or "").strip()
            if not evidence:
                fail(f"Missing evidence for violation: {s['task_id']} / {v.get('category')}")
            elif evidence not in model_out:
                fail(
                    f"Violation evidence is not a verbatim quote from model output: "
                    f"{s['task_id']} / {v.get('category')} → \"{evidence[:60]}\""
                )
            else:
                ok(f"Violation evidence verbatim: {s['task_id']} / {v.get('category')}")

    for q in quality_data:
        model_out = model_output_by_id.get(q["task_id"], "")
        for cr in q.get("constraint_results", []):
            status = cr.get("status")
            evidence = (cr.get("evidence") or "").strip()
            if status == "fail":
                if not evidence:
                    fail(f"Failed constraint missing evidence: {q['task_id']} / {cr.get('constraint')}")
                elif evidence == _ABSENT_SENTINEL:
                    ok(f"Constraint evidence (absent sentinel): {q['task_id']} / {cr.get('constraint')}")
                elif evidence not in model_out:
                    fail(
                        f"Failed constraint evidence is not verbatim from model output: "
                        f"{q['task_id']} / {cr.get('constraint')} → \"{evidence[:60]}\""
                    )
                else:
                    ok(f"Constraint evidence verbatim: {q['task_id']} / {cr.get('constraint')}")
            elif status == "partial":
                if evidence and (evidence == _ABSENT_SENTINEL or evidence in model_out):
                    ok(f"Constraint evidence verbatim: {q['task_id']} / {cr.get('constraint')}")

    # ── Result ────────────────────────────────────────────────────────────
    if not silent:
        print(f"\n{'PASSED' if not errors else 'FAILED'} — {len(errors)} error(s)\n")

    return len(errors) == 0


if __name__ == "__main__":
    passed = run_validation(silent=False)
    sys.exit(0 if passed else 1)
