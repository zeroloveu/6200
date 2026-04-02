import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import inspect, text


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ[key] = value


load_local_env()


DATABASE_URL = os.getenv("APP_DATABASE_URL", "sqlite:///./fastapi_vote.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_legacy_columns()


def ensure_legacy_columns() -> None:
    inspector = inspect(engine)

    user_columns = {column["name"] for column in inspector.get_columns("users")} if inspector.has_table("users") else set()
    poll_columns = {column["name"] for column in inspector.get_columns("polls")} if inspector.has_table("polls") else set()
    vote_columns = {column["name"] for column in inspector.get_columns("poll_votes")} if inspector.has_table("poll_votes") else set()

    alter_statements: list[str] = []

    if "wallet_address" not in user_columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN wallet_address VARCHAR(128)")

    if "chain_contract_address" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_contract_address VARCHAR(128)")
    if "chain_deploy_tx_hash" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_deploy_tx_hash VARCHAR(128)")
    if "chain_network_name" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_network_name VARCHAR(64)")
    if "chain_chain_id" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_chain_id VARCHAR(32)")
    if "chain_deploy_block" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_deploy_block INTEGER")
    if "chain_error" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_error TEXT")
    if "chain_deployed_at" not in poll_columns:
        alter_statements.append("ALTER TABLE polls ADD COLUMN chain_deployed_at DATETIME")

    if "chain_tx_hash" not in vote_columns:
        alter_statements.append("ALTER TABLE poll_votes ADD COLUMN chain_tx_hash VARCHAR(128)")

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
