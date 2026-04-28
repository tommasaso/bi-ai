from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.config import settings


def get_engine():
    return create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def get_inspector():
    engine = get_engine()
    return inspect(engine)


def table_exists(table_name: str) -> bool:
    inspector = get_inspector()
    return table_name in inspector.get_table_names()
