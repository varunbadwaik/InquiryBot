# Internal Service Specification — InquiryBot Enterprise

This specification outlines the signatures, models, and error behaviors for the service interfaces inside the application.

## 1. ChatService
Handles retrieval-augmented question answering, prompting constraints, and response construction.

### `generate_response(session_id: str, lead_id: int, query: str) -> dict`
*   **Purpose:** Fetches context chunks, formats prompt with anti-hallucination rules, calls OpenAI, persists conversation, and serializes citations.
*   **Output Structure:**
    ```python
    {
        "answer": str,       # Fully formulated text response
        "citations": list,  # List of dicts with source_type, document_name, chunk_index
        "model": str         # Model identifier used (e.g. gpt-4o-mini)
    }
    ```
*   **Exceptions Raised:**
    *   `ValueError` on invalid or empty queries.
    *   `Exception` on OpenAI api failures.

---

## 2. LeadService
Coordinates lead resolution, deduplication, and matching.

### `find_or_create_lead(name: str, phone: str, email: str, intent: str = "general") -> Lead`
*   **Purpose:** Resolves lead identity using tiered phone-then-email matches, updating name/email fields if they were missing.
*   **Output:** Returns a `Lead` schemas instance.

### `update_lead_status(lead_id: int, status: str) -> bool`
*   **Purpose:** Transitions lead status (e.g., "New", "Contacted", "Closed") in SQLite.

---

## 3. DocumentService
Manages raw uploaded PDF assets and coordinates vector ingestion.

### `upload_and_ingest_document(file_name: str, file_bytes: bytes) -> dict`
*   **Purpose:** Computes file hash, checks duplicates, writes file to local upload directory, and splits, embeds, and loads chunks to ChromaDB.
*   **Output Structure:**
    ```python
    {
        "status": "success" | "duplicate" | "error",
        "document_id": int,
        "chunk_count": int,
        "message": str
    }
    ```

---

## 4. TrainingService
Enables the administration panel to synchronize custom FAQ overrides directly to the vector corpus.

### `create_training_entry(question: str, answer: str, category: str = "", tags: str = "") -> TrainingEntry`
*   **Purpose:** Inserts a QA pair in SQLite and embed-syncs it as a persistent chunk in ChromaDB.

### `update_training_entry(entry_id: int, question: str, answer: str, category: str, tags: str) -> bool`
*   **Purpose:** Re-embeds the vector chunk and updates relational data.

### `delete_training_entry(entry_id: int) -> bool`
*   **Purpose:** Purges the chunk from ChromaDB by ID and deletes SQLite record.

---

## 5. AdminService
Aggregates state information and logs for active user monitoring.

### `get_dashboard_metrics() -> dict`
*   **Purpose:** Compiles metrics counts for Total Leads, Active Users, Todays Messages, Ingested Files, and FAQ Entries.

### `get_active_sessions_with_leads() -> list`
*   **Purpose:** Returns a list of active user metadata, mapping leads to session states.
