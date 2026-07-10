from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import COOKIE, get_current_user
from app.auth.security import create_token, hash_password, verify_password
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/auth")


class Creds(BaseModel):
    email: str
    password: str
    full_name: str = ""


@router.post("/register")
def register(body: Creds, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Το email χρησιμοποιείται ήδη")
    u = User(email=body.email, password_hash=hash_password(body.password),
             full_name=body.full_name)
    db.add(u); db.commit()
    return {"id": u.id}


@router.post("/login")
def login(body: Creds, response: Response, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Λάθος στοιχεία")
    response.set_cookie(COOKIE, create_token(u.id), httponly=True,
                        samesite="lax", max_age=8 * 3600)
    audit(db, u.id, "auth.login"); db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name}
