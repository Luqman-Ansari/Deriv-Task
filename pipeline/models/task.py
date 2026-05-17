from pydantic import BaseModel


class Task(BaseModel):
    task_id: str
    task_type: str
    user_input: str
    model_output: str
    expected_constraints: list[str]


class ParsedTask(Task):
    char_count: int
    word_count: int
    is_json: bool
    is_empty: bool


class TaskSuite(BaseModel):
    tasks: list[Task]
