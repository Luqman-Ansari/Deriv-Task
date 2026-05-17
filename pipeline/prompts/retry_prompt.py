"""
Prompt template for Stage 3: Retry Instruction Generation.

IMPORTANT: This module accepts only pipeline.models.task.Task objects.
It must never receive QualityEvalResult, SafetyReviewResult, or any object
that carries scores, verdicts, or severity ratings. That constraint is
enforced by the function signature below.
"""
import json

from pipeline.models.task import Task


def build(task: Task) -> str:
    """Build a retry prompt using ONLY task-level fields — never scores or verdicts."""
    constraints_json = json.dumps(task.expected_constraints, indent=2)
    return f"""\
You are a prompt improvement specialist for an AI customer support task runner.

Do NOT explain your reasoning. Fill every output field directly and concisely.

---

TASK ID   : {task.task_id}
TASK TYPE : {task.task_type}

ORIGINAL USER INPUT:
{task.user_input}

MODEL OUTPUT (the response under review):
{task.model_output}

EXPECTED CONSTRAINTS:
{constraints_json}

---

INSTRUCTIONS

Compare MODEL OUTPUT against each constraint in EXPECTED CONSTRAINTS.

Decide:
  retry_needed : true  — if the model failed or partially met one or more constraints
               : false — if the model met all constraints

If retry_needed is true:
  improved_prompt      : a complete, standalone rewrite of ORIGINAL USER INPUT that an
                         engineer can use directly as the new prompt. It must be specific
                         enough to prevent the exact failures you identified. Do not
                         reference scores, ratings, or severity. Do not say "improve X" —
                         write the actual improved instruction.
  expected_improvements: list of short, concrete strings describing what will be better
                         (e.g. "avoids inventing facts", "stays under 40 words")
  notes                : one sentence of additional context for the engineer, or empty string

If retry_needed is false:
  improved_prompt      : "" (empty string)
  expected_improvements: [] (empty list)
  notes                : "" (empty string)

RULES:
- Do not reference numeric scores, pass/fail verdicts, or severity ratings.
- improved_prompt must be a complete usable instruction, not a description of changes.
- task_id must be exactly: {task.task_id}
"""
