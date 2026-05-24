from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Smart Logistics API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    postgres_db: str = "smart_logistics"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_host_port: int | None = None
    postgres_sslmode: str = "prefer"
    mapbox_api_key: str = ""
    openai_api_key: str = ""
    gps_ingest_token: str = ""
    ml_train_token: str = ""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        use_host_port = self.postgres_host in {"localhost", "127.0.0.1"} and self.postgres_host_port
        port = use_host_port or self.postgres_port
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{port}/{self.postgres_db}?sslmode={self.postgres_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
