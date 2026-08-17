#!/usr/bin/env python3
"""PostgreSQL schema utility for the assessment project.

Examples:
  python manage_db.py check
  python manage_db.py init
  python manage_db.py reset --confirm DROP_POSTGRES_TABLES
"""

import argparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import models  # noqa: F401 - registers all SQLAlchemy models with Base.metadata
from database import Base, engine, init_database, safe_database_url


def check_db() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database connection failed for {safe_database_url()}: {exc}") from exc
    print(f"Database connection OK: {safe_database_url()}")


def init_db() -> None:
    init_database()
    print(f"Tables created/verified on: {safe_database_url()}")


def reset_db(confirm: str | None) -> None:
    if confirm != "DROP_POSTGRES_TABLES":
        raise SystemExit(
            "Refusing to drop tables. Re-run with: "
            "python manage_db.py reset --confirm DROP_POSTGRES_TABLES"
        )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print(f"All managed tables dropped and recreated on: {safe_database_url()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage PostgreSQL tables.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Verify the configured database connection.")
    subparsers.add_parser("init", help="Create missing tables.")

    reset_parser = subparsers.add_parser("reset", help="Drop and recreate all managed tables.")
    reset_parser.add_argument("--confirm", help="Must be exactly DROP_POSTGRES_TABLES.")

    args = parser.parse_args()

    if args.command == "check":
        check_db()
    elif args.command == "init":
        init_db()
    elif args.command == "reset":
        reset_db(args.confirm)


if __name__ == "__main__":
    main()
