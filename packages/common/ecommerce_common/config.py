from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "unknown-service"
    PORT: int = 8000

    # Mongo
    MONGO_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "test_db"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    EXCHANGE_NAME: str = "ecommerce.events"
    DLX_EXCHANGE_NAME: str = "ecommerce.dlx"

    # Security
    JWT_SECRET_KEY: str = "supersecretjwtkeychangeinproductionminimum32characterslong"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
