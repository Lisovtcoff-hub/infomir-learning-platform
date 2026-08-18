from pydantic import BaseModel, ConfigDict


class VariantTaskRead(BaseModel):
    task_id: int
    sort_order: int
    points: int

    model_config = ConfigDict(from_attributes=True)


class VariantRead(BaseModel):
    id: int
    title: str
    exam_type: str
    subject: str
    grade: int | None
    description: str | None
    time_limit_minutes: int | None

    model_config = ConfigDict(from_attributes=True)


class VariantDetailRead(VariantRead):
    variant_tasks: list[VariantTaskRead]
