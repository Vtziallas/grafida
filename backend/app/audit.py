from app.models import AuditLog


def audit(db, user_id: int, action: str, entity_type: str = "",
          entity_id: int | None = None, detail: dict | None = None):
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail or {}))
