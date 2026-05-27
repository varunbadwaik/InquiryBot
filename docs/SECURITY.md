# Security Architecture & Controls — InquiryBot Enterprise

This document details the security safeguards built into InquiryBot Enterprise to protect system APIs, administrative views, and uploaded files.

## 1. Authentication & Route Protection
*   **Admin Route Protection:** All administrative controls are located inside `pages/Admin.py`. The view checks Streamlit's `st.session_state` for authentication status. If unauthenticated, the application displays a secure password entry screen.
*   **Password Storage Strategy:** The administrative password is never hardcoded. It is loaded at runtime from the `ADMIN_PASSWORD` environment variable.

## 2. Relational & File Upload Protection
*   **100% Parameterized Queries:** To completely neutralize SQL Injection (SQLi) vulnerabilities, all queries executed inside `repositories/sqlite_repository.py` use strictly parameterized SQL inputs (e.g. `CURSOR.execute("SELECT * FROM leads WHERE phone = ?", (phone,))`).
*   **File Extension Filtering:** The file ingestion service validates that uploaded assets use the `.pdf` extension exclusively.
*   **File Size Caps:** Ingestion methods enforce a maximum upload threshold (10MB) to mitigate denial-of-service (DoS) risks from excessive memory usage.
*   **Path Traversal Countermeasures:** The upload directory is isolated to `data/`. Uploaded file names are sanitized using standard safe basename lookups to prevent path traversal attempts (`../../etc/passwd`).

## 3. API & Observability Protection
*   **Environment Secret Isolation:** All sensitive configuration items (such as `OPENAI_API_KEY`) are managed strictly using `.env` configurations. They are loaded securely into `config.py` using `python-dotenv`.
*   **Error Redaction:** Production run errors are logged to `logs/app.log` with complete stack traces, while the user frontend receives user-friendly, redacted notifications to prevent details leakage.
