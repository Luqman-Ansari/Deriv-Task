from typing import Literal
from pydantic import BaseModel


class TaskSummary(BaseModel):
    task_id: str
    instruction_following_score: int
    task_success_score: int
    violation_count: int
    highest_violation_severity: Literal["none", "low", "medium", "high", "critical"]
    final_verdict: Literal["pass", "review", "fail"]
