"""
Stage 0 — Deterministic Task Parsing.

Reads task_suite.json, enriches each Task with structural metadata,
and writes parsed_tasks/tasks.json. No LLM calls are made here.
"""
import json
import pathlib

from pipeline.models.task import ParsedTask, TaskSuite


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def run(suite_path: pathlib.Path, output_dir: pathlib.Path) -> list[ParsedTask]:
    raw = json.loads(suite_path.read_text(encoding="utf-8"))
    suite = TaskSuite(**raw)

    parsed: list[ParsedTask] = []
    for task in suite.tasks:
        stripped = task.model_output.strip()
        parsed.append(
            ParsedTask(
                **task.model_dump(),
                char_count=len(stripped),
                word_count=len(stripped.split()) if stripped else 0,
                is_json=_is_valid_json(stripped),
                is_empty=len(stripped) == 0,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tasks.json").write_text(
        json.dumps([t.model_dump() for t in parsed], indent=2),
        encoding="utf-8",
    )
    return parsed
