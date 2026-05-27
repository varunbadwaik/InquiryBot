"""Lead service — lead creation, matching, and activity tracking."""

from __future__ import annotations

import logging
from typing import Optional

from models.schemas import Lead
from repositories import sqlite_repository as repo


logger = logging.getLogger(__name__)


def sync_leads_to_csv() -> None:
    """Synchronize all SQLite leads to a local CSV file as a backup/supplement."""
    import csv
    from config import LEADS_FILE
    
    try:
        leads = repo.list_leads()
        with open(LEADS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow([
                "id", "name", "phone", "email", "status", "intent", 
                "notes", "organization", "first_seen_at", "last_seen_at", 
                "created_at", "updated_at"
            ])
            for lead in leads:
                writer.writerow([
                    lead.id, lead.name, lead.phone, lead.email, lead.status, lead.intent,
                    lead.notes, lead.organization, lead.first_seen_at, lead.last_seen_at,
                    lead.created_at, lead.updated_at
                ])
        logger.info("Synchronized %d leads to %s", len(leads), LEADS_FILE)
    except Exception:
        logger.exception("Failed to sync leads to CSV")


def find_or_create_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    intent: str = "",
    organization: str = "",
) -> Lead:
    """Match by phone first, then email; create if no match found."""
    lead = repo.find_or_create_lead(
        name=name, phone=phone, email=email, intent=intent, organization=organization,
    )
    sync_leads_to_csv()
    return lead


def update_lead_activity(lead_id: int) -> None:
    """Touch the lead's last_seen_at timestamp."""
    repo.update_lead_activity(lead_id)
    sync_leads_to_csv()


def get_lead_by_id(lead_id: int) -> Optional[Lead]:
    return repo.get_lead_by_id(lead_id)


def update_lead_status(lead_id: int, status: str) -> None:
    repo.update_lead_status(lead_id, status)
    sync_leads_to_csv()


def update_lead_notes(lead_id: int, notes: str) -> None:
    repo.update_lead_notes(lead_id, notes)
    sync_leads_to_csv()


def list_leads() -> list[Lead]:
    return repo.list_leads()


def get_lead_conversations(lead_id: int) -> list[dict]:
    """Return all sessions and messages for a lead as a timeline."""
    sessions = repo.list_sessions()
    lead_sessions = [s for s in sessions if s.lead_id == lead_id]

    conversations = []
    for session in lead_sessions:
        messages = repo.get_messages_by_session(session.id)
        conversations.append({
            "session_id": session.id,
            "started_at": session.started_at,
            "last_active_at": session.last_active_at,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "citations_json": m.citations_json,
                    "model": m.model,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        })
    return conversations


def calculate_lead_score_and_intent(lead_id: int) -> dict[str, Any]:
    """Calculate a dynamic lead score (0-100) and detected intent category based on active chats.
    
    Scoring logic:
    - Base profile: +10 if name is provided, +20 if email is provided
    - Messages volume: +5 per message, capped at 30 points
    - High-intent keywords: +30 points if user asks pricing/buying/cost details
    - Multi-session engagement: +10 if they started more than 1 session
    """
    lead = repo.get_lead_by_id(lead_id)
    if not lead:
        return {"score": 0, "rating": "Cold", "detected_intent": "Unknown"}

    score = 0
    if lead.name and lead.name.lower() not in ["anonymous", ""]:
        score += 10
    if lead.email and "@" in lead.email:
        score += 20
    if lead.organization and lead.organization.strip():
        score += 10

    conversations = get_lead_conversations(lead_id)
    total_sessions = len(conversations)
    total_messages = sum(len(c["messages"]) for c in conversations)
    
    # Message frequency points
    score += min(total_messages * 5, 30)

    # Multi-engagement points
    if total_sessions > 1:
        score += 10

    # Keyword analysis for intent override and scoring
    has_high_intent = False
    has_support_intent = False
    
    purchasing_keywords = ["price", "pricing", "cost", "quote", "buy", "purchase", "features", "discount", "fee", "sales"]
    support_keywords = ["support", "help", "broken", "error", "bug", "issue", "fail", "wrong", "setup", "configure"]
    
    for conv in conversations:
        for msg in conv["messages"]:
            if msg["role"] == "user":
                content_lower = msg["content"].lower()
                if any(kw in content_lower for kw in purchasing_keywords):
                    has_high_intent = True
                if any(kw in content_lower for kw in support_keywords):
                    has_support_intent = True

    if has_high_intent:
        score += 30
    
    score = min(score, 100)

    # Classify dynamic temperature rating
    if score >= 70:
        rating = "🔥 Hot"
    elif score >= 35:
        rating = "☀️ Warm"
    else:
        rating = "❄️ Cold"

    # Classify dynamic intent based on content
    detected_intent = lead.intent or "General inquiry"
    if has_high_intent:
        detected_intent = "Pricing / Commercial"
    elif has_support_intent:
        detected_intent = "Customer Support"

    return {
        "score": score,
        "rating": rating,
        "detected_intent": detected_intent
    }
