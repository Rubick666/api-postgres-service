from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orders_db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()