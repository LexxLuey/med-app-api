import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL")
    redis_url: str = os.getenv("REDIS_URL")
    secret_key: str = os.getenv("SECRET_KEY")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY")
    tenant_id: str = os.getenv("TENANT_ID", "default")
    paid_amount_threshold: float = float(os.getenv("PAID_AMOUNT_THRESHOLD", 1000))
    approval_number_min: int = int(os.getenv("APPROVAL_NUMBER_MIN", 100000))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    port: int = int(os.getenv("PORT", 8000))

    # CORS Configuration (12-Factor compliant)
    cors_allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "True").lower() == "true"
    cors_allow_methods: str = os.getenv("CORS_ALLOW_METHODS", "*")
    cors_allow_headers: str = os.getenv("CORS_ALLOW_HEADERS", "*")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string"""
        origins = self.cors_allow_origins.strip()
        if origins == "*":
            return ["*"]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    @property
    def cors_methods_list(self) -> list[str]:
        """Parse CORS methods from comma-separated string"""
        methods = self.cors_allow_methods.strip()
        if methods == "*":
            return ["*"]
        return [method.strip() for method in methods.split(",") if method.strip()]

    @property
    def cors_headers_list(self) -> list[str]:
        """Parse CORS headers from comma-separated string"""
        headers = self.cors_allow_headers.strip()
        if headers == "*":
            return ["*"]
        return [header.strip() for header in headers.split(",") if header.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
