import json
import re

from app.agents.prompts import load_prompt


def build_case_file(db, case) -> dict:
    from app.models import CaseFact, Evidence, Party
    parties = db.query(Party).filter_by(case_id=case.id, confirmed_by_lawyer=True).all()
    facts = db.query(CaseFact).filter_by(case_id=case.id, confirmed_by_lawyer=True).all()
    evidence = db.query(Evidence).filter_by(case_id=case.id).all()
    return {
        "title": case.title, "court": case.court_name, "category": case.category,
        "parties": [{"name": p.name, "role": p.role} for p in parties],
        "facts": [{"kind": f.kind, "value": f.value, "description": f.description,
                   "source_quote": f.source_quote} for f in facts],
        "evidence": [{"exhibit_number": e.exhibit_number,
                      "description": e.description} for e in evidence],
        "conflicts": [f.id for f in facts if f.conflict_group is not None],
    }


def run_draft(provider, case_file: dict, profile_spec: dict,
              exemplars: list[str], doc_type_name: str) -> tuple[str, dict]:
    system, version = load_prompt("draft")
    user = (f"ΤΥΠΟΣ ΕΓΓΡΑΦΟΥ: {doc_type_name}\n\n"
            f"CASE_FILE:\n{json.dumps(case_file, ensure_ascii=False, indent=1)}\n\n"
            f"STYLE_PROFILE:\n{json.dumps(profile_spec, ensure_ascii=False, indent=1)}\n\n"
            + "".join(f"EXEMPLAR (ανωνυμοποιημένο):\n{e[:4000]}\n\n" for e in exemplars))
    content = provider.generate(system=system, user=user)
    report = {
        "unverified_refs": content.count("[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"),
        "gaps": content.count("[ΚΕΝΟ"),
        "exemplar_count": len(exemplars),
        "confirmed_fact_count": len(case_file["facts"]),
        "prompt_version": version,
    }
    return content, report


def leak_scan(draft: str, case_file: dict) -> list[dict]:
    known = json.dumps(case_file, ensure_ascii=False)
    findings = []
    for num in set(re.findall(r"\b\d{9}\b|\b\d{11}\b", draft)):
        if num not in known:
            findings.append({"severity": "red", "source_agent": "leak_scan",
                             "text": f"Ο αριθμός {num} δεν υπάρχει στον φάκελο — "
                                     "πιθανή διαρροή από παλαιό έγγραφο.",
                             "anchor_quote": num})
    return findings


def overlap_scan(draft: str, sample_texts: list[str]) -> list[dict]:
    words = draft.split()
    findings, seen = [], set()
    for i in range(0, max(0, len(words) - 12), 4):
        span = " ".join(words[i:i + 12])
        if len(span) < 40 or span in seen:
            continue
        for s in sample_texts:
            if span in s:
                seen.add(span)
                findings.append({"severity": "yellow", "source_agent": "overlap_scan",
                                 "text": "Απόσπασμα ταυτίζεται αυτολεξεί με παλαιό "
                                         "δείγμα — ελέγξτε για μεταφορά περιεχομένου.",
                                 "anchor_quote": span[:120]})
                break
    return findings
