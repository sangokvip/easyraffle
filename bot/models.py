from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LotteryStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    COMPLETED = "completed"


class GroupConfig(Base):
    __tablename__ = "group_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lottery(Base):
    __tablename__ = "lotteries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winners_count: Mapped[int] = mapped_column(Integer, default=1)
    join_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[LotteryStatus] = mapped_column(Enum(LotteryStatus), default=LotteryStatus.OPEN)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    strategy: Mapped[str] = mapped_column(String(64), default="random")

    participants: Mapped[list[Participant]] = relationship(
        "Participant", back_populates="lottery", cascade="all, delete-orphan"
    )
    winners: Mapped[list[Winner]] = relationship("Winner", back_populates="lottery", cascade="all, delete-orphan")
    preset_winners: Mapped[list[PresetWinner]] = relationship(
        "PresetWinner", back_populates="lottery", cascade="all, delete-orphan"
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lottery_id: Mapped[int] = mapped_column(ForeignKey("lotteries.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lottery: Mapped[Lottery] = relationship("Lottery", back_populates="participants")


class PresetWinner(Base):
    __tablename__ = "preset_winners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lottery_id: Mapped[int] = mapped_column(ForeignKey("lotteries.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    lottery: Mapped[Lottery] = relationship("Lottery", back_populates="preset_winners")


class Winner(Base):
    __tablename__ = "winners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lottery_id: Mapped[int] = mapped_column(ForeignKey("lotteries.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    picked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    preset: Mapped[bool] = mapped_column(Boolean, default=False)

    lottery: Mapped[Lottery] = relationship("Lottery", back_populates="winners")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
