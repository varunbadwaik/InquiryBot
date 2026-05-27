"""Domain dataclasses for InquiryBot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Lead:
    id: Optional[int] = None
    name: str = ""
    phone: str = ""
    email: str = ""
    status: str = "New"
    intent: str = ""
    notes: str = ""
    organization: str = ""
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Session:
    id: str = ""
    lead_id: Optional[int] = None
    started_at: Optional[str] = None
    last_active_at: Optional[str] = None
    status: str = "active"


@dataclass
class Message:
    id: Optional[int] = None
    session_id: str = ""
    role: str = ""
    content: str = ""
    citations_json: str = "[]"
    model: str = ""
    created_at: Optional[str] = None


@dataclass
class DocumentRecord:
    id: Optional[int] = None
    file_name: str = ""
    file_path: str = ""
    file_hash: str = ""
    chunk_count: int = 0
    status: str = "uploaded"
    uploaded_at: Optional[str] = None
    ingested_at: Optional[str] = None
    error_message: str = ""


@dataclass
class TrainingEntry:
    id: Optional[int] = None
    question: str = ""
    answer: str = ""
    category: str = ""
    tags: str = ""
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
