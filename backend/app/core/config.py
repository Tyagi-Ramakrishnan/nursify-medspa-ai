from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_SECRET_KEY: str = "dev-secret-change-in-production"
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379"

    QB_CLIENT_ID: str = ""
    QB_CLIENT_SECRET: str = ""
    QB_REDIRECT_URI: str = "http://localhost:8000/api/v1/quickbooks/callback"
    QB_ENVIRONMENT: str = "sandbox"

    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    REPORT_FROM_EMAIL: str = ""
    REPORT_TO_EMAIL: str = ""

    ADMIN_EMAIL: str = "admin@nursify.com"
    ADMIN_PASSWORD: str = "changeme"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
