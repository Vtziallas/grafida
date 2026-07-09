from app.auth.security import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import DocumentType, User

ANAKOPI_CHECKLIST = [
    "Ελέγξτε την προθεσμία άσκησης της ανακοπής (προς επαλήθευση με ΚΠολΔ).",
    "Ελέγξτε την αρμοδιότητα του δικαστηρίου.",
    "Ελέγξτε ότι όλα τα σχετικά αναφέρονται και επισυνάπτονται.",
    "Ελέγξτε γραμμάτιο προείσπραξης και λοιπά παράβολα (προς επαλήθευση).",
]


def run():
    db = SessionLocal()
    if not db.query(User).filter_by(email=settings.seed_email).first():
        db.add(User(email=settings.seed_email,
                    password_hash=hash_password(settings.seed_password),
                    full_name="Δικηγόρος"))
    for name, checklist in [
        ("Ανακοπή κατά διαταγής πληρωμής", ANAKOPI_CHECKLIST),
        ("Γενικό δικόγραφο", []),
    ]:
        if not db.query(DocumentType).filter_by(name_gr=name).first():
            db.add(DocumentType(name_gr=name, checklist_template=checklist))
    db.commit(); db.close()


if __name__ == "__main__":
    run()
