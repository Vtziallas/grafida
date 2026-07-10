from app.models import SearchIndex


def index_text(db, user_id: int, kind: str, ref_id: int,
               case_id: int | None, text: str, provider):
    if not text or not text.strip():
        return
    row = db.query(SearchIndex).filter_by(kind=kind, ref_id=ref_id).first()
    emb = provider.embed([text[:2000]])[0]
    if row:
        row.text, row.embedding, row.case_id = text, emb, case_id
    else:
        db.add(SearchIndex(owner_user_id=user_id, kind=kind, ref_id=ref_id,
                           case_id=case_id, text=text, embedding=emb))
