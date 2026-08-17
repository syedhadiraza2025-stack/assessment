from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
import os

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/voice_agent"


def normalize_database_url(database_url: str) -> str:
    """Return a SQLAlchemy-compatible Postgres URL."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))

if DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite is disabled for this project. Set DATABASE_URL to a PostgreSQL "
        "connection string before starting the API or LiveKit worker."
    )


def safe_database_url() -> str:
    """Database URL for logs without exposing credentials."""
    url = make_url(DATABASE_URL)
    if url.password:
        url = url.set(password="***")
    return str(url)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_database() -> None:
    """Create all managed tables on the configured PostgreSQL database."""
    import models  # noqa: F401 - registers model classes with Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
