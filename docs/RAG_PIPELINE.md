# Retrieval-Augmented Generation (RAG) Pipeline — InquiryBot Enterprise

This document describes the end-to-end data ingestion and vector retrieval pipeline implemented in InquiryBot Enterprise.

## 1. Document Ingestion Lifecycle

```text
Upload PDF ──> Hash Validation ──> Text Parsing ──> Recursive Splitter ──> Vector Embeddings ──> ChromaDB
```

*   **Step 1: Upload & Deduplication Gate:** Uploaded PDF bytes are parsed, and a SHA-256 checksum is calculated. The system queries SQLite `documents` for matching hashes. If found, the ingestion aborts, returning a status warning.
*   **Step 2: Document Parsing:** Validated PDFs are read using `PyPDF2` / standard LangChain document loader APIs to extract page content.
*   **Step 3: Document Chunking:** Content is split using a `RecursiveCharacterTextSplitter` configured with a target `CHUNK_SIZE = 800` characters and `CHUNK_OVERLAP = 150` characters.
*   **Step 4: Vector Generation:** Chunks are embedded in batches utilizing OpenAI's configured embeddings client.
*   **Step 5: Vector DB Injection:** Chunks are loaded into ChromaDB under the collection name `inquirybot_documents`. Batches are committed in groupings (max 100) to ensure high-speed, safe uploads.

## 2. Dynamic Retrieval & Inference Lifecycle

```text
User Question ──> Embed Query ──> Chroma Similarity Search (k=5) ──> Similarity Gating (0.35) ──> Deduplication ──> Prompt Context Assembly ──> LLM Completion
```

*   **Step 1: Embedding User Input:** The user query is vectorized using the same embeddings model configuration.
*   **Step 2: Vector Search:** Queries ChromaDB for the top $K$ ($K = 5$) nearest neighbor documents, capturing content, metadata, and distance metrics.
*   **Step 3: Similarity Score Threshold Gate:** Chroma distances are converted into normalized similarity scores: `score = 1 / (1 + distance)`. All chunks with a relevance score below `0.35` are discarded.
*   **Step 4: Context Merging:** Surviving context chunks are mapped to their origins (e.g. document name or admin training id). Duplicate adjacent chunks are merged.
*   **Step 5: Response Generation & Citations:** The completion output references the origin names, and citations are parsed and saved to SQLite alongside the query exchange.
