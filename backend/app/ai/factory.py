from app.ai.base import AIProvider
from app.ai.mock import MockProvider
from app.ai.ollama import OllamaProvider
from app.config import settings


def get_provider() -> AIProvider:
    return MockProvider() if settings.ai_provider == "mock" else OllamaProvider()
