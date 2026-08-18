from pydantic import BaseModel, ConfigDict


class TariffRead(BaseModel):
    id: int
    code: str
    title: str
    price: float
    duration_days: int
    description: str | None
    features_json: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
