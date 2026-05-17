"""
Stage 3 — Retry Instruction Generation.

One LLM call per task.

SCORE ISOLATION GUARANTEE
--------------------------
This stage accepts list[ParsedTask] — a type that carries ONLY structural
metadata (char_count, word_count, is_json, is_empty) on top of the base Task
fields. It never receives QualityEvalResult, SafetyReviewResult, scores,
verdicts, or severity ratings.

The prompt builder (retry_prompt.build) is typed to accept Task and only reads:
  task_id, task_type, user_input, model_output, expected_constraints.

scores_included is hardcoded False in the log_call below and cannot be True.
"""
import json
import pathlib

import settings
from pipeline.llm_logger import log_call
from pipeline.models.retry import RetryInstruction
from pipeline.models.task import ParsedTask
from pipeline.prompts import retry_prompt
from pipeline.utils import run_with_retry


_agent = settings.make_agent(RetryInstruction)


def run(tasks: list[ParsedTask], output_path: pathlib.Path) -> list[RetryInstruction]:
    results: list[RetryInstruction] = []

    for task in tasks:
        print(f"    Retry gen: {task.task_id} ...", end=" ", flush=True)

        # retry_prompt.build is typed Task -> str; scores are never in scope
        prompt = retry_prompt.build(task)
        result = _agent.run_sync(prompt)

        ri = RetryInstruction(**{**result.output.model_dump(), "task_id": task.task_id})
        results.append(ri)

        log_call(
            stage="retry_gen",
            task_id=task.task_id,
            prompt=prompt,
            input_artifacts=["parsed_tasks/tasks.json"],
            output_artifact="retry_instructions.json",
            scores_included=False,  # ENFORCED: always False for Stage 3
            policy_files_used=[],
        )

        output_path.write_text(
            json.dumps([r.model_dump() for r in results], indent=2),
            encoding="utf-8",
        )
        print("done")

    return results
