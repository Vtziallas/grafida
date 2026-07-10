import os
import re

DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(name: str) -> tuple[str, int]:
    with open(os.path.join(DIR, f"{name}.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"<!-- version: (\d+) -->", text)
    return text, int(m.group(1)) if m else 0
