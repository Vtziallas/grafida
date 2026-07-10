from app.audit import audit
from app.db import SessionLocal
from app import models as m


def test_entities_roundtrip():
    db = SessionLocal()
    u = m.User(email="a@a.gr", password_hash="x", full_name="A")
    db.add(u); db.commit()
    c = m.Client(owner_user_id=u.id, name="Πελάτης ΑΕ", afm="123456789")
    db.add(c); db.commit()
    case = m.Case(owner_user_id=u.id, client_id=c.id, title="Ανακοπή Χ", category="civil")
    db.add(case); db.commit()
    audit(db, u.id, "case.create", "case", case.id)
    db.commit()
    assert db.query(m.AuditLog).count() == 1
    db.close()
