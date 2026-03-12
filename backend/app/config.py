from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "sqlite:///./test.db"
    SECRET_KEY: str = "changeme"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False


settings = Settings()
