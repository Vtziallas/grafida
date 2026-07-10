import hashlib
import json
import re

from app.ai.base import EMBED_DIM

MOCK_RESPONSES: dict[str, str] = {
    "intake_extract": json.dumps({
        "parties": [{"name": "Ιωάννης Παπαδόπουλος", "role": "ανακόπτων",
                     "source_quote": "Ιωάννης Παπαδόπουλος", "confidence": 0.95}],
        "dates": [{"value": "2026-06-01", "description": "επίδοση διαταγής",
                   "source_quote": "1/6/2026", "confidence": 0.9}],
        "amounts": [{"value": "14500.00", "description": "απαίτηση",
                     "source_quote": "14.500,00", "confidence": 0.9}],
        "claims": [{"value": "ακύρωση διαταγής πληρωμής",
                    "description": "κύριο αίτημα",
                    "source_quote": "διαταγή πληρωμής", "confidence": 0.8}],
    }, ensure_ascii=False),
    "style_analyze": json.dumps({
        "structure": [{"section": "Ιστορικό", "order": 1, "share": 0.4},
                      {"section": "Λόγοι", "order": 2, "share": 0.4},
                      {"section": "Αίτημα", "order": 3, "share": 0.2}],
        "phrase_bank": {"openings": ["ΕΝΩΠΙΟΝ ΤΟΥ"], "transitions": ["Επειδή"],
                        "closers": ["ΓΙΑ ΤΟΥΣ ΛΟΓΟΥΣ ΑΥΤΟΥΣ"],
                        "favorite_expressions": ["όλως αβασίμως"]},
        "tone": {"formality": 5, "avg_sentence_length": 38},
        "formatting": {"numbering": "arabic", "headings": "caps"},
    }, ensure_ascii=False),
    "draft": ("ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ\n\nΑΝΑΚΟΠΗ\n\nΤου Ιωάννη Παπαδόπουλου.\n\n"
              "Επειδή η προσβαλλόμενη διαταγή πληρωμής ποσού 14.500,00 ευρώ "
              "[πηγή: σχετικό 1] εκδόθηκε [ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ — δεν ανακτήθηκε πηγή] "
              "παρανόμως.\n\nΓΙΑ ΤΟΥΣ ΛΟΓΟΥΣ ΑΥΤΟΥΣ ζητώ την ακύρωσή της."),
}


class MockProvider:
    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str:
        m = re.search(r"AGENT: (\w+)", system)
        key = m.group(1) if m else ""
        return MOCK_RESPONSES.get(key, "{}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.md5(t.encode()).digest()
            out.append([(h[i % 16] + i) % 100 / 100.0 for i in range(EMBED_DIM)])
        return out
