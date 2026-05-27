"""Chat service — retrieval, LLM completion, and message persistence."""

from __future__ import annotations

import json
import logging
import time
import uuid

from openai import OpenAI, APIError, APIStatusError

from config import (
    DEFAULT_CHAT_MODEL,
    REFUSAL_MESSAGE,
    RETRIEVAL_K,
    SIMILARITY_SCORE_THRESHOLD,
)
from database import get_vector_store, retrieve_relevant_documents
from repositories import sqlite_repository as repo
from utils import citation_payload, format_documents_for_prompt


logger = logging.getLogger(__name__)

# Fallback model chain — tried in order when the primary model is unavailable.
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10  # seconds — free tier often needs 20-50s cooldown


ANSWER_SYSTEM_PROMPT = f"""You are InquiryBot, a careful business document assistant.

STRICT RULES:
1. Answer ONLY using the provided context documents below.
2. If the context does not contain enough information to answer, reply EXACTLY with:
   "{REFUSAL_MESSAGE}"
3. NEVER fabricate, assume, or infer information not explicitly present in the context.
4. When referencing information, mention the source document name or number.
5. Keep answers concise, professional, and directly relevant to the question.
6. If the question is ambiguous, ask for clarification rather than guessing.
7. Do NOT answer questions about topics unrelated to the provided documents.
"""


def _call_llm(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
    """Single LLM call (no retry)."""
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def _parse_retry_delay(exc: Exception) -> float | None:
    """Extract the suggested retry delay from a Google AI Studio error, if present."""
    import re
    body = getattr(exc, "body", None) or str(exc)
    text = str(body)
    match = re.search(r"[Rr]etry in (\d+(?:\.\d+)?)s", text)
    if match:
        return float(match.group(1))
    return None


def complete_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    """Call Google AI Studio with retry + automatic model fallback on 503/429."""
    client = OpenAI()

    # Build ordered list: requested model first, then fallbacks (no duplicates).
    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

    last_exc = None
    for current_model in models_to_try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = _call_llm(client, current_model, system_prompt, user_prompt)
                if current_model != model:
                    logger.info(
                        "Succeeded with fallback model %s (original: %s)",
                        current_model, model,
                    )
                return result
            except (APIStatusError, APIError) as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                if status in (503, 429):
                    # Use the API's suggested delay if available, else exponential backoff.
                    api_delay = _parse_retry_delay(exc)
                    delay = api_delay if api_delay else RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    # Cap at 60s to avoid very long waits.
                    delay = min(delay, 60)
                    logger.warning(
                        "Model %s returned %s (attempt %d/%d). "
                        "Retrying in %.1fs...",
                        current_model, status, attempt, MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                else:
                    raise  # Non-retryable error — propagate immediately.

        logger.warning(
            "All %d retries exhausted for model %s. Trying next fallback...",
            MAX_RETRIES, current_model,
        )

    # All models failed — raise with a user-friendly message.
    raise RuntimeError(
        f"All models unavailable after retries. Tried: {models_to_try}. "
        "Google AI Studio may be experiencing high demand — please try again shortly."
    )


def answer_question(question: str, model: str) -> tuple[str, list[dict]]:
    """Retrieve context and generate an answer with citations."""
    vector_store = get_vector_store()
    retrieved = retrieve_relevant_documents(
        question,
        vector_store=vector_store,
        k=RETRIEVAL_K,
        score_threshold=SIMILARITY_SCORE_THRESHOLD,
    )

    if not retrieved:
        return REFUSAL_MESSAGE, []

    docs = [doc for doc, _score in retrieved]
    citations = [citation_payload(doc, score) for doc, score in retrieved]
    user_prompt = (
        f"Refusal message:\n{REFUSAL_MESSAGE}\n\n"
        f"Context:\n{format_documents_for_prompt(docs)}\n\n"
        f"Question:\n{question}\n\n"
        "Answer:"
    )
    answer = complete_chat(model, ANSWER_SYSTEM_PROMPT, user_prompt)
    return answer, citations


def generate_email_draft(
    question: str,
    answer: str,
    model: str,
    name: str,
    email: str,
    intent: str,
) -> str:
    """Draft a professional email based on the Q&A exchange."""
    user_prompt = (
        "Draft a concise professional email based on the user's inquiry and the "
        "document-grounded answer.\n\n"
        f"Lead name: {name or 'Prospective customer'}\n"
        f"Lead email: {email or 'Not provided'}\n"
        f"Intent: {intent or 'General inquiry'}\n"
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        "Email draft:"
    )
    return complete_chat(model, "You write clear business emails.", user_prompt)


def persist_message(
    session_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    model: str = "",
) -> None:
    """Save a chat message to SQLite."""
    citations_json = json.dumps(citations) if citations else "[]"
    try:
        repo.create_message(
            session_id=session_id,
            role=role,
            content=content,
            citations_json=citations_json,
            model=model,
        )
        repo.update_session_active(session_id)
    except Exception:
        logger.exception("Failed to persist message for session %s", session_id)


def generate_session_id() -> str:
    """Return a new UUID4 session identifier."""
    return str(uuid.uuid4())


def get_or_create_session(session_id: str, lead_id: int) -> str:
    """Ensure a session record exists for the given ID and lead."""
    existing = repo.get_session(session_id)
    if existing is None:
        repo.create_session(session_id, lead_id)
    return session_id
