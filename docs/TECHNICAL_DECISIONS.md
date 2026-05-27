# Technical Decisions & ADRs — InquiryBot Enterprise

This document aggregates the Architecture Decision Records (ADRs) explaining core systems and engineering compromises.

---

## ADR-001: Layered Modular Monolith Architecture
*   **Context:** The existing codebase was highly coupled, with database, vector store, and completion logic all written inside the presentation file (`chatbot.py`).
*   **Decision:** We transitioned to a clean layered architecture, organizing business rules into a `services/` layer, relational logic into `repositories/`, and pure configurations into `config.py`.
*   **Rationale:** Ensures highly isolated components that can be tested in isolation without spawning an entire Streamlit rendering runtime.

---

## ADR-002: SQLite Persistent Engine Selection
*   **Context:** Captured leads were stored in a CSV file that got overwritten, which could cause write locks and data corruption under high concurrent request volume.
*   **Decision:** Implemented SQLite as the persistent storage engine, utilizing standard library modules, explicit foreign key cascading, and WAL journal modes.
*   **Rationale:** Standard library SQLite requires zero extra cluster deployment setups, guarantees atomic transactions, and solves concurrency locks when multiple chat users interact concurrently.

---

## ADR-003: Streamlit Multipage Admin Interface
*   **Context:** Administrative capabilities (e.g. reviewing leads, monitoring active sessions, and updating FAQ files) required a protected panel.
*   **Decision:** Implemented pages/Admin.py using Streamlit's native multipage routing capabilities, protected via administrative credential verification checks.
*   **Rationale:** Keeps the tech stack 100% consistent across chatbot and admin dashboards, eliminating the need to compile, run, and host separate React/Flask application packages.

---

## ADR-004: Service/Repository Testing Strategy
*   **Context:** Developing test pipelines for RAG systems frequently suffers from external API dependencies (OpenAI/Chroma).
*   **Decision:** SQLite repository methods are designed to take parameterized paths, allowing all 30 repository tests to execute utilizing dynamic in-memory databases (`:memory:`).
*   **Rationale:** Guarantees fast unit-test suites that execute in under two seconds with 100% database isolation and zero reliance on local disk cleanup operations.

---

## ADR-005: RAG Relevance Score Gating
*   **Context:** Hallucination and irrelevant answers are a major business risk when users ask questions outside the domain boundaries.
*   **Decision:** Configured a strict relevance similarity threshold of `0.35` (computed from L2 vector distance: `1 / (1 + distance)`). Any retrieved chunks failing to pass this score are completely discarded.
*   **Rationale:** Guarantees that when users ask off-topic questions, the system falls back immediately and gracefully to the standardized `REFUSAL_MESSAGE` rather than guessing or fabricating claims.
