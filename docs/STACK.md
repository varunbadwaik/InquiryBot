# Technology Stack Specification — InquiryBot Enterprise

## 1. Application & Core Layer
*   **Language:** Python 3.11+ (Fully compatible with modern runtime libraries).
*   **Configuration:** `python-dotenv` for local environment variable loading (`.env` -> `config.py`).
*   **Validation & Serialization:** Pydantic (used for structured schema modeling and configuration verification).

## 2. Presentation & User Interface
*   **Framework:** Streamlit (v1.30+).
    *   *Rationale:* Facilitates extremely rapid, reactive frontend prototyping for the chatbot UI, lead forms, and the administrative dashboard.
    *   *Routing:* Utilizes Streamlit's native multipage routing via a `pages/` directory to separate the user-facing app from `pages/Admin.py`.

## 3. Persistent Database Layer
*   **Relational Engine:** SQLite (using the Python Standard Library `sqlite3` driver).
    *   *Rationale:* Eliminates infrastructure setup overhead, offers simple deployment, and guarantees transactional integrity (ACID) for leads, sessions, and messages.
    *   *Configuration:* Optimized with Write-Ahead Logging (WAL) and foreign key enforcement (`PRAGMA foreign_keys = ON;`).
*   **Vector Engine:** ChromaDB.
    *   *Rationale:* Offers zero-setup local persistent vector storage, seamless integration with LangChain's retrievers, and structured metadata query support.

## 4. Artificial Intelligence & RAG Orchestration
*   **Framework:** LangChain (v0.1.0+).
    *   *Chroma Wrapper:* `langchain-community` vector store integration.
    *   *Models Wrapper:* `langchain-openai` for high-performance embeddings and completion requests.
*   **Embeddings Model:** `text-embedding-3-large` (or `text-embedding-ada-002`).
*   **Generative Chat Model:** `gpt-4o-mini` / `gpt-4.1-mini`.

## 5. Development & Testing Framework
*   **Unit & Integration Tests:** Standard library `unittest` runner.
*   **Code Coverage:** `coverage.py` compatibility for service-layer and repository-layer verification.
