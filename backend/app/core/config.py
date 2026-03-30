from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_SECRET_KEY: str
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    QB_CLIENT_ID: str
    QB_CLIENT_SECRET: str
    QB_REDIRECT_URI: str
    QB_ENVIRONMENT: str = "sandbox"

    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    REPORT_FROM_EMAIL: str
    REPORT_TO_EMAIL: str

    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    class Config:
        env_file = ".env"


settings = Settings()
