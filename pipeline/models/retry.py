from pydantic import BaseModel


class RetryInstruction(BaseModel):
    task_id: str
    retry_needed: bool
    improved_prompt: str
    expected_improvements: list[str]
    notes: str
