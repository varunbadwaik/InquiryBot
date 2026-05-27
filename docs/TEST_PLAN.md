# Test Plan & Verification Strategy — InquiryBot Enterprise

InquiryBot Enterprise implements a multi-layered testing paradigm combining in-memory repository verification, mocked services integration, and manual quality assurance scripts.

## 1. Automated Test Suites

### A. Repository Testing (`tests/test_sqlite_repository.py`)
Verifies CRUD and query behavior against SQLite.
*   **Database Isolation:** Uses transient in-memory databases (`:memory:`) reset on every `setUp()` call.
*   **Coverage Focus:**
    *   Leads creation, email/phone lookups, and merge propagation.
    *   Session creation and timing metrics.
    *   Message persistence, serializing and deserializing JSON citations list.
    *   Document uploading and SHA-256 duplicate constraint enforcement.
    *   Training entry additions, updates, and deletion cascades.

### B. Service Testing (`tests/test_services.py`)
Verifies service logic and business rules.
*   **Coverage Focus:**
    *   Tiered lead matching priorities (Phone match > Email match > Create new).
    *   FAQ metadata generation for vector store registration.
    *   Ensuring conversation history is loaded in correct chronological order.

### C. Retrieval Testing (`tests/test_retrieval.py`)
Ensures RAG queries function correctly.
*   **Coverage Focus:**
    *   Ensuring distance scores normalize accurately.
    *   Verifying score range bounds.
    *   Verifying relevance score filtering below `0.35`.

## 2. Execution Command
To run the automated tests, execute:
```bash
python -m unittest discover tests -v
```

## 3. Manual QA Scenarios
To verify aspects that cannot be fully automated:
*   **Upload Duplicate PDF:** Verify that attempting to re-upload an ingested PDF blocks processing and displays a warning.
*   **Unsupported Domain Question:** Submit queries outside the ingested scope. Confirm the assistant responds with the precise configured `REFUSAL_MESSAGE`.
*   **Admin Panel Unauthorized Attempt:** Attempt to navigate to the administrative page via `http://localhost:8501/Admin` and confirm the credential entry dialog is displayed.
