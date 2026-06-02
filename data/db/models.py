"""SQLAlchemy 模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Activity(Base):
    """活动时间表（与解包 activity_table / GUI 活动筛选对齐）。"""

    __tablename__ = "activities"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OperatorSupplementary(Base):
    """干员 B 站 / 手工补充字段（与 generate_template 中 value dict 对齐）。"""

    __tablename__ = "operator_supplementary"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    char_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    acquisition_path: Mapped[str] = mapped_column(Text, default="")
    release_date: Mapped[str] = mapped_column(Text, default="")
    dynamic_id: Mapped[str] = mapped_column(String(64), default="")
    specialization: Mapped[str] = mapped_column(Text, default="")
    drawer: Mapped[str] = mapped_column(Text, default="")
    promo_intro: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="bilibili")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
