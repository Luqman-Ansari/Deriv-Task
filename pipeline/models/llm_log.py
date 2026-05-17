from typing import Optional
from pydantic import BaseModel


class LLMCallLog(BaseModel):
    stage: str
    task_id: Optional[str] = None
    timestamp: str
    provider: str
    model: str
    prompt_hash: str
    input_artifacts: list[str]
    output_artifact: str
    scores_included: bool
    policy_files_used: list[str]
