"""Appends one JSON line per LLM call to llm_calls.jsonl."""
import hashlib
import pathlib
from datetime import datetime, timezone

from pipeline.models.llm_log import LLMCallLog
import settings

JSONL_PATH = pathlib.Path("llm_calls.jsonl")


def init_log_file() -> None:
    """Truncate at the start of each run to ensure a clean, replayable log."""
    JSONL_PATH.write_text("", encoding="utf-8")


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def log_call(
    *,
    stage: str,
    task_id: str | None,
    prompt: str,
    input_artifacts: list[str],
    output_artifact: str,
    scores_included: bool,
    policy_files_used: list[str],
) -> None:
    entry = LLMCallLog(
        stage=stage,
        task_id=task_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=settings.PROVIDER,
        model=settings.MODEL_NAME,
        prompt_hash=_hash_prompt(prompt),
        input_artifacts=input_artifacts,
        output_artifact=output_artifact,
        scores_included=scores_included,
        policy_files_used=policy_files_used,
    )
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
