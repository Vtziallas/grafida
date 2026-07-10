from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.db import get_db
from app.models import User

COOKIE = "grafida_token"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    tok = request.cookies.get(COOKIE)
    if not tok:
        raise HTTPException(401, "Απαιτείται σύνδεση")
    try:
        uid = decode_token(tok)
    except Exception:
        raise HTTPException(401, "Μη έγκυρη συνεδρία")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Μη έγκυρη συνεδρία")
    return user
