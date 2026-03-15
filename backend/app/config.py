from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate .env: check CWD first, then walk up to project root
def _find_env_file() -> str:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return ".env"  # let pydantic-settings fail gracefully


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS credentials
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"

    # Nova Act
    NOVA_ACT_API_KEY: str = ""

    # Server ports
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000


settings = Settings()
