from typing import Protocol

EMBED_DIM = 1024


class AIProvider(Protocol):
    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
