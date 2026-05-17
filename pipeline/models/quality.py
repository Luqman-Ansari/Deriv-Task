from typing import Literal, Optional
from pydantic import BaseModel, Field


class ConstraintResult(BaseModel):
    constraint: str
    status: Literal["pass", "fail", "partial"]
    evidence: Optional[str] = None
    rationale: str


class QualityEvalResult(BaseModel):
    task_id: str
    instruction_following_score: int = Field(ge=0, le=5)
    task_success_score: int = Field(ge=0, le=5)
    constraint_results: list[ConstraintResult]
    strengths: list[str]
    failures: list[str]
