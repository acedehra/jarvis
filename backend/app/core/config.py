import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    API_KEY: Optional[str] = None
    API_KEY_FILE_PATH: str = "data/.api_key"
    API_KEY_AUTH_ENABLED: bool = True
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/chatbot"
    MCP_CONFIG_PATH: str = "mcp_config.json"

    # LangSmith Observability
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "jarvis-backend"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # Telegram Configurations
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # Default model configuration
    DEFAULT_PROVIDER: str = "gemini"
    DEFAULT_GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-latest"
    DEFAULT_OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    # User Timezone Configuration
    USER_TIMEZONE: str = "America/New_York"

    # Checkpoint Retention & Auto-Cleanup
    CHECKPOINT_RETENTION_HOURS: int = 24
    CHECKPOINT_CLEANUP_INTERVAL_HOURS: int = 1

    # CORS Allowed Origins
    CORS_ORIGINS: list[str] = ["*"]

    # Configure Pydantic to read environment files
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parent.parent.parent / ".env",
            Path(__file__).resolve().parent.parent.parent.parent / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

# Export LangChain variables to environment so standard langchain client picks them up automatically
for key, value in settings.model_dump().items():
    if key.startswith("LANGCHAIN_") and value is not None:
        os.environ[key] = str(value)

