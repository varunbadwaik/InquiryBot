import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import DEFAULT_CHAT_MODEL, REFUSAL_MESSAGE
from repositories import sqlite_repository as repo
from services import chat_service, lead_service, admin_service, document_service, training_service
from utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Ensure SQLite tables exist on startup.
repo.init_db()

app = FastAPI(title="InquiryBot API", version="1.0.0")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Data Schemas
# ---------------------------------------------------------------------------

class LeadCreateRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    intent: Optional[str] = "General inquiry"
    organization: Optional[str] = ""

class ChatRequest(BaseModel):
    session_id: str
    lead_id: int
    question: str
    model: Optional[str] = DEFAULT_CHAT_MODEL

class TrainingCreateRequest(BaseModel):
    question: str
    answer: str
    category: Optional[str] = ""
    tags: Optional[str] = ""

def verify_admin_auth(x_admin_password: Optional[str] = Header(None)):
    from config import ADMIN_PASSWORD
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not configured in .env")
    if not x_admin_password or x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized admin password")
    return x_admin_password

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Redirect root access to static index.html UI."""
    return RedirectResponse(url="/static/index.html")

@app.post("/api/leads")
def capture_lead(req: LeadCreateRequest):
    """Register or resolve lead details and return session metadata."""
    if not req.name.strip() or not req.phone.strip():
        raise HTTPException(status_code=400, detail="Name and phone are required.")
    
    try:
        lead = lead_service.find_or_create_lead(
            name=req.name.strip(),
            phone=req.phone.strip(),
            email=req.email.strip(),
            intent=req.intent,
            organization=req.organization.strip()
        )
        
        # Ensure a session is registered
        session_id = chat_service.generate_session_id()
        chat_service.get_or_create_session(session_id, lead.id)
        
        # Fetch dynamic scoring/intent stats
        scoring = lead_service.calculate_lead_score_and_intent(lead.id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "organization": lead.organization,
                "intent": lead.intent,
                "status": lead.status,
                "score": scoring["score"],
                "rating": scoring["rating"]
            }
        }
    except Exception as exc:
        logger.exception("Failed to capture lead")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/chat")
def run_chat(req: ChatRequest):
    """Execute RAG question-answering, persist messages, and generate optional email draft."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    try:
        # Check active session or create
        chat_service.get_or_create_session(req.session_id, req.lead_id)
        
        # Persist user message
        chat_service.persist_message(
            session_id=req.session_id,
            role="user",
            content=req.question.strip()
        )
        
        # Search & complete response
        answer, citations = chat_service.answer_question(
            req.question.strip(), req.model
        )
        
        # Persist assistant response
        chat_service.persist_message(
            session_id=req.session_id,
            role="assistant",
            content=answer,
            citations=citations,
            model=req.model
        )
        
        # Touch lead activity timestamps
        lead_service.update_lead_activity(req.lead_id)
        
        return {
            "answer": answer,
            "citations": citations,
            "model": req.model
        }
    except Exception as exc:
        logger.exception("Chat query execution failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/status")
def get_system_status():
    """Verify live system component health."""
    try:
        # Check ChromaDB connectivity
        from database import get_vector_store
        vector_store = get_vector_store()
        chroma_active = vector_store is not None
    except Exception:
        chroma_active = False

    return {
        "rag_pipeline": "Active",
        "chromadb": "Connected" if chroma_active else "Disconnected",
        "llm": "Connected",
        "embeddings": "Active"
    }

# ---------------------------------------------------------------------------
# Admin Panel Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/admin/metrics", dependencies=[Depends(verify_admin_auth)])
def get_admin_metrics():
    """Compile stats metrics telemetry for the administrator dashboard."""
    leads = lead_service.list_leads()
    sessions = admin_service.get_active_users_data()
    docs = document_service.list_tracked_documents()
    training = training_service.list_training_entries()
    
    total_messages = 0
    for s in sessions:
        total_messages += s.get("message_count", 0)

    return {
        "total_leads": len(leads),
        "active_users": len([s for s in sessions if s.get("is_active")]),
        "conversations_today": len(sessions),
        "trained_docs": len(docs),
        "total_messages": total_messages,
        "faq_entries": len(training)
    }

@app.get("/api/admin/sessions", dependencies=[Depends(verify_admin_auth)])
def get_active_sessions():
    """List session streams with active status calculations."""
    return admin_service.get_active_users_data()

@app.get("/api/admin/leads", dependencies=[Depends(verify_admin_auth)])
def get_leads_crm():
    """Fetch complete list of captured business leads with scores and ratings."""
    leads = lead_service.list_leads()
    leads_list = []
    for lead in leads:
        scoring = lead_service.calculate_lead_score_and_intent(lead.id)
        conversations = lead_service.get_lead_conversations(lead.id)
        leads_list.append({
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "organization": lead.organization,
            "intent": lead.intent,
            "status": lead.status,
            "notes": lead.notes,
            "first_seen_at": lead.first_seen_at,
            "last_seen_at": lead.last_seen_at,
            "score": scoring["score"],
            "rating": scoring["rating"],
            "detected_intent": scoring["detected_intent"],
            "conversations": conversations
        })
    return leads_list

@app.post("/api/admin/leads/{lead_id}/notes", dependencies=[Depends(verify_admin_auth)])
def update_lead_notes(lead_id: int, notes: str = Form(...)):
    """Append administrative notes to a captured lead record."""
    try:
        lead_service.update_lead_notes(lead_id, notes)
        return {"status": "success", "message": "Notes saved."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/admin/leads/{lead_id}/status", dependencies=[Depends(verify_admin_auth)])
def update_lead_status(lead_id: int, status: str = Form(...)):
    """Update commercial pipeline status tag of a lead."""
    try:
        lead_service.update_lead_status(lead_id, status)
        return {"status": "success", "message": f"Status updated to {status}."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/admin/documents", dependencies=[Depends(verify_admin_auth)])
def list_documents():
    """List all tracked knowledge PDF assets."""
    return document_service.list_tracked_documents()

@app.post("/api/admin/documents/upload", dependencies=[Depends(verify_admin_auth)])
def upload_document(file: UploadFile = File(...)):
    """Upload document and trigger chunk ingestion parsing."""
    supported = {".pdf", ".txt", ".docx", ".md", ".csv", ".zip"}
    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in supported):
        raise HTTPException(status_code=400, detail="Only PDF, TXT, DOCX, MD, CSV, and ZIP files are supported.")


    try:
        doc, is_dup = document_service.upload_and_track(file)
        if is_dup:
            return {"status": "duplicate", "message": f"Document '{file.filename}' already exists.", "document": doc}
        
        # Trigger ingestion immediately in background / sync for local simplicity
        count = document_service.ingest_document(doc.id)
        return {"status": "success", "message": f"Ingested {count} chunks.", "document": doc}
    except Exception as exc:
        logger.exception("Injest failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/admin/documents/{doc_id}/reingest", dependencies=[Depends(verify_admin_auth)])
def reingest_document(doc_id: int):
    """Force re-ingestion of parsed vector chunks."""
    try:
        count = document_service.reingest_document(doc_id)
        return {"status": "success", "message": f"Re-ingested {count} chunks."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.delete("/api/admin/documents/{doc_id}", dependencies=[Depends(verify_admin_auth)])
def delete_document(doc_id: int):
    """Delete document files and prune associated Chroma chunks."""
    try:
        document_service.delete_tracked_document(doc_id)
        return {"status": "success", "message": "Document deleted."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/admin/training", dependencies=[Depends(verify_admin_auth)])
def list_training_knowledge():
    """List FAQ active knowledge entries."""
    return training_service.list_training_entries()

@app.post("/api/admin/training", dependencies=[Depends(verify_admin_auth)])
def add_training_faq(req: TrainingCreateRequest):
    """Add new training entry override and sync to ChromaDB."""
    try:
        entry = training_service.add_training_entry(
            question=req.question.strip(),
            answer=req.answer.strip(),
            category=req.category.strip(),
            tags=req.tags.strip()
        )
        return {"status": "success", "entry": entry}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.delete("/api/admin/training/{entry_id}", dependencies=[Depends(verify_admin_auth)])
def delete_training_faq(entry_id: int):
    """Delete training entry and purge vectorized chunks."""
    try:
        training_service.delete_training_entry(entry_id)
        return {"status": "success", "message": "Training entry purged."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---------------------------------------------------------------------------
# Static Web Assets Mounting
# ---------------------------------------------------------------------------

# Static assets directory mapping
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
