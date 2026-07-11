from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://grafida:grafida@db:5432/grafida"
    jwt_secret: str = "dev-secret"
    jwt_expires_minutes: int = 480
    storage_dir: str = "/data/uploads"
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ai_chat_model: str = "qwen2.5:7b"
    ai_embed_model: str = "bge-m3"
    cors_origin: str = "http://localhost:3000"
    seed_email: str = "owner@example.com"
    seed_password: str = "grafida123"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email: str = ""


settings = Settings()
