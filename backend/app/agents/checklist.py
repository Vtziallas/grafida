from app.models import ChecklistItem

ATTESTATION = ("Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος. "
               "Το AI βοηθά — ο δικηγόρος αποφασίζει.")


def run_checks(db, doc, case_file, content, dtype, extra_findings=None):
    db.query(ChecklistItem).filter_by(document_id=doc.id).delete()
    items = list(extra_findings or [])
    if content.count("[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"):
        items.append({"severity": "red", "source_agent": "citation",
                      "text": f"{content.count('[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ')} νομικές αναφορές "
                              "χωρίς πηγή — απαιτείται επαλήθευση.",
                      "anchor_quote": "[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"})
    for t in (dtype.checklist_template or []):
        items.append({"severity": "yellow", "source_agent": "procedure",
                      "text": t, "anchor_quote": ""})
    items.append({"severity": "red", "source_agent": "attestation",
                  "text": ATTESTATION, "anchor_quote": ""})
    for it in items:
        db.add(ChecklistItem(owner_user_id=doc.owner_user_id, document_id=doc.id,
                             **it))
