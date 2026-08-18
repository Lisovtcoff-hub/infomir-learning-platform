from pydantic import BaseModel, ConfigDict


class TaskOptionRead(BaseModel):
    id: int
    option_text: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class TaskRead(BaseModel):
    id: int
    category_id: int | None
    category_title: str | None = None
    category_sort_order: int | None = None
    grade: int | None
    exam_type: str | None
    subject: str | None = None
    title: str
    question: str
    hint: str | None = None
    difficulty: str | None
    options: list[TaskOptionRead]

    model_config = ConfigDict(from_attributes=True)


class TaskCheckRequest(BaseModel):
    user_answer: str


class TaskCheckResponse(BaseModel):
    task_id: int
    is_correct: bool
    correct_answer: str
    explanation: str | None = None


class TaskCategoryRead(BaseModel):
    id: int
    code: str
    title: str
    exam_type: str
    subject: str
    grade: int | None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
