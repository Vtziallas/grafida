import json

from app.agents.prompts import load_prompt


def build_profile(provider, scrubbed_samples: list[str]) -> dict:
    system, _v = load_prompt("style_analyze")
    joined = "\n\n=== ΔΕΙΓΜΑ ===\n\n".join(scrubbed_samples)
    raw = provider.generate(system=system, user=joined, json_mode=True)
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError:
        spec = {}
    bank = spec.get("phrase_bank", {})
    for key, phrases in list(bank.items()):
        kept = []
        for ph in phrases or []:
            hits = sum(1 for s in scrubbed_samples if ph.lower() in s.lower())
            if hits >= 2:
                kept.append(ph)
        bank[key] = kept
    spec["phrase_bank"] = bank
    return spec
