from sqlalchemy import text as sql

from app.models import SearchIndex


def _snippet(t: str, q: str, width: int = 200) -> str:
    low, pos = t.lower(), -1
    for w in q.lower().split():
        pos = low.find(w)
        if pos >= 0:
            break
    start = max(0, pos - width // 2) if pos >= 0 else 0
    return t[start:start + width]


def hybrid_search(db, user_id: int, q: str, provider, limit: int = 10) -> list[dict]:
    fts = db.execute(sql(
        "SELECT id FROM search_index WHERE owner_user_id=:u "
        "AND tsv @@ plainto_tsquery('greek', :q) "
        "ORDER BY ts_rank(tsv, plainto_tsquery('greek', :q)) DESC LIMIT 20"),
        {"u": user_id, "q": q}).scalars().all()
    qvec = provider.embed([q])[0]
    vec = [r.id for r in db.query(SearchIndex)
           .filter(SearchIndex.owner_user_id == user_id,
                   SearchIndex.embedding.isnot(None))
           .order_by(SearchIndex.embedding.cosine_distance(qvec)).limit(20)]
    scores: dict[int, float] = {}
    for ranked in (fts, vec):
        for rank, rid in enumerate(ranked):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (60 + rank)
    top = sorted(scores, key=lambda k: scores[k], reverse=True)[:limit]
    rows = ({r.id: r for r in
             db.query(SearchIndex).filter(SearchIndex.id.in_(top))} if top else {})
    fts_set = set(fts)
    out = []
    for rid in top:
        r = rows.get(rid)
        if not r:
            continue
        out.append({"kind": r.kind, "ref_id": r.ref_id, "case_id": r.case_id,
                    "snippet": _snippet(r.text, q), "score": scores[rid],
                    "_fts": rid in fts_set})
    # keyword-only relevance guard: if nothing matches by keyword anywhere,
    # semantic-only noise is dropped
    if not fts and not any(any(w in i["snippet"].lower() for w in q.lower().split())
                           for i in out):
        return []
    out.sort(key=lambda i: (0 if i["_fts"] else 1, -i["score"]))
    for i in out:
        i.pop("_fts")
    return out
