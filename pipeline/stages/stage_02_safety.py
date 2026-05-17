"""
Stage 2 — Safety / Guardrail Review.

One LLM call per task. Focuses on safety, policy, and trust risks only.
Policy files from the policies/ directory are injected into each prompt when present.
"""
import json
import pathlib

import settings
from pipeline.llm_logger import log_call
from pipeline.models.safety import SafetyReviewResult
from pipeline.models.task import ParsedTask
from pipeline.prompts import safety_prompt
from pipeline.utils import run_with_retry


_agent = settings.make_agent(SafetyReviewResult)


def _load_policies(policies_dir: pathlib.Path) -> tuple[str, list[str]]:
    """Return (combined policy text, list of file paths used)."""
    if not policies_dir.exists():
        return "", []

    files = sorted(
        p for p in policies_dir.iterdir()
        if p.suffix in {".txt", ".md"} and p.stat().st_size > 0
    )
    if not files:
        return "", []

    sections = [f"=== {p.name} ===\n{p.read_text(encoding='utf-8')}" for p in files]
    return "\n\n".join(sections), [str(p) for p in files]


def run(
    tasks: list[ParsedTask],
    output_path: pathlib.Path,
    policies_dir: pathlib.Path,
) -> list[SafetyReviewResult]:
    policy_text, policy_files = _load_policies(policies_dir)
    if policy_files:
        print(f"    Policy files loaded: {[pathlib.Path(p).name for p in policy_files]}")

    results: list[SafetyReviewResult] = []

    for task in tasks:
        print(f"    Safety review: {task.task_id} ...", end=" ", flush=True)
        prompt = safety_prompt.build(task, policy_text)
        result = _agent.run_sync(prompt)

        sr = SafetyReviewResult(**{**result.output.model_dump(), "task_id": task.task_id})
        results.append(sr)

        log_call(
            stage="safety_review",
            task_id=task.task_id,
            prompt=prompt,
            input_artifacts=["parsed_tasks/tasks.json"],
            output_artifact="safety_review.json",
            scores_included=False,
            policy_files_used=policy_files,
        )

        output_path.write_text(
            json.dumps([r.model_dump() for r in results], indent=2),
            encoding="utf-8",
        )
        print("done")

    return results
