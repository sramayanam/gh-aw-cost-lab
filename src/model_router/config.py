from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qwen_base_url: str | None = Field(default=None, alias="QWEN_BASE_URL")
    qwen_api_key: SecretStr | None = Field(default=None, alias="QWEN_API_KEY")
    qwen_model: str = Field(default="qwen", alias="QWEN_MODEL")
    qwen_hourly_cost_usd: float = Field(
        default=0,
        ge=0,
        alias="QWEN_HOURLY_COST_USD",
    )

    azure_openai_endpoint: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_ENDPOINT",
    )
    azure_openai_api_key: SecretStr | None = Field(
        default=None,
        alias="AZURE_OPENAI_API_KEY",
    )
    azure_openai_api_version: str = Field(
        default="2025-04-01-preview",
        alias="AZURE_OPENAI_API_VERSION",
    )
    azure_openai_deployment: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_DEPLOYMENT",
    )
    azure_openai_judge_deployment: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_JUDGE_DEPLOYMENT",
    )
    azure_input_cost_per_million: float = Field(
        default=0,
        ge=0,
        alias="AZURE_INPUT_COST_PER_MILLION",
    )
    azure_output_cost_per_million: float = Field(
        default=0,
        ge=0,
        alias="AZURE_OUTPUT_COST_PER_MILLION",
    )

    router_data_dir: Path = Field(default=Path("data"), alias="ROUTER_DATA_DIR")
    router_store_content: bool = Field(
        default=False,
        alias="ROUTER_STORE_CONTENT",
    )
    router_api_key: SecretStr | None = Field(
        default=None,
        alias="ROUTER_API_KEY",
    )

    @property
    def qwen_ready(self) -> bool:
        return self.qwen_base_url is not None

    @property
    def azure_ready(self) -> bool:
        return all(
            (
                self.azure_openai_endpoint,
                self.azure_openai_api_key,
                self.azure_openai_deployment,
            )
        )

    @property
    def judge_ready(self) -> bool:
        return self.azure_ready and self.azure_openai_judge_deployment is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
