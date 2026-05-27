"""InquiryBot — Streamlit RAG chatbot UI.

Run with:  streamlit run chatbot.py
"""

import logging

import streamlit as st
from dotenv import load_dotenv

from config import (
    CHAT_MODEL_CHOICES,
    DEFAULT_CHAT_MODEL,
    REFUSAL_MESSAGE,
)
from repositories import sqlite_repository as repo
from services import chat_service, lead_service
from utils import setup_logging, validate_phone


load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Ensure SQLite tables exist on startup.
repo.init_db()


# ---------------------------------------------------------------------------
# Citation display
# ---------------------------------------------------------------------------

def display_citations(citations: list[dict]) -> None:
    if not citations:
        return

    st.markdown("**Sources**")
    for index, citation in enumerate(citations, start=1):
        label = f"{index}. {citation['document_name']}"
        if citation.get("page_number"):
            label += f" - page {citation['page_number']}"
        if citation.get("score") is not None:
            label += f" - relevance {citation['score']:.2f}"
        if citation.get("source_type") == "admin_training":
            label += " *(Admin Training)*"

        with st.expander(label):
            st.write(citation["chunk_text"])


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="InquiryBot RAG", layout="wide")
st.title("InquiryBot")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = chat_service.generate_session_id()

if "lead_captured" not in st.session_state:
    st.session_state.lead_captured = False

if "lead_id" not in st.session_state:
    st.session_state.lead_id = None

if "lead_name" not in st.session_state:
    st.session_state.lead_name = ""

if "lead_phone" not in st.session_state:
    st.session_state.lead_phone = ""

if "lead_email" not in st.session_state:
    st.session_state.lead_email = ""

if "lead_intent" not in st.session_state:
    st.session_state.lead_intent = "General inquiry"

if "lead_organization" not in st.session_state:
    st.session_state.lead_organization = ""


# ---------------------------------------------------------------------------
# Sidebar — model selection + lead info display
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    selected_model = st.selectbox(
        "Google AI model",
        CHAT_MODEL_CHOICES,
        index=CHAT_MODEL_CHOICES.index(DEFAULT_CHAT_MODEL)
        if DEFAULT_CHAT_MODEL in CHAT_MODEL_CHOICES
        else 0,
    )

    if st.session_state.lead_captured:
        st.divider()
        st.subheader("Your Info")
        st.text(f"Name: {st.session_state.lead_name}")
        st.text(f"Phone: {st.session_state.lead_phone}")
        if st.session_state.lead_email:
            st.text(f"Email: {st.session_state.lead_email}")
        if st.session_state.lead_organization:
            st.text(f"Organization: {st.session_state.lead_organization}")
        st.text(f"Intent: {st.session_state.lead_intent}")

    create_email_draft = st.checkbox("Generate email draft for each answer")

    if st.button("Clear chat history"):
        st.session_state.messages = []
        st.session_state.session_id = chat_service.generate_session_id()
        st.rerun()


# ---------------------------------------------------------------------------
# Lead capture form (shown before chat if not yet captured)
# ---------------------------------------------------------------------------

if not st.session_state.lead_captured:
    st.markdown("### Welcome! Please provide your details to get started.")
    st.markdown("*Phone number is required. Email is optional.*")

    with st.form("lead_capture_form"):
        name = st.text_input("Name *", placeholder="Your full name")
        phone = st.text_input("Phone *", placeholder="e.g. +1 555 123 4567")
        email = st.text_input("Email (optional)", placeholder="you@example.com")
        organization = st.text_input("Organization (optional)", placeholder="e.g. TechNova Solutions")
        intent = st.selectbox(
            "What brings you here?",
            ["General inquiry", "Services", "Portfolio", "Pricing", "Contact", "Support"],
        )
        submitted = st.form_submit_button("Start Chat")

    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
        elif not phone.strip():
            st.error("Phone number is required.")
        elif not validate_phone(phone.strip()):
            st.error("Please enter a valid phone number (at least 7 digits).")
        else:
            lead = lead_service.find_or_create_lead(
                name=name.strip(),
                phone=phone.strip(),
                email=email.strip(),
                intent=intent,
                organization=organization.strip(),
            )
            st.session_state.lead_captured = True
            st.session_state.lead_id = lead.id
            st.session_state.lead_name = lead.name
            st.session_state.lead_phone = lead.phone
            st.session_state.lead_email = lead.email or email.strip()
            st.session_state.lead_organization = lead.organization or organization.strip()
            st.session_state.lead_intent = intent

            # Create session record
            chat_service.get_or_create_session(
                st.session_state.session_id, lead.id,
            )

            # Restore previous messages for returning users
            prev_sessions = lead_service.get_lead_conversations(lead.id)
            if prev_sessions:
                st.toast(f"Welcome back, {lead.name}!", icon="👋")

            st.rerun()

    st.stop()


# ---------------------------------------------------------------------------
# Ensure session record exists
# ---------------------------------------------------------------------------

if st.session_state.lead_id:
    chat_service.get_or_create_session(
        st.session_state.session_id, st.session_state.lead_id,
    )


# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("citations"):
            display_citations(message["citations"])
        if message.get("email_draft"):
            st.markdown("**Email draft**")
            st.code(message["email_draft"], language="markdown")


# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

if question := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Persist user message
    chat_service.persist_message(
        session_id=st.session_state.session_id,
        role="user",
        content=question,
    )

    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching documents..."):
                answer, citations = chat_service.answer_question(
                    question, selected_model,
                )

            st.markdown(answer)
            display_citations(citations)

            email_draft = None
            if create_email_draft and answer != REFUSAL_MESSAGE:
                with st.spinner("Drafting email..."):
                    email_draft = chat_service.generate_email_draft(
                        question=question,
                        answer=answer,
                        model=selected_model,
                        name=st.session_state.lead_name,
                        email=st.session_state.lead_email,
                        intent=st.session_state.lead_intent,
                    )
                st.markdown("**Email draft**")
                st.code(email_draft, language="markdown")

            # Persist assistant message
            chat_service.persist_message(
                session_id=st.session_state.session_id,
                role="assistant",
                content=answer,
                citations=citations,
                model=selected_model,
            )

            # Update lead activity
            if st.session_state.lead_id:
                lead_service.update_lead_activity(st.session_state.lead_id)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                    "email_draft": email_draft,
                }
            )
        except Exception as exc:
            logger.exception("Query failed")
            st.error(f"Could not answer the question: {exc}")
            st.error("Check your API key, model availability on Google AI Studio, and Chroma database.")
