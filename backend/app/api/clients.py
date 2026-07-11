from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Case, Client, User

router = APIRouter(prefix="/api/clients")


class ClientIn(BaseModel):
    name: str
    afm: str | None = None
    id_number: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str = ""


@router.post("")
def create(body: ClientIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = Client(owner_user_id=user.id, **body.model_dump())
    db.add(c); db.commit()
    return {"id": c.id}


@router.get("")
def list_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Client).filter_by(owner_user_id=user.id).order_by(Client.name).all()
    return [{"id": c.id, "name": c.name, "afm": c.afm, "phone": c.phone,
             "email": c.email} for c in rows]


@router.get("/{client_id}")
def detail(client_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(id=client_id, owner_user_id=user.id).first()
    if not c:
        raise HTTPException(404)
    cases = db.query(Case).filter_by(client_id=c.id, owner_user_id=user.id).all()
    return {"id": c.id, "name": c.name, "afm": c.afm, "id_number": c.id_number,
            "email": c.email, "phone": c.phone, "notes": c.notes,
            "cases": [{"id": k.id, "title": k.title, "status": k.status,
                       "court_name": k.court_name, "next_action": k.next_action}
                      for k in cases]}
