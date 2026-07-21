from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://itr_user:password@localhost:5432/itr_family",
)
DATA_DIR = Path(os.getenv("ITR_DATA_DIR", "./private_data")).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Base(DeclarativeBase):
    pass


def get_engine():
    """Create database engine with error handling."""
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except OperationalError as e:
        if "could not connect" in str(e).lower() or "authentication failed" in str(e).lower():
            print("\n" + "="*70)
            print("DATABASE CONNECTION ERROR")
            print("="*70)
            print(f"\n❌ Cannot connect to PostgreSQL database:")
            print(f"   URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
            print(f"\n   Error: {e}")
            print(f"\n📋 Please ensure:")
            print(f"   1. PostgreSQL 18+ is installed and running")
            print(f"   2. .env file has correct DATABASE_URL")
            print(f"   3. Database user and password are correct")
            print(f"\n🔧 Run setup again:")
            print(f"   python setup.py")
            print("="*70 + "\n")
            sys.exit(1)
        raise


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
