from pydantic import BaseModel


class ConsistencyIssue(BaseModel):
    task_ids: list[str]
    issue: str
    why_inconsistent: str
    suggested_recheck: str


class ConsistencyCheckResult(BaseModel):
    issues: list[ConsistencyIssue]
