from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    test_database_url: str = ""
    redis_url: str
    jwt_secret: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    frontend_url: str = "http://localhost:5173"
    session_secret: str = "dev-session-secret"
    public_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
