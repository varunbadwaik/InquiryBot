# Training Ingestion & FAQ Workflows — InquiryBot Enterprise

InquiryBot Enterprise enables administrators to train the RAG assistant using two different modalities: file-based document ingestion and custom FAQ Q&A training overrides.

## 1. Custom FAQ (Chat Training) Workflow
FAQ overrides are ideal for providing explicit answers to questions (such as pricing tiers, custom support processes, or specific contact details) that might not be comprehensively covered in uploaded PDFs.

### Ingestion Flow
1.  **Form Submission:** Admin enters a Question, Answer, Category, and optional tags in the Admin Panel Training tab.
2.  **Relational Persistence:** The FAQ entry is stored in the SQLite `training_entries` table.
3.  **Knowledge Document Construction:** The entry is converted to a LangChain `Document` structured as:
    ```text
    Question: {question}
    Answer: {answer}
    ```
4.  **Metadata Attribution:** Metadata tags are appended to distinguish the source:
    *   `source_type = "admin_training"`
    *   `document_name = "Admin Training"`
    *   `training_entry_id = {id}`
    *   `category = {category}`
    *   `tags = {tags}`
5.  **Chroma DB Injection:** The document is vectorized and loaded into ChromaDB using a deterministic string ID: `training_entry|{id}`.

### Mutation and Deletion Flows
*   **Updates:** When an FAQ entry is edited, the system deletes the old chunk from ChromaDB using the deterministic ID `training_entry|{id}`, updates the relational row in SQLite, re-vectorizes the new Q&A document, and loads the new chunk.
*   **Deletions:** When deleted, the system issues a purge statement to SQLite and calls `Chroma.delete(ids=[f"training_entry|{id}"])`.

---

## 2. Document Training (PDF) Workflow
Used for batch uploading corporate policies, manuals, product specifications, and general documentation.

1.  **Upload:** Admin drops a PDF file into the Streamlit file upload widget.
2.  **Integrity Validation:** The system reads file bytes and checks that the file size is under the configured limit (10MB) and has a `.pdf` extension.
3.  **SHA-256 Validation:** Checksum check queries SQLite to prevent duplicate processing.
4.  **Parsing & Chunking:** `PyPDF2` reads pages; `RecursiveCharacterTextSplitter` creates overlapping chunks.
5.  **Vector Store Loading:** Chunks are loaded in batches (max 100 per write) into ChromaDB with metadata referencing the original file name.
