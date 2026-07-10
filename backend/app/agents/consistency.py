import re

from rapidfuzz import fuzz


def _gr_amount(value: str) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value or ""
    whole, dec = f"{n:,.2f}".split(".")
    return whole.replace(",", ".") + "," + dec


AMOUNT_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+,\d{2}\b|\b\d+,\d{2}\b")
EXHIBIT_RE = re.compile(r"σχετικ[όο]\s+(\d+)", re.IGNORECASE)


def check_consistency(case_file: dict, draft: str) -> list[dict]:
    findings = []
    cf_amounts = {_gr_amount(f["value"]) for f in case_file.get("facts", [])
                  if f.get("kind") == "amount" and f.get("value")}
    for amt in cf_amounts:
        if amt and amt not in draft:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Το ποσό {amt} του φακέλου δεν εμφανίζεται στο προσχέδιο.",
                "anchor_quote": amt})
    for amt in set(AMOUNT_RE.findall(draft)):
        if amt not in cf_amounts:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Το ποσό {amt} του προσχεδίου δεν αντιστοιχεί σε "
                        "επιβεβαιωμένο στοιχείο του φακέλου.",
                "anchor_quote": amt})
    draft_words = draft.split()
    for p in case_file.get("parties", []):
        surname = (p.get("name") or "").split()[-1] if p.get("name") else ""
        if len(surname) > 3 and not any(
                fuzz.ratio(surname.lower(), w.strip(".,;:()").lower()) >= 85
                for w in draft_words):
            findings.append({"severity": "yellow", "source_agent": "consistency",
                "text": f"Ο διάδικος «{p['name']}» δεν εντοπίστηκε στο προσχέδιο.",
                "anchor_quote": p["name"]})
    known_exhibits = {e["exhibit_number"] for e in case_file.get("evidence", [])}
    for num in {int(n) for n in EXHIBIT_RE.findall(draft)}:
        if num not in known_exhibits:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Αναφέρεται «σχετικό {num}» που δεν υπάρχει στον φάκελο.",
                "anchor_quote": f"σχετικό {num}"})
    return findings
