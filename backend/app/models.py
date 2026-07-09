from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (JSON, Boolean, Computed, Date, DateTime, Float,
                        ForeignKey, Index, Integer, String, Text)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.base import EMBED_DIM
from app.db import Base


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Owned:
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class User(Base, TS):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    firm_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Client(Base, TS, Owned):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    afm: Mapped[str | None] = mapped_column(String(9), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Case(Base, TS, Owned):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100), default="civil")
    court_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    next_action: Mapped[str] = mapped_column(String(500), default="")
    ref_numbers: Mapped[str] = mapped_column(String(255), default="")
    facts_text: Mapped[str] = mapped_column(Text, default="")


class Party(Base, TS, Owned):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100), default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)


class CaseFact(Base, TS, Owned):
    __tablename__ = "case_facts"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # date|amount|claim|other
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    confirmed_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_group: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Deadline(Base, TS, Owned):
    __tablename__ = "deadlines"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    due_date: Mapped[date] = mapped_column(Date)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentType(Base, TS):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name_gr: Mapped[str] = mapped_column(String(255), unique=True)
    category: Mapped[str] = mapped_column(String(100), default="civil")
    checklist_template: Mapped[list] = mapped_column(JSON, default=list)


class Document(Base, TS, Owned):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"))
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|exported
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DocumentVersion(Base, TS, Owned):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(10), default="ai")  # ai|lawyer
    content_hash: Mapped[str] = mapped_column(String(64), default="")


class Evidence(Base, TS, Owned):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    exhibit_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500), default="")
    file_path: Mapped[str] = mapped_column(String(1000))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    ocr_pending: Mapped[bool] = mapped_column(Boolean, default=False)


class StyleSample(Base, TS, Owned):
    __tablename__ = "style_samples"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    original_text: Mapped[str] = mapped_column(Text, default="")
    scrubbed_text: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok|ocr_pending|rejected


class StyleProfile(Base, TS, Owned):
    __tablename__ = "style_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    built_from_sample_ids: Mapped[list] = mapped_column(JSON, default=list)
    approved_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)


class AIDraft(Base, TS, Owned):
    __tablename__ = "ai_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    document_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    style_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inputs_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    uncertainty_report: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|failed
    error: Mapped[str] = mapped_column(Text, default="")


class ChecklistItem(Base, TS, Owned):
    __tablename__ = "checklist_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    source_agent: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10))  # red|yellow
    text: Mapped[str] = mapped_column(Text)
    anchor_quote: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved|overridden
    override_note: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditLog(Base, TS):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchIndex(Base, TS, Owned):
    __tablename__ = "search_index"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # document|evidence|sample
    ref_id: Mapped[int] = mapped_column(Integer)
    case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('greek', text)", persisted=True))
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    __table_args__ = (
        Index("ix_search_tsv", "tsv", postgresql_using="gin"),
        Index("ix_search_kind_ref", "kind", "ref_id", unique=True),
    )
