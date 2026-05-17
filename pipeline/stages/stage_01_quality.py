"""
Stage 1 — Quality Evaluation.

One LLM call per task. Assesses usefulness and instruction-following only.
Results are written to quality_eval.json after every task so partial progress
is preserved if the run is interrupted.
"""
import json
import pathlib

import settings
from pipeline.llm_logger import log_call
from pipeline.models.quality import QualityEvalResult
from pipeline.models.task import ParsedTask
from pipeline.prompts import quality_prompt
from pipeline.utils import run_with_retry

_agent = settings.make_agent(QualityEvalResult)


def run(tasks: list[ParsedTask], output_path: pathlib.Path) -> list[QualityEvalResult]:
    results: list[QualityEvalResult] = []

    for task in tasks:
        print(f"    Quality eval: {task.task_id} ...", end=" ", flush=True)
        prompt = quality_prompt.build(task)
        result = _agent.run_sync(prompt)

        # Pin task_id to prevent LLM from returning a different value
        qr = QualityEvalResult(**{**result.output.model_dump(), "task_id": task.task_id})
        results.append(qr)

        log_call(
            stage="quality_eval",
            task_id=task.task_id,
            prompt=prompt,
            input_artifacts=["parsed_tasks/tasks.json"],
            output_artifact="quality_eval.json",
            scores_included=True,
            policy_files_used=[],
        )

        # Write after each task so partial results survive interruptions
        output_path.write_text(
            json.dumps([r.model_dump() for r in results], indent=2),
            encoding="utf-8",
        )
        print("done")

    return results
