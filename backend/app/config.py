from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    agent_engine_resource_name: str
    frontend_url: str = "http://localhost:3000"
    port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
