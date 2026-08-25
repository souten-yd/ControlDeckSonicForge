from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SetupComponent(Base):
    __tablename__ = "setup_components"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), default="missing")
    version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Provenance(Base):
    __tablename__ = "provenance"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[str] = mapped_column(String(120))
    engine_id: Mapped[str] = mapped_column(String(120))
    engine_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_revision: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_license_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    qa: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(48))
    mime_type: Mapped[str] = mapped_column(String(120))
    relative_path: Mapped[str] = mapped_column(String(400))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    provenance_id: Mapped[str] = mapped_column(ForeignKey("provenance.id"))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Voice(Base):
    __tablename__ = "voices"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(40), default="built-in")
    languages: Mapped[list] = mapped_column(JSON, default=list)
    engine_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recipe: Mapped[dict] = mapped_column(JSON, default=dict)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LocalizationBatch(Base):
    __tablename__ = "localization_batches"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(32), default="draft")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lines: Mapped[list["LocalizationLine"]] = relationship(cascade="all, delete-orphan", back_populates="batch")


class LocalizationLine(Base):
    __tablename__ = "localization_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("localization_batches.id"), index=True)
    line_id: Mapped[str] = mapped_column(String(120))
    character: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ja_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    en_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    qa: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    batch: Mapped[LocalizationBatch] = relationship(back_populates="lines")


def make_session_factory(settings: Settings):
    engine = create_engine(f"sqlite:///{settings.db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False)


def session_scope(factory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
