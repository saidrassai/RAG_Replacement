from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .orm import Base


@dataclass(slots=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)


def build_database(database_url: str) -> Database:
    engine = create_engine(database_url, future=True)
    return Database(engine=engine, session_factory=sessionmaker(engine, expire_on_commit=False))
