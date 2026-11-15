"""Persistence model. Every tenant-owned row carries `org_id`; queries must filter on it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


_PK = lambda: mapped_column(String(36), primary_key=True, default=_id)  # noqa: E731
_TS = lambda: mapped_column(DateTime(timezone=True), default=_now, nullable=False)  # noqa: E731


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = _PK()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    created_at: Mapped[datetime] = _TS()


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = _PK()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _TS()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),)
    id: Mapped[str] = _PK()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")  # owner|admin|member|viewer
    created_at: Mapped[datetime] = _TS()


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_watchlists_org_name"),)
    id: Mapped[str] = _PK()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = _TS()
    items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", order_by="WatchlistItem.position")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_items_symbol"),)
    id: Mapped[str] = _PK()
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = _TS()
    watchlist: Mapped[Watchlist] = relationship(back_populates="items")


class SavedScan(Base):
    __tablename__ = "saved_scans"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_saved_scans_org_name"),)
    id: Mapped[str] = _PK()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    universe: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = _TS()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = _PK()
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    org_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
