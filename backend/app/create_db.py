from app.db import Base, engine
import app.models  # noqa: F401

Base.metadata.create_all(engine)
