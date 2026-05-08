from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    service_name: str = Field(
        default="OpenAI Agent SDK Dashboard",
        validation_alias=AliasChoices("DASHBOARD_SERVICE_NAME"),
    )
    redis_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "DASHBOARD_REDIS_URL"),
    )
    redis_channel: str = Field(
        default="agent:traces",
        validation_alias=AliasChoices("DASHBOARD_REDIS_CHANNEL"),
    )
    auth_token: SecretStr = Field(
        default=SecretStr("dev-dashboard-token"),
        validation_alias=AliasChoices("DASHBOARD_AUTH_TOKEN"),
    )
    developer_auth_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHBOARD_DEVELOPER_AUTH_TOKEN"),
    )
    replay_buffer_size: int = Field(
        default=50,
        ge=1,
        le=500,
        validation_alias=AliasChoices("DASHBOARD_REPLAY_BUFFER_SIZE"),
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8090"],
        validation_alias=AliasChoices("DASHBOARD_CORS_ORIGINS"),
    )
    config_path: Path = Field(
        default=Path("dashboard_service/config/default.dashboard.json"),
        validation_alias=AliasChoices("DASHBOARD_CONFIG_PATH"),
    )
    enable_redis_subscriber: bool = Field(
        default=True,
        validation_alias=AliasChoices("DASHBOARD_ENABLE_REDIS_SUBSCRIBER"),
    )
    enable_dev_tools: bool = Field(
        default=False,
        validation_alias=AliasChoices("DASHBOARD_ENABLE_DEV_TOOLS"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def viewer_token(self) -> str:
        return self.auth_token.get_secret_value()

    @property
    def developer_token(self) -> str | None:
        if self.developer_auth_token is None:
            return None
        token = self.developer_auth_token.get_secret_value().strip()
        return token or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
