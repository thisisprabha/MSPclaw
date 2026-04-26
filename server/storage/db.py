"""SQLAlchemy engine + session factory.

v0.1 uses SQLite. Switch to Postgres by changing the URL — schema is portable.
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.storage.sqlite_schema import Base

_engine = None
_Session = None


def init_db(url: str = "sqlite:///mspclaw.db") -> None:
    global _engine, _Session
    _engine = create_engine(url, future=True)
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


@contextmanager
def get_session():
    if _Session is None:
        raise RuntimeError("call init_db() first")
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
