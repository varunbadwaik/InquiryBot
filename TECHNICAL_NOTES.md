# InquiryBot — Technical Notes

## Architecture

### Design Pattern

The project follows a **Service-Repository-Model** pattern:

```
chatbot.py (UI) → services/ (business logic) → repositories/ (data access) → storage/app.db
                                               → database.py (Chroma vector ops)
```

- **Models** (`models/schemas.py`) — Pure dataclasses with no behavior. Represent
  leads, sessions, messages, documents, and training entries.
- **Repositories** (`repositories/sqlite_repository.py`) — All SQLite CRUD operations.
  Module-level functions with a shared connection. Each function is small, focused,
  and independently testable.
- **Services** — Business logic layer that orchestrates between repositories and
  the vector database:
  - `chat_service` — RAG Q&A, LLM calls, message persistence
  - `lead_service` — Lead matching, creation, activity tracking
  - `document_service` — PDF upload tracking, hash-based duplicate detection
  - `admin_service` — Authentication, data aggregation for the admin panel
  - `training_service` — FAQ entries with automatic Chroma ingestion
- **UI** (`chatbot.py`, `pages/Admin.py`) — Pure Streamlit presentation code.

### Why Not an ORM?

SQLite with raw `sqlite3` was chosen over SQLAlchemy or another ORM for these reasons:
- Zero additional dependencies (sqlite3 is in the Python standard library)
- Simple schema with no complex relationships needing ORM features
- Direct SQL gives full control over queries for admin aggregation
- Easier to understand and debug for a project of this size

---

## SQLite Storage Design

### Schema

Five tables with full audit timestamps:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `leads` | User contact info | phone, email, status, intent, first/last_seen_at |
| `sessions` | Chat sessions per lead | id (UUID), lead_id (FK), last_active_at |
| `messages` | All chat messages | session_id (FK), role, content, citations_json, model |
| `documents` | Tracked PDF uploads | file_hash, status, chunk_count, error_message |
| `training_entries` | FAQ/knowledge pairs | question, answer, category, tags, status |

### Connection Management

- Shared module-level connection with `check_same_thread=False` for Streamlit's
  threading model
- WAL journal mode for concurrent reads during chat + admin access
- Foreign keys enabled for referential integrity
- `reset_connection()` allows tests to use in-memory databases

### Initialisation

`init_db()` uses `CREATE TABLE IF NOT EXISTS` — idempotent and safe to call on
every app startup. No migration framework needed at this stage.

---

## Lead Matching Logic

When a user provides their details:

1. **Phone match first** — `SELECT * FROM leads WHERE phone = ? LIMIT 1`
2. **Email match second** — `SELECT * FROM leads WHERE email = ? AND email != '' LIMIT 1`
3. **Create new** — if neither match, insert a new lead

On match, the system updates:
- `last_seen_at` timestamp
- Missing `name` or `email` if the returning user now provides them
- `intent` if a new one is specified

This ensures returning users are recognized without requiring login.

---

## Active User Detection

An active user is defined as having a session with `last_active_at` within the
last 10 minutes (configurable via `ACTIVE_USER_TIMEOUT_MINUTES`).

The admin panel queries:
```sql
SELECT s.*, l.*, COUNT(m.id), MAX(m.created_at)
FROM sessions s
LEFT JOIN leads l ON s.lead_id = l.id
LEFT JOIN messages m ON m.session_id = s.id
GROUP BY s.id
```

The `is_active` flag is computed in Python by comparing `last_active_at` against
`now - timeout`. This avoids SQLite datetime function compatibility issues.

---

## Training Ingestion Pipeline

FAQ/knowledge entries follow this flow:

1. Admin submits question + answer + category + tags
2. Entry saved to `training_entries` table
3. Entry converted to a LangChain `Document` with metadata:
   - `source_type: "admin_training"`
   - `document_name: "Admin Training"`
   - `training_entry_id: <id>`
4. Document added to Chroma with a deterministic ID (`SHA-256 of "training_entry|{id}"`)
5. On update, the old chunk is deleted and replaced
6. On delete, both SQLite record and Chroma chunk are removed

Training entries appear in RAG retrieval alongside PDF chunks. Citations display
"Admin Training" as the source and are tagged with `*(Admin Training)*` in the UI.

---

## RAG Optimizations

### Improved System Prompt

The original prompt was:
> "Answer the user's question using only the provided context."

The new prompt adds explicit anti-hallucination rules:
- NEVER fabricate information
- If context is insufficient, respond with the exact refusal message
- Mention source documents when referencing information
- Ask for clarification rather than guessing on ambiguous questions
- Do NOT answer unrelated topics

### Retrieval Quality

- Similarity score threshold (`0.35`) filters out low-relevance chunks
- Distance-to-relevance conversion: `1 / (1 + distance)` with clamping
- Batch insertion prevents partial ingestion failures
- Deterministic chunk IDs based on content hash prevent true duplicates

### Citation Enhancements

- Citations now include `source_type` to distinguish PDF vs. Admin Training
- Admin Training citations are visually marked in the UI
- Citations stored as JSON in messages for full history replay

---

## Document Duplicate Detection

When uploading a PDF:

1. File saved to `data/` directory
2. SHA-256 hash computed over file bytes
3. Hash checked against `documents.file_hash` in SQLite
4. If match found → duplicate warning, no re-upload
5. If new → document record created with status "uploaded"

This prevents wasting embedding API calls on identical files.

---

## Trade-offs

| Decision | Trade-off |
|----------|-----------|
| SQLite over PostgreSQL | Simpler deployment, but limited concurrency |
| Module-level connection | Simple but not suitable for multi-process deployments |
| No migration framework | Simpler but manual ALTER TABLE for schema changes |
| Streamlit multipage | Easy admin routing but adds page selector to sidebar |
| Password auth over OAuth | Simple but not enterprise-grade |
| In-memory test databases | Fast and isolated but don't test disk I/O |

---

## Future Improvements

- **User authentication** — Replace phone-based matching with proper login
- **PostgreSQL migration** — For multi-instance deployments
- **Alembic migrations** — For schema versioning
- **WebSocket updates** — Real-time admin panel refresh
- **Conversation context** — Pass recent history to LLM for multi-turn coherence
- **Chunking strategy** — Sentence-aware splitting instead of fixed-size
- **Embedding cache** — Avoid re-embedding unchanged documents
- **Rate limiting** — Prevent API abuse
- **Export/import** — Bulk training entry management
- **Analytics dashboard** — Response quality metrics, usage patterns
