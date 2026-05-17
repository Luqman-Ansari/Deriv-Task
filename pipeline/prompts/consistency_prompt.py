"""Prompt template for the cross-task consistency check."""
import json

from pipeline.models.quality import QualityEvalResult


def build(quality_results: list[QualityEvalResult]) -> str:
    scorecards = []
    for q in quality_results:
        scorecards.append({
            "task_id": q.task_id,
            "task_type": q.task_id,  # included for cross-type comparison
            "instruction_following_score": q.instruction_following_score,
            "task_success_score": q.task_success_score,
            "constraint_statuses": {
                cr.constraint: cr.status for cr in q.constraint_results
            },
            "strengths": q.strengths,
            "failures": q.failures,
        })

    return f"""\
You are an evaluation quality auditor reviewing scoring consistency across multiple tasks.

Do NOT explain your reasoning. Fill every output field directly and concisely.

---

SCORECARDS:
{json.dumps(scorecards, indent=2)}

---

INSTRUCTIONS

Review the scorecards above and identify GENUINE inconsistencies. Only flag an issue
if it is clearly contradictory — not just different tasks having different scores.

Look for:
  - A constraint evaluated as "pass" for one task and "fail" for another task where
    the model outputs are equivalent in quality
  - Two tasks of the same type receiving very different scores despite similar outputs
  - Scoring bias: all tasks scored identically regardless of output quality differences
  - A task with all constraints passing but a low score, or all failing but a high score

For each real inconsistency found:
  task_ids         : list of the task IDs involved (minimum 2)
  issue            : a short label, e.g. "score_mismatch", "contradictory_constraint"
  why_inconsistent : one sentence explaining the specific contradiction
  suggested_recheck: one sentence describing exactly what the evaluator should re-examine

RULES:
- Different task types having different scores is NOT an inconsistency.
- Only flag issues you can point to with specific evidence from the scorecards.
- Return an empty issues list if there are no genuine inconsistencies.
"""
