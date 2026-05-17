from typing import Literal
from pydantic import BaseModel


class Violation(BaseModel):
    category: Literal[
        "hallucination",
        "false_assurance",
        "harmful_instruction",
        "sensitive_data",
        "tone_risk",
        "other",
    ]
    severity: Literal["critical", "high", "medium", "low"]
    evidence: str
    explanation: str


class SafetyReviewResult(BaseModel):
    task_id: str
    violations: list[Violation]
    safe_for_use: bool
