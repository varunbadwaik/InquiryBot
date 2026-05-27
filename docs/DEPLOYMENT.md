# Deployment & Execution Guide — InquiryBot Enterprise

This guide covers local environment initialization and production scaling guidelines.

## 1. Local Development Quickstart

### Prerequisites
*   Python 3.11+
*   pip package manager
*   OpenAI API credentials

### Installation & Initialization
1.  **Clone or Navigate to the Workspace:**
    ```bash
    cd f:\InquiryBot\source_extracted\Inquirybot-langchain-main
    ```
2.  **Install Required Libraries:**
    ```bash
    pip install -r requirements-local.txt
    ```
3.  **Configure Local Environment Variables:**
    Create a `.env` file in the root workspace (based on `.env.example`):
    ```ini
    OPENAI_API_KEY=your_openai_api_key_here
    ADMIN_PASSWORD=your_admin_password_here
    APP_ENV=local
    DEFAULT_CHAT_MODEL=gpt-4o-mini
    EMBEDDING_MODEL=text-embedding-3-large
    SIMILARITY_SCORE_THRESHOLD=0.35
    ```
4.  **Execute the Test Suite:**
    ```bash
    python -m unittest discover tests -v
    ```
5.  **Launch the Streamlit Server:**
    ```bash
    streamlit run chatbot.py
    ```

---

## 2. Production Deployment Guidelines

### Stateful Storage Persistence
InquiryBot stores operational state inside SQLite (`storage/app.db`) and ChromaDB (`chroma_db/`).
*   **Volume Mounts:** In cloud environments (e.g. AWS ECS, GCP Cloud Run, or Kubernetes), the `storage/` and `chroma_db/` directories **must** be mounted to persistent volumes. Volatile file systems will result in data loss on container restarts.

### Secrets Management
*   **No Credentials in Repositories:** Never commit `.env` files to git.
*   **Cloud Injectors:** Use secret injection managers (such as AWS Secrets Manager, HashiCorp Vault, or Vercel Environment Variables) to feed `OPENAI_API_KEY` and `ADMIN_PASSWORD` directly into target runtime environments.

### Logs & Backup Strategy
*   **Logs Isolation:** App logs reside in `storage/app.log` or are outputted to `stdout`. Direct standard output to centralized cloud aggregators (e.g. Datadog or CloudWatch).
*   **Database Backups:** Maintain a periodic cron schedule to execute safe SQLite backups using:
    ```bash
    sqlite3 storage/app.db ".backup 'storage/backups/app_backup.db'"
    ```
