from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# pool_pre_ping: Neon closes connections that sit idle (and suspends compute
# when the project is idle), so a pooled connection can be dead by the time
# it is reused -- an ingestion script hit "SSL connection has been closed
# unexpectedly" on its first query after a long download. Pinging first
# replaces a dead connection instead of failing the request.
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
