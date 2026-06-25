
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings


engine = create_engine(
    settings.mysql_url,
    echo=settings.sqlalchemy_echo,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=True,
    autocommit=False,
    expire_on_commit=False,
)

def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
