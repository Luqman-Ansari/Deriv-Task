"""Prompt template for Stage 1: Quality Evaluation."""
import json

from pipeline.models.task import ParsedTask


def build(task: ParsedTask) -> str:
    constraints_json = json.dumps(task.expected_constraints, indent=2)
    return f"""\
You are a quality evaluator for AI-generated customer support responses.
Assess instruction-following and task quality ONLY. Do not comment on safety.

Do NOT explain your reasoning. Fill every output field directly and concisely.

---

TASK ID   : {task.task_id}
TASK TYPE : {task.task_type}

USER INPUT:
{task.user_input}

MODEL OUTPUT:
{task.model_output}

OUTPUT METADATA:
- Word count  : {task.word_count}
- Char count  : {task.char_count}
- Is JSON     : {task.is_json}
- Is empty    : {task.is_empty}

EXPECTED CONSTRAINTS:
{constraints_json}

---

EVALUATION RULES

For every constraint in the list above, produce one constraint_result with:

  constraint : exact string from the list above, copied verbatim
  status     : one of "pass", "fail", "partial"
  evidence   : a non-null string — choose the RIGHT rule below:
               • status = "pass"   → copy the exact phrase from MODEL OUTPUT that satisfies the constraint
               • status = "fail"   → if something wrong IS present: copy the exact offending phrase from MODEL OUTPUT
                                     if required content is ABSENT:  use the literal string "[Not present in output]"
               • status = "partial"→ copy the exact phrase that partially meets the constraint
  rationale  : one sentence explaining your ruling — do not repeat the evidence

SCORES (integers 0–5, no decimals):
  instruction_following_score : how precisely the model obeyed the task instructions
  task_success_score          : how well the overall task objective was achieved
  5=perfect 4=minor issues 3=acceptable 2=significant gaps 1=mostly wrong 0=failed

strengths : list of short strings — what the model did correctly (empty list if nothing)
failures  : list of short strings — what the model got wrong or omitted (empty list if nothing)

IMPORTANT:
- evidence must never be null. Use "[Not present in output]" when content is absent.
- Do not invent quotes. Every evidence string must appear verbatim in MODEL OUTPUT
  or be the exact literal "[Not present in output]".
- task_id must be exactly: {task.task_id}
"""
