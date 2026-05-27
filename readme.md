# InquiryBot LangChain RAG

InquiryBot is a production-grade Streamlit chatbot for answering questions over PDF
documents. It uses OpenAI embeddings, ChromaDB for persistent vector search,
LangChain for retrieval, SQLite for persistence, and includes a full admin panel.

## What It Does

- Ingests PDFs from `data/` or from the admin panel file uploader.
- Stores vectors locally in `chroma_db/`.
- Uses one shared Chroma collection and one embedding model everywhere.
- Retrieves relevant chunks with a similarity score threshold.
- Answers only from document context and politely refuses unsupported questions.
- Shows citations with document name, page number, relevance score, and chunk text.
- Captures leads with name, phone (required), email (optional), and intent.
- Matches returning users by phone or email.
- Persists all sessions, messages, and lead data in SQLite.
- Supports FAQ/knowledge training entries that integrate into RAG retrieval.
- Full admin panel with authentication, active user monitoring, chat history,
  lead management, document management, and training management.
- Logs runtime errors to `logs/app.log`.

## Project Structure

```text
Inquirybot-langchain/
├── chatbot.py                  # Streamlit chatbot UI (main entry point)
├── app.py                      # Vercel WSGI stub
├── config.py                   # Paths, models, retrieval settings, env overrides
├── database.py                 # Chroma, PDF loading, ingestion, retrieval helpers
├── embeddings.py               # Shared OpenAI embedding client
├── ingest_database.py          # CLI ingestion/rebuild script
├── utils.py                    # Logging, uploads, citations, validation helpers
├── models/
│   └── schemas.py              # Domain dataclasses (Lead, Session, Message, etc.)
├── repositories/
│   └── sqlite_repository.py    # All SQLite CRUD operations
├── services/
│   ├── chat_service.py         # Chat logic, LLM calls, message persistence
│   ├── lead_service.py         # Lead CRUD, matching, activity tracking
│   ├── document_service.py     # PDF tracking, ingestion, duplicate detection
│   ├── admin_service.py        # Admin data aggregation, auth, CSV export
│   └── training_service.py     # FAQ training pipeline with Chroma ingestion
├── pages/
│   └── Admin.py                # Admin panel (auth, users, history, leads, training)
├── storage/                    # SQLite database (auto-created, gitignored)
├── data/                       # PDF documents
├── tests/
│   ├── test_retrieval.py       # Original retrieval tests
│   ├── test_sqlite_repository.py  # SQLite repository tests
│   └── test_services.py        # Service layer tests
├── .env.example
├── requirements-local.txt
├── TECHNICAL_NOTES.md
└── DEPLOYMENT.md
```

## Setup

Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements-local.txt
```

Create a `.env` file:

```bash
copy .env.example .env
```

Configure required variables:

```env
OPENAI_API_KEY=your_openai_api_key_here
ADMIN_PASSWORD=your_admin_password_here
APP_ENV=local
```

Optional overrides (defaults shown):

```env
DEFAULT_CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-large
SIMILARITY_SCORE_THRESHOLD=0.35
```

## Run the App

```bash
streamlit run chatbot.py
```

The chatbot will:

1. Show a lead capture form (name, phone required, email optional).
2. Match returning users by phone or email.
3. Start an interactive chat with document-grounded answers.
4. Display citations for every answer.
5. Persist all messages to SQLite.

## Admin Panel

Navigate to the **Admin** page in the Streamlit sidebar.

Features:

- **Active Users** — real-time view of active sessions (10-minute window)
- **Chat History** — filterable message history with CSV export
- **Leads** — lead management with editable status and notes
- **File Training** — PDF upload, ingestion, duplicate detection, rebuild
- **Chat Training** — FAQ/knowledge entry management with auto-ingestion

## CLI Ingestion

```bash
# Ingest all PDFs from data/
python ingest_database.py

# Rebuild the vector database
python ingest_database.py --rebuild

# Ingest specific files
python ingest_database.py "data/document.pdf"
```

## Citations

Each answer includes expandable source citations with:

- Document name
- Page number
- Relevance score
- Retrieved chunk text
- Source type (PDF or Admin Training)

If no retrieved chunk passes the similarity threshold, the app returns a refusal
message instead of guessing.

## Tests

```bash
python -m unittest discover tests
```

Tests use deterministic fake embeddings and in-memory SQLite, so they do not
require OpenAI API calls.

## Notes

- `chroma_db/`, `storage/`, `.env`, `venv/`, logs, and CSV files are gitignored.
- Uploaded PDFs are saved into `data/`.
- SQLite database auto-initialises at `storage/app.db` on first run.
- Admin password must be set in `.env` — never hardcoded.
