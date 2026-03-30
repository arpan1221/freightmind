from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str
    bypass_cache: bool = False
    database_url: str = "sqlite:///./freightmind.db"
    cache_dir: str = "./cache"
    analytics_model: str = "meta-llama/llama-3.3-70b-instruct"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
