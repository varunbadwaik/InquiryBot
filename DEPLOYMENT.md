# Vercel Free Deployment Notes

This repository is optimized so Vercel Free deploys only the lightweight Python
entrypoint in `app.py`.

## Dependency Strategy

`requirements.txt` is intentionally minimal for Vercel:

```text
# Vercel deployment dependencies.
# app.py uses only the Python standard library.
```

The full Streamlit RAG chatbot uses heavier local dependencies and should be
installed with:

```bash
pip install -r requirements-local.txt
```

Those local dependencies include Streamlit, ChromaDB, LangChain, PyPDF, and
OpenAI. They are not installed in Vercel because they can push the serverless
bundle toward the 500 MB limit and because Streamlit is not a good fit for
Vercel serverless execution.

## Asset Strategy

Large files are not bundled:

- `data/` is ignored by git and Vercel.
- `chroma_db/` is ignored by git and Vercel.
- `logs/` and `leads.csv` are ignored.
- Local virtual environments are ignored.

Use one of these approaches for large PDFs or model files:

- Upload PDFs at runtime in the Streamlit UI when running the chatbot on a
  Streamlit-compatible host.
- Store PDFs in S3, Google Cloud Storage, Azure Blob Storage, or another object
  store and download only the required file at runtime.
- Keep generated Chroma indexes outside the repository. Rebuild them from source
  documents on the host, or use a managed vector database for production.

## Vercel Behavior

Vercel serves `app.py`, a small WSGI landing/status page. It does not run the
full chatbot UI.

For the real chatbot experience, deploy `chatbot.py` to a platform that supports
long-running Streamlit apps, such as:

- Streamlit Community Cloud
- Render
- Railway
- A VM/container host

## Runtime Secrets

Never commit `.env`. Set secrets in the hosting provider dashboard:

```text
OPENAI_API_KEY=...
```

## Local Run

```bash
pip install -r requirements-local.txt
streamlit run chatbot.py
```

## Vercel Run

Vercel should install from `requirements.txt`, skip files listed in
`.vercelignore`, and deploy `app.py`.
