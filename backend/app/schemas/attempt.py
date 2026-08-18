from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal


class AttemptCreate(BaseModel):
    mode: Literal["practice", "variant"]
    variant_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_mode_and_variant(self):
        if self.mode == "variant" and self.variant_id is None:
            raise ValueError("variant_id is required for variant attempts")
        if self.mode == "practice" and self.variant_id is not None:
            raise ValueError("variant_id is not allowed for practice attempts")
        return self


class AttemptAnswerCreate(BaseModel):
    task_id: int = Field(gt=0)
    user_answer: str = Field(min_length=1, max_length=4000)


class AttemptAnswerAccepted(BaseModel):
    task_id: int
    saved: bool = True


class AttemptAnswerResultRead(BaseModel):
    task_id: int
    user_answer: str | None = None
    is_correct: bool
    correct_answer: str
    explanation: str | None = None


class AttemptResultRead(BaseModel):
    attempt_id: int
    answers: list[AttemptAnswerResultRead]


class AttemptRead(BaseModel):
    id: int
    user_id: int
    variant_id: int | None
    variant_title: str | None = None
    mode: str
    started_at: datetime
    finished_at: datetime | None
    spent_seconds: int = 0
    score: int
    max_score: int
    percent: int
    grade_mark: int | None

    model_config = ConfigDict(from_attributes=True)


class AttemptStatsRead(BaseModel):
    attempts_total: int
    solved_tasks_total: int
    average_percent: int
    average_grade: float
    variant_average_percent: int
    predicted_exam_grade: float
    theory_completion_percent: int
    variant_stability_percent: int
    readiness_vpr_percent: int


class WeekActivityDayRead(BaseModel):
    date: str
    attempts: int
    tasks: int
    total: int


class WeekActivityRead(BaseModel):
    days: list[WeekActivityDayRead]


class RecommendedTopicRead(BaseModel):
    category_id: int | None
    theory_slug: str | None = None
    title: str
    progress_percent: int
    exam_type: str | None


class RecommendedTopicsRead(BaseModel):
    items: list[RecommendedTopicRead]

