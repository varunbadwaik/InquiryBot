"""Admin service — data aggregation for the admin panel."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import ACTIVE_USER_TIMEOUT_MINUTES, ADMIN_PASSWORD
from repositories import sqlite_repository as repo


logger = logging.getLogger(__name__)


def authenticate(password: str) -> bool:
    """Check the supplied password against the configured admin password."""
    if not ADMIN_PASSWORD:
        logger.warning("ADMIN_PASSWORD is not set in .env")
        return False
    return password == ADMIN_PASSWORD


def get_active_users_data() -> list[dict[str, Any]]:
    """Return session data with active/inactive status based on timeout."""
    sessions = repo.get_active_sessions(ACTIVE_USER_TIMEOUT_MINUTES)
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=ACTIVE_USER_TIMEOUT_MINUTES)
    ).isoformat()

    for s in sessions:
        last = s.get("last_active_at") or ""
        s["is_active"] = last >= cutoff if last else False

        # Get latest user question as preview
        latest = repo.get_latest_message_by_session(s["session_id"])
        if latest and latest.role == "user":
            s["latest_question"] = (
                latest.content[:100] + "..." if len(latest.content) > 100
                else latest.content
            )
        else:
            # Look for most recent user message
            messages = repo.get_messages_by_session(s["session_id"])
            user_msgs = [m for m in messages if m.role == "user"]
            if user_msgs:
                last_q = user_msgs[-1].content
                s["latest_question"] = (
                    last_q[:100] + "..." if len(last_q) > 100 else last_q
                )
            else:
                s["latest_question"] = ""

    return sessions


def get_chat_history(
    phone: str = "",
    name: str = "",
    session_id: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict[str, Any]]:
    """Return filtered chat history with lead info."""
    return repo.list_messages_filtered(
        phone=phone, name=name, session_id=session_id,
        date_from=date_from, date_to=date_to,
    )


def get_leads_data() -> list[dict[str, Any]]:
    """Return all leads with conversation/message statistics."""
    return repo.get_leads_with_stats()


def export_chat_history_csv(
    phone: str = "",
    name: str = "",
    session_id: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Generate a CSV string of filtered chat history."""
    messages = get_chat_history(
        phone=phone, name=name, session_id=session_id,
        date_from=date_from, date_to=date_to,
    )

    output = io.StringIO()
    fieldnames = [
        "created_at", "session_id", "name", "phone", "email",
        "role", "content", "citations_json", "model", "intent",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for msg in messages:
        writer.writerow(msg)

    return output.getvalue()
