import re

CAPS_WHITELIST = {"ΕΝΩΠΙΟΝ", "ΔΙΚΑΣΤΗΡΙΟΥ", "ΜΟΝΟΜΕΛΟΥΣ", "ΠΟΛΥΜΕΛΟΥΣ",
                  "ΠΡΩΤΟΔΙΚΕΙΟΥ", "ΕΙΡΗΝΟΔΙΚΕΙΟΥ", "ΕΦΕΤΕΙΟΥ", "ΑΘΗΝΩΝ",
                  "ΓΙΑ", "ΤΟΥΣ", "ΛΟΓΟΥΣ", "ΑΥΤΟΥΣ", "ΑΝΑΚΟΠΗ", "ΑΓΩΓΗ"}

_GREEK_NAME = re.compile(
    r"\b[Α-ΩΆΈΉΊΌΎΏ][α-ωάέήίόύώϊϋΐΰ]+(?:\s+[Α-ΩΆΈΉΊΌΎΏ][α-ωάέήίόύώϊϋΐΰ]+)+\b")

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ΠΟΣΟ", re.compile(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:€|ευρώ)")),
    ("ΗΜΕΡΟΜΗΝΙΑ", re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b")),
    ("ΑΜΚΑ", re.compile(r"\b\d{11}\b")),
    ("ΑΦΜ", re.compile(r"\b\d{9}\b")),
    ("ΑΡΙΘΜΟΣ", re.compile(r"\b\d+/\d{4}\b")),
]


def scrub(text: str) -> tuple[str, list[dict]]:
    reps: list[dict] = []
    out = text
    for label, pat in PATTERNS:
        for m in pat.finditer(out):
            reps.append({"type": label, "original": m.group(0)})
        out = pat.sub(f"⟨{label}⟩", out)

    def _name(m: re.Match) -> str:
        if all(w.upper() in CAPS_WHITELIST for w in m.group(0).split()):
            return m.group(0)
        reps.append({"type": "ΟΝΟΜΑ", "original": m.group(0)})
        return "⟨ΟΝΟΜΑ⟩"

    out = _GREEK_NAME.sub(_name, out)
    return out, reps
