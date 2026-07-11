from sqlalchemy import text

from app.db import Base, engine
import app.models  # noqa: F401

Base.metadata.create_all(engine)

# additive column migrations for existing databases (create_all does not ALTER)
with engine.begin() as c:
    c.execute(text(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS id_number VARCHAR(20)"))
    c.execute(text(
        "ALTER TABLE deadlines ADD COLUMN IF NOT EXISTS alerts_sent JSON "
        "DEFAULT '[]'::json"))
