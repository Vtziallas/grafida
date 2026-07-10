import httpx

from app.ai.base import EMBED_DIM
from app.config import settings


class AIError(Exception):
    pass


class OllamaProvider:
    def __init__(self):
        self.base = settings.ollama_base_url.rstrip("/")

    def _post(self, path: str, payload: dict) -> dict:
        last = None
        for _ in range(3):
            try:
                r = httpx.post(f"{self.base}{path}", json=payload, timeout=300)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001
                last = e
        raise AIError(f"Αποτυχία επικοινωνίας με το τοπικό μοντέλο AI: {last}")

    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload = {"model": settings.ai_chat_model, "stream": False,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]}
        if json_mode:
            payload["format"] = "json"
        return self._post("/api/chat", payload)["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/api/embed",
                          {"model": settings.ai_embed_model, "input": texts})
        vecs = data["embeddings"]
        if vecs and len(vecs[0]) != EMBED_DIM:
            raise AIError(f"Λάθος διάσταση embeddings: {len(vecs[0])}")
        return vecs
