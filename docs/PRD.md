# Product Requirements Document (PRD) — InquiryBot Enterprise

## 1. Executive Summary
InquiryBot Enterprise is a production-grade AI-powered inquiry assistant designed to revolutionize how organizations resolve customer questions, capture high-intent leads, track real-time communication sessions, and govern organizational knowledge. The platform transforms standard, volatile vector search prototypes into a stable, persistent, and highly auditable enterprise-ready SaaS-lite solution.

## 2. Problem Statement
Existing RAG prototype solutions face several critical barriers to production readiness:
*   **Volatile State:** In-memory or CSV-based lead and chat tracking are prone to data loss, corruption, and lack concurrency support.
*   **Poor Observability:** Operations teams cannot easily audit active users, analyze conversation histories, or download transcripts.
*   **Ungoverned Knowledge:** Chatbots rely purely on passive document chunks. Organizations cannot easily correct errors or "train" the AI directly on highly specific FAQ overrides without fine-tuning.
*   **Hallucination Vulnerability:** Standard LLM prompts speculate on answers when relevant context is missing, exposing companies to business and legal risks.
*   **Security Gaps:** Lack of secure admin authentication and access controls leaves administrative APIs and file ingest workflows unprotected.

## 3. Scope of Work
### In-Scope
*   **Streamlit Chatbot Frontend:** Responsive, premium consumer-facing Q&A chatbot interface with structured lead capture forms.
*   **Multi-Tab Admin Panel:** Password-authenticated control center supporting leads CRM, active sessions, conversation transcript downloads, PDF uploads, and FAQ training entries.
*   **SQLite Relational Persistence:** Fully ACID-compliant relational persistence layer using raw `sqlite3` for leads, sessions, messages, uploaded documents, and custom Q&A training entries.
*   **Chroma Vector Database Integration:** Local vector store managing parsed PDF embeddings alongside admin FAQ training records.
*   **Anti-Hallucination Guardrails:** Strict score-based threshold gates (`0.35` similarity threshold) coupled with defensive prompts to refuse questions outside the ingested corpus.

### Out-of-Scope
*   Full LLM fine-tuning pipelines.
*   Multi-tenant SaaS payment gating.
*   Distributed multi-node PostgreSQL/Chroma high-availability clustering.

## 4. Key Performance Indicators (KPIs)
*   **Chatbot Response Latency:** < 3.0 seconds median response time.
*   **Retrieval Accuracy:** > 95% relevance score for questions answered in the ingested corpus.
*   **Ingestion Safety:** 0 duplicate document ingestion (prevented via SHA-256 hash checks).
*   **Persistence Reliability:** 100% conversation transcript and lead capture retention under SQLite WAL mode.
