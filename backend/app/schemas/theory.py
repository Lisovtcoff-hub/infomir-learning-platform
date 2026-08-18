from pydantic import BaseModel, ConfigDict


class TheoryTopicRead(BaseModel):
    id: int
    category_id: int | None = None
    category_title: str | None = None
    category_sort_order: int | None = None
    grade: int | None
    subject: str | None = None
    slug: str
    title: str
    content_json: list[dict]

    model_config = ConfigDict(from_attributes=True)


class TheoryProgressMarkResponse(BaseModel):
    ok: bool


class TheoryProgressStatsRead(BaseModel):
    completed_topics: int
    total_topics: int
