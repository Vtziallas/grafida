import json

from rapidfuzz import fuzz

from app.agents.prompts import load_prompt

KEYS = ["parties", "dates", "amounts", "claims"]


def run_extraction(provider, source_text: str) -> dict:
    system, _v = load_prompt("intake_extract")
    raw = provider.generate(system=system, user=source_text, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {k: [] for k in KEYS}
    out: dict = {}
    for key in KEYS:
        items = []
        for it in data.get(key, []) or []:
            quote = (it.get("source_quote") or "").strip()
            ok = bool(quote) and fuzz.partial_ratio(quote, source_text) >= 90
            if not ok:
                if key != "parties":
                    it["value"] = None
                it["confidence"] = 0.0
                it["description"] = (it.get("description", "") +
                                     " [δεν επαληθεύτηκε στο κείμενο]").strip()
            items.append(it)
        out[key] = items
    return out
