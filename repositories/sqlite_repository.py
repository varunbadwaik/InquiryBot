"""SQLite repository for InquiryBot persistence.

All database operations are centralised here. The module exposes plain
functions that operate on a shared connection created lazily on first use.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import DB_PATH, STORAGE_DIR
from models.schemas import DocumentRecord, Lead, Message, Session, TrainingEntry


logger = logging.getLogger(__name__)

_connection: Optional[sqlite3.Connection] = None


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Return the shared SQLite connection, creating it on first call."""
    global _connection
    if _connection is None:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        init_db(_connection)
    return _connection


def close_connection() -> None:
    """Close the shared connection if open."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def reset_connection(db_path: str | Path | None = None) -> None:
    """Close the current connection and point to a new database path.

    Useful for tests that need an isolated in-memory or temp database.
    """
    global _connection
    close_connection()
    if db_path is not None:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _connection = conn
        init_db(_connection)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables if they do not exist (idempotent)."""
    c = conn or _get_connection()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL DEFAULT '',
            phone        TEXT NOT NULL DEFAULT '',
            email        TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'New',
            intent       TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            organization TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT,
            last_seen_at  TEXT,
            created_at   TEXT,
            updated_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id             TEXT PRIMARY KEY,
            lead_id        INTEGER,
            started_at     TEXT,
            last_active_at TEXT,
            status         TEXT NOT NULL DEFAULT 'active',
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     TEXT NOT NULL,
            role           TEXT NOT NULL,
            content        TEXT NOT NULL DEFAULT '',
            citations_json TEXT NOT NULL DEFAULT '[]',
            model          TEXT NOT NULL DEFAULT '',
            created_at     TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name     TEXT NOT NULL DEFAULT '',
            file_path     TEXT NOT NULL DEFAULT '',
            file_hash     TEXT NOT NULL DEFAULT '',
            chunk_count   INTEGER NOT NULL DEFAULT 0,
            status        TEXT NOT NULL DEFAULT 'uploaded',
            uploaded_at   TEXT,
            ingested_at   TEXT,
            error_message TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS training_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            question   TEXT NOT NULL DEFAULT '',
            answer     TEXT NOT NULL DEFAULT '',
            category   TEXT NOT NULL DEFAULT '',
            tags       TEXT NOT NULL DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        );
    """)
    c.commit()
    logger.info("SQLite database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def create_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    intent: str = "",
    status: str = "New",
    notes: str = "",
    organization: str = "",
) -> Lead:
    now = _utcnow()
    conn = _get_connection()
    cursor = conn.execute(
        """INSERT INTO leads (name, phone, email, status, intent, notes, organization,
                              first_seen_at, last_seen_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, phone, email, status, intent, notes, organization, now, now, now, now),
    )
    conn.commit()
    return Lead(
        id=cursor.lastrowid,
        name=name, phone=phone, email=email,
        status=status, intent=intent, notes=notes,
        organization=organization,
        first_seen_at=now, last_seen_at=now,
        created_at=now, updated_at=now,
    )


def get_lead_by_id(lead_id: int) -> Optional[Lead]:
    row = _get_connection().execute(
        "SELECT * FROM leads WHERE id = ?", (lead_id,)
    ).fetchone()
    return _row_to_lead(row) if row else None


def get_lead_by_phone(phone: str) -> Optional[Lead]:
    if not phone:
        return None
    row = _get_connection().execute(
        "SELECT * FROM leads WHERE phone = ? ORDER BY id LIMIT 1", (phone,)
    ).fetchone()
    return _row_to_lead(row) if row else None


def get_lead_by_email(email: str) -> Optional[Lead]:
    if not email:
        return None
    row = _get_connection().execute(
        "SELECT * FROM leads WHERE email = ? AND email != '' ORDER BY id LIMIT 1",
        (email,),
    ).fetchone()
    return _row_to_lead(row) if row else None


def find_or_create_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    intent: str = "",
    organization: str = "",
) -> Lead:
    """Match existing lead by phone first, then email. Create if not found."""
    lead = get_lead_by_phone(phone)
    if lead is None and email:
        lead = get_lead_by_email(email)

    if lead is not None:
        # Update fields that may have changed
        now = _utcnow()
        updates = {"last_seen_at": now, "updated_at": now}
        if name and not lead.name:
            updates["name"] = name
        if email and not lead.email:
            updates["email"] = email
        if intent:
            updates["intent"] = intent
        if organization and not lead.organization:
            updates["organization"] = organization
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [lead.id]
        _get_connection().execute(
            f"UPDATE leads SET {set_clause} WHERE id = ?", values,
        )
        _get_connection().commit()
        return get_lead_by_id(lead.id)  # type: ignore[return-value]

    return create_lead(name=name, phone=phone, email=email, intent=intent, organization=organization)


def update_lead_status(lead_id: int, status: str) -> None:
    now = _utcnow()
    _get_connection().execute(
        "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, lead_id),
    )
    _get_connection().commit()


def update_lead_notes(lead_id: int, notes: str) -> None:
    now = _utcnow()
    _get_connection().execute(
        "UPDATE leads SET notes = ?, updated_at = ? WHERE id = ?",
        (notes, now, lead_id),
    )
    _get_connection().commit()


def update_lead_activity(lead_id: int) -> None:
    now = _utcnow()
    _get_connection().execute(
        "UPDATE leads SET last_seen_at = ?, updated_at = ? WHERE id = ?",
        (now, now, lead_id),
    )
    _get_connection().commit()


def list_leads() -> list[Lead]:
    rows = _get_connection().execute(
        "SELECT * FROM leads ORDER BY last_seen_at DESC"
    ).fetchall()
    return [_row_to_lead(r) for r in rows]


def _row_to_lead(row: sqlite3.Row) -> Lead:
    return Lead(
        id=row["id"], name=row["name"], phone=row["phone"], email=row["email"],
        status=row["status"], intent=row["intent"], notes=row["notes"],
        organization=row["organization"] if "organization" in row.keys() else "",
        first_seen_at=row["first_seen_at"], last_seen_at=row["last_seen_at"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def create_session(session_id: str, lead_id: int) -> Session:
    now = _utcnow()
    _get_connection().execute(
        """INSERT INTO sessions (id, lead_id, started_at, last_active_at, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (session_id, lead_id, now, now),
    )
    _get_connection().commit()
    return Session(
        id=session_id, lead_id=lead_id,
        started_at=now, last_active_at=now, status="active",
    )


def get_session(session_id: str) -> Optional[Session]:
    row = _get_connection().execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return _row_to_session(row) if row else None


def update_session_active(session_id: str) -> None:
    now = _utcnow()
    _get_connection().execute(
        "UPDATE sessions SET last_active_at = ? WHERE id = ?", (now, session_id),
    )
    _get_connection().commit()


def list_sessions() -> list[Session]:
    rows = _get_connection().execute(
        "SELECT * FROM sessions ORDER BY last_active_at DESC"
    ).fetchall()
    return [_row_to_session(r) for r in rows]


def get_active_sessions(timeout_minutes: int = 10) -> list[dict[str, Any]]:
    """Return sessions with activity in the last ``timeout_minutes``."""
    conn = _get_connection()
    rows = conn.execute("""
        SELECT s.id AS session_id, s.lead_id, s.last_active_at, s.status,
               l.name, l.phone, l.email,
               COUNT(m.id) AS message_count,
               MAX(m.created_at) AS last_message_at
        FROM sessions s
        LEFT JOIN leads l ON s.lead_id = l.id
        LEFT JOIN messages m ON m.session_id = s.id
        GROUP BY s.id
        ORDER BY s.last_active_at DESC
    """).fetchall()

    result = []
    for r in rows:
        result.append({
            "session_id": r["session_id"],
            "lead_id": r["lead_id"],
            "name": r["name"] or "",
            "phone": r["phone"] or "",
            "email": r["email"] or "",
            "message_count": r["message_count"],
            "last_message_at": r["last_message_at"],
            "last_active_at": r["last_active_at"],
            "status": r["status"],
        })
    return result


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"], lead_id=row["lead_id"],
        started_at=row["started_at"], last_active_at=row["last_active_at"],
        status=row["status"],
    )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def create_message(
    session_id: str,
    role: str,
    content: str,
    citations_json: str = "[]",
    model: str = "",
) -> Message:
    now = _utcnow()
    conn = _get_connection()
    cursor = conn.execute(
        """INSERT INTO messages (session_id, role, content, citations_json, model, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, role, content, citations_json, model, now),
    )
    conn.commit()
    return Message(
        id=cursor.lastrowid, session_id=session_id,
        role=role, content=content, citations_json=citations_json,
        model=model, created_at=now,
    )


def get_messages_by_session(session_id: str) -> list[Message]:
    rows = _get_connection().execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    return [_row_to_message(r) for r in rows]


def count_messages_by_session(session_id: str) -> int:
    row = _get_connection().execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row["cnt"] if row else 0


def get_latest_message_by_session(session_id: str) -> Optional[Message]:
    row = _get_connection().execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return _row_to_message(row) if row else None


def list_messages_filtered(
    phone: str = "",
    name: str = "",
    session_id: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict[str, Any]]:
    """Return messages joined with lead info, applying optional filters."""
    conn = _get_connection()
    query = """
        SELECT m.id, m.session_id, m.role, m.content, m.citations_json,
               m.model, m.created_at,
               l.name, l.phone, l.email, l.intent
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        LEFT JOIN leads l ON s.lead_id = l.id
        WHERE 1=1
    """
    params: list[Any] = []

    if phone:
        query += " AND l.phone = ?"
        params.append(phone)
    if name:
        query += " AND l.name LIKE ?"
        params.append(f"%{name}%")
    if session_id:
        query += " AND m.session_id = ?"
        params.append(session_id)
    if date_from:
        query += " AND m.created_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND m.created_at <= ?"
        params.append(date_to)

    query += " ORDER BY m.created_at DESC"
    rows = conn.execute(query, params).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "content": r["content"],
            "citations_json": r["citations_json"],
            "model": r["model"],
            "created_at": r["created_at"],
            "name": r["name"] or "",
            "phone": r["phone"] or "",
            "email": r["email"] or "",
            "intent": r["intent"] or "",
        })
    return result


def _row_to_message(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"], session_id=row["session_id"],
        role=row["role"], content=row["content"],
        citations_json=row["citations_json"], model=row["model"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def create_document(
    file_name: str,
    file_path: str,
    file_hash: str,
    status: str = "uploaded",
) -> DocumentRecord:
    now = _utcnow()
    conn = _get_connection()
    cursor = conn.execute(
        """INSERT INTO documents (file_name, file_path, file_hash, status, uploaded_at)
           VALUES (?, ?, ?, ?, ?)""",
        (file_name, file_path, file_hash, status, now),
    )
    conn.commit()
    return DocumentRecord(
        id=cursor.lastrowid, file_name=file_name,
        file_path=file_path, file_hash=file_hash,
        status=status, uploaded_at=now,
    )


def get_document_by_hash(file_hash: str) -> Optional[DocumentRecord]:
    row = _get_connection().execute(
        "SELECT * FROM documents WHERE file_hash = ? LIMIT 1", (file_hash,)
    ).fetchone()
    return _row_to_document(row) if row else None


def get_document_by_id(doc_id: int) -> Optional[DocumentRecord]:
    row = _get_connection().execute(
        "SELECT * FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    return _row_to_document(row) if row else None


def update_document_status(
    doc_id: int,
    status: str,
    chunk_count: int = 0,
    error_message: str = "",
) -> None:
    now = _utcnow()
    _get_connection().execute(
        """UPDATE documents
           SET status = ?, chunk_count = ?, error_message = ?, ingested_at = ?
           WHERE id = ?""",
        (status, chunk_count, error_message, now, doc_id),
    )
    _get_connection().commit()


def list_documents() -> list[DocumentRecord]:
    rows = _get_connection().execute(
        "SELECT * FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    return [_row_to_document(r) for r in rows]


def delete_document_record(doc_id: int) -> None:
    _get_connection().execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    _get_connection().commit()


def _row_to_document(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        id=row["id"], file_name=row["file_name"],
        file_path=row["file_path"], file_hash=row["file_hash"],
        chunk_count=row["chunk_count"], status=row["status"],
        uploaded_at=row["uploaded_at"], ingested_at=row["ingested_at"],
        error_message=row["error_message"],
    )


# ---------------------------------------------------------------------------
# Training entries
# ---------------------------------------------------------------------------

def create_training_entry(
    question: str,
    answer: str,
    category: str = "",
    tags: str = "",
) -> TrainingEntry:
    now = _utcnow()
    conn = _get_connection()
    cursor = conn.execute(
        """INSERT INTO training_entries (question, answer, category, tags,
                                        status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'active', ?, ?)""",
        (question, answer, category, tags, now, now),
    )
    conn.commit()
    return TrainingEntry(
        id=cursor.lastrowid, question=question, answer=answer,
        category=category, tags=tags, status="active",
        created_at=now, updated_at=now,
    )


def get_training_entry(entry_id: int) -> Optional[TrainingEntry]:
    row = _get_connection().execute(
        "SELECT * FROM training_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    return _row_to_training(row) if row else None


def update_training_entry(
    entry_id: int,
    question: str = "",
    answer: str = "",
    category: str = "",
    tags: str = "",
) -> None:
    now = _utcnow()
    _get_connection().execute(
        """UPDATE training_entries
           SET question = ?, answer = ?, category = ?, tags = ?, updated_at = ?
           WHERE id = ?""",
        (question, answer, category, tags, now, entry_id),
    )
    _get_connection().commit()


def delete_training_entry(entry_id: int) -> None:
    _get_connection().execute(
        "DELETE FROM training_entries WHERE id = ?", (entry_id,),
    )
    _get_connection().commit()


def list_training_entries() -> list[TrainingEntry]:
    rows = _get_connection().execute(
        "SELECT * FROM training_entries ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_training(r) for r in rows]


def _row_to_training(row: sqlite3.Row) -> TrainingEntry:
    return TrainingEntry(
        id=row["id"], question=row["question"], answer=row["answer"],
        category=row["category"], tags=row["tags"], status=row["status"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Aggregate queries for admin panel
# ---------------------------------------------------------------------------

def get_leads_with_stats() -> list[dict[str, Any]]:
    """Return all leads with conversation/message counts."""
    rows = _get_connection().execute("""
        SELECT l.*,
               COUNT(DISTINCT s.id) AS total_conversations,
               COUNT(m.id) AS total_messages
        FROM leads l
        LEFT JOIN sessions s ON s.lead_id = l.id
        LEFT JOIN messages m ON m.session_id = s.id
        GROUP BY l.id
        ORDER BY l.last_seen_at DESC
    """).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"], "name": r["name"], "phone": r["phone"],
            "email": r["email"], "status": r["status"], "intent": r["intent"],
            "notes": r["notes"], "organization": r["organization"] if "organization" in r.keys() else "",
            "first_seen_at": r["first_seen_at"],
            "last_seen_at": r["last_seen_at"],
            "total_conversations": r["total_conversations"],
            "total_messages": r["total_messages"],
        })
    return result
