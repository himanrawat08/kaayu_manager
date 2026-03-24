import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_WEAK_SECRETS = {
    "change-me-to-a-long-random-string-in-production",
    "replace-with-a-long-random-string-at-least-64-chars",
    "",
}


class Settings(BaseSettings):
    # SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    FROM_NAME: str = "Kaayu Studio"
    FROM_EMAIL: str = ""

    # App
    ENVIRONMENT: str = "development"   # 'development' or 'production'
    SECRET_KEY: str = "change-me-to-a-long-random-string-in-production"
    BASE_URL: str = "http://localhost:8001"
    DATABASE_URL: str = "sqlite:///./studio_manager.db"
    ROOT_PATH: str = ""   # e.g. "/pms" when served under a subpath

    # Supabase Storage
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "uploads"

    # Integration
    EMAIL_TOOL_DB_PATH: str = "../email-automation/email_automation.db"
    EMAIL_TOOL_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


settings = Settings()

# Warn loudly if running with a weak secret key
if settings.SECRET_KEY in _WEAK_SECRETS:
    logger.warning(
        "WARNING: SECRET_KEY is not set or is using the default placeholder. "
        "Generate a strong key: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

if settings.is_production and settings.SECRET_KEY in _WEAK_SECRETS:
    raise RuntimeError(
        "Cannot start in production mode with a weak SECRET_KEY. "
        "Set a strong SECRET_KEY in your .env file."
    )
