from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "sqlite:///./test.db"
    SECRET_KEY: str = "changeme"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # GHL Integration
    GHL_LOCATION_ID: str = "BZlud2FcXjl5CoBAs4rU"
    GHL_LOCATION_ACCESS_TOKEN: str = ""
    GHL_API_URL: str = "https://services.leadconnectorhq.com"

    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False


settings = Settings()


def get_settings() -> Settings:
    return settings
