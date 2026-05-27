# Database Architecture Specification — InquiryBot Enterprise

InquiryBot Enterprise utilizes SQLite as its transactional data ledger, configured for multi-threaded access and transactional safety.

## 1. Schema Tables

### `leads`
Tracks business contact details and interaction states.
```sql
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    status TEXT DEFAULT 'New',
    intent TEXT DEFAULT 'general',
    notes TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `sessions`
Coordinates communication sessions belonging to a specific lead.
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    lead_id INTEGER NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
);
```

### `messages`
Maintains the complete, immutable transaction log of chat logs.
```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,
    citations_json TEXT,         -- Serialized JSON array of citation dicts
    model TEXT,                  -- Model name (e.g. gpt-4o-mini)
    intent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

### `documents`
Tracks state metadata for uploaded and parsed PDF assets.
```sql
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,  -- SHA-256 hash to prevent duplicate ingestion
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'uploaded',  -- 'uploaded' | 'ingested' | 'failed'
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ingested_at TIMESTAMP,
    error_message TEXT
);
```

### `training_entries`
Stores custom QA pairs created by administrative users.
```sql
CREATE TABLE IF NOT EXISTS training_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,
    tags TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 2. Index Strategy
To ensure optimal performance as table records grow, the following indices are maintained:
*   `idx_leads_phone` on `leads(phone)` for rapid user identification lookup.
*   `idx_leads_email` on `leads(email)` as a secondary identification path.
*   `idx_sessions_last_active` on `sessions(last_active_at)` for active user status calculations.
*   `idx_messages_session` on `messages(session_id)` for quick conversational retrieval.
*   `idx_documents_hash` on `documents(file_hash)` for duplicate file prevention checks.

## 3. Database Constraints & Settings
The initialization module executes these settings on every connection:
*   `PRAGMA foreign_keys = ON;` — Guarantees referential integrity; deleting a session or lead cascades to delete associated messages.
*   `PRAGMA journal_mode = WAL;` — Write-Ahead Logging allows concurrently reading from Streamlit threads while write transactions are outstanding.
