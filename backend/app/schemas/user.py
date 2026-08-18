from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError(
            "Пароль слишком короткий. Минимум 8 символов."
        )
    has_lower = any(ch.islower() for ch in value)
    has_upper = any(ch.isupper() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    if not (has_lower and has_upper and has_digit):
        missing: list[str] = []
        if not has_upper:
            missing.append("заглавную букву")
        if not has_lower:
            missing.append("строчную букву")
        if not has_digit:
            missing.append("цифру")
        raise ValueError(
            "Пароль должен содержать "
            + ", ".join(missing)
            + ". Пример: Password123"
        )
    return value


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str
    grade: int | None = Field(default=None, ge=7, le=9)
    invite_code: str | None = Field(default=None, min_length=6, max_length=16)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    grade: int | None
    paid_tariff_id: int | None = None
    paid_tariff_code: str | None = None
    paid_tariff_title: str | None = None
    paid_tariff_expires_at: datetime | None = None
    connected_group_title: str | None = None
    connected_teacher_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    school: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=4000)
    settings_json: str | None = Field(default=None, max_length=20000)


class UserProfileRead(BaseModel):
    id: int
    user_id: int
    avatar_url: str | None
    school: str | None
    city: str | None
    bio: str | None
    settings_json: str | None

    model_config = ConfigDict(from_attributes=True)


class UserMeUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    grade: int | None = Field(default=None, ge=7, le=9)


class UserTariffUpdate(BaseModel):
    tariff_code: str


class TeacherConnectRequest(BaseModel):
    invite_code: str = Field(min_length=6, max_length=16)


class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class LeaderboardEntry(BaseModel):
    user_id: int
    name: str
    grade: int | None = None
    rating: float
    average_percent: int
    attempts_finished: int
    rank: int


class LeaderboardSummary(BaseModel):
    total_students: int
    current_user_rank: int
    current_user_rating: float
    top: list[LeaderboardEntry]


class UserLeaderboardRead(BaseModel):
    overall: LeaderboardSummary
    weekly: LeaderboardSummary
