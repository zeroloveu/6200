import json
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utc_now, server_default=func.now())

    created_polls: Mapped[list["Poll"]] = relationship(back_populates="creator")
    votes: Mapped[list["PollVote"]] = relationship(back_populates="voter")


class Poll(Base):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic: Mapped[str] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    options_json: Mapped[str] = mapped_column(Text)
    allowed_user_ids_json: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chain_contract_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chain_deploy_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chain_network_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chain_chain_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chain_deploy_block: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chain_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chain_deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=naive_utc_now,
        onupdate=naive_utc_now,
        server_default=func.now()
    )

    creator: Mapped["User"] = relationship(back_populates="created_polls")
    votes: Mapped[list["PollVote"]] = relationship(back_populates="poll", cascade="all, delete-orphan")

    def get_options(self) -> list[str]:
        return json.loads(self.options_json or "[]")

    def set_options(self, options: list[str]) -> None:
        self.options_json = json.dumps(options, ensure_ascii=False)

    def get_allowed_user_ids(self) -> list[int]:
        return json.loads(self.allowed_user_ids_json or "[]")

    def set_allowed_user_ids(self, user_ids: list[int]) -> None:
        self.allowed_user_ids_json = json.dumps(user_ids)


class PollVote(Base):
    __tablename__ = "poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "voter_id", name="uq_poll_vote_voter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), index=True)
    voter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    selected_option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    chain_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utc_now, server_default=func.now())

    poll: Mapped["Poll"] = relationship(back_populates="votes")
    voter: Mapped["User"] = relationship(back_populates="votes")
