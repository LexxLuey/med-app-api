import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL")
    redis_url: str = os.getenv("REDIS_URL")
    secret_key: str = os.getenv("SECRET_KEY")
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    tenant_id: str = os.getenv("TENANT_ID", "default")
    paid_amount_threshold: float = float(os.getenv("PAID_AMOUNT_THRESHOLD", 1000))
    approval_number_min: int = int(os.getenv("APPROVAL_NUMBER_MIN", 100000))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    port: int = int(os.getenv("PORT", 8000))

    class Config:
        env_file = ".env"


settings = Settings()
