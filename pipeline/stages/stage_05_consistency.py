"""
Stage 5 — Cross-Task Consistency Check.

A single LLM call that reviews all quality evaluations side by side
and flags obvious scoring inconsistencies.
"""
import json
import pathlib

import settings
from pipeline.llm_logger import log_call
from pipeline.models.consistency import ConsistencyCheckResult, ConsistencyIssue
from pipeline.models.quality import QualityEvalResult
from pipeline.prompts import consistency_prompt
from pipeline.utils import run_with_retry


_agent = settings.make_agent(ConsistencyCheckResult)


def run(
    quality_results: list[QualityEvalResult],
    output_path: pathlib.Path,
) -> list[ConsistencyIssue]:
    print("    Consistency check ...", end=" ", flush=True)
    prompt = consistency_prompt.build(quality_results)
    result = _agent.run_sync(prompt)
    issues = result.output.issues

    log_call(
        stage="consistency_check",
        task_id=None,
        prompt=prompt,
        input_artifacts=["quality_eval.json"],
        output_artifact="consistency_check.json",
        scores_included=True,
        policy_files_used=[],
    )

    output_path.write_text(
        json.dumps([i.model_dump() for i in issues], indent=2),
        encoding="utf-8",
    )
    print(f"done ({len(issues)} issue(s) found)")
    return issues
