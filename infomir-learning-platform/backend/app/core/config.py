from functools import lru_cache

from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./backend/infomir.sqlite3"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"
    project_name: str = "Infomir API"
    debug: bool = True
    app_env: str = "development"
    cors_origins: Annotated[list[str], NoDecode] = ["http://127.0.0.1:8000", "http://localhost:8000"]
    cors_allow_credentials: bool = True
    allowed_hosts: Annotated[list[str], NoDecode] = ["127.0.0.1", "localhost", "testserver"]
    admin_hosts: Annotated[list[str], NoDecode] = ["admin.localhost", "admin.127.0.0.1"]
    admin_session_expire_minutes: int = 30
    teacher_commission_percent: int = 20
    payment_provider: str = "manual"
    manual_payment_instructions: str = "Свяжитесь с администратором и сообщите номер платёжной заявки."
    enable_dev_payment_confirmation: bool = False
    trust_proxy_headers: bool = False
    max_request_body_bytes: int = 1_048_576

    @field_validator("debug", mode="before")
    @classmethod
    def _normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"0", "false", "no", "off", "release"}:
            return False
        return True

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value):
        if value is None:
            return "development"
        normalized = str(value).strip().lower()
        if normalized in {"prod", "production"}:
            return "production"
        if normalized in {"stage", "staging"}:
            return "staging"
        return "development"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_cors_origins(cls, value):
        if isinstance(value, list):
            return value
        if value is None:
            return ["http://127.0.0.1:8000", "http://localhost:8000"]
        raw = str(value).strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @field_validator("allowed_hosts", "admin_hosts", mode="before")
    @classmethod
    def _normalize_host_lists(cls, value):
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        if value is None:
            return []
        return [item.strip().lower() for item in str(value).split(",") if item.strip()]

    @model_validator(mode="after")
    def _validate_secure_settings(self):
        if self.app_env == "production":
            if self.debug:
                raise ValueError("DEBUG must be disabled in production")
            if not self.secret_key or len(self.secret_key) < 32 or self.secret_key in {"change-me", "replace-with-strong-random-secret"}:
                raise ValueError("SECRET_KEY must contain at least 32 non-placeholder characters in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS cannot contain '*' when APP_ENV=production")
            if not self.allowed_hosts or not self.admin_hosts:
                raise ValueError("ALLOWED_HOSTS and ADMIN_HOSTS must be configured in production")
            if self.enable_dev_payment_confirmation:
                raise ValueError("ENABLE_DEV_PAYMENT_CONFIRMATION must be disabled in production")
            if self.algorithm != "HS256":
                raise ValueError("ALGORITHM must be HS256 in production")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("DATABASE_URL must use PostgreSQL in production")
            if self.payment_provider == "manual" and (
                self.manual_payment_instructions.startswith("Свяжитесь с администратором")
                or "example.com" in self.manual_payment_instructions.lower()
            ):
                raise ValueError("MANUAL_PAYMENT_INSTRUCTIONS must contain the real payment instructions in production")
        if not 0 <= self.teacher_commission_percent <= 100:
            raise ValueError("TEACHER_COMMISSION_PERCENT must be between 0 and 100")
        if self.max_request_body_bytes < 1024:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be at least 1024")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
