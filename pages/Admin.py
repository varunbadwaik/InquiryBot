"""InquiryBot Admin Panel.

Accessible as a Streamlit multipage under pages/Admin.py.
Requires ADMIN_PASSWORD authentication.
"""

import json
import logging

import streamlit as st

from config import ADMIN_PASSWORD
from repositories import sqlite_repository as repo
from services import admin_service, document_service, lead_service, training_service
from utils import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

# Ensure DB is initialised.
repo.init_db()

st.set_page_config(page_title="InquiryBot Admin", layout="wide")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False


def do_logout():
    st.session_state.admin_authenticated = False


if not st.session_state.admin_authenticated:
    st.title("🔒 Admin Login")

    if not ADMIN_PASSWORD:
        st.error(
            "ADMIN_PASSWORD is not configured. Set it in your `.env` file "
            "before using the admin panel."
        )
        st.stop()

    with st.form("admin_login"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if admin_service.authenticate(password):
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("Invalid password.")

    st.stop()


# ---------------------------------------------------------------------------
# Authenticated admin area
# ---------------------------------------------------------------------------

st.title("📊 InquiryBot Admin Panel")

with st.sidebar:
    st.markdown("**Admin Panel**")
    if st.button("🚪 Logout"):
        do_logout()
        st.rerun()

tab_users, tab_history, tab_leads, tab_files, tab_training = st.tabs([
    "👥 Active Users",
    "💬 Chat History",
    "🎯 Leads",
    "📄 File Training",
    "🧠 Chat Training",
])


# ---------------------------------------------------------------------------
# TAB A: Active Users
# ---------------------------------------------------------------------------

with tab_users:
    st.subheader("Active Users")
    col_ref1, col_ref2 = st.columns([1, 4])
    with col_ref1:
        if st.button("🔄 Refresh", key="refresh_users"):
            st.rerun()
    with col_ref2:
        auto_refresh = st.checkbox("Enable Auto-Refresh (every 15s)", value=False, key="auto_refresh_users")

    if auto_refresh:
        # Import time and set sleep for a lightweight native auto-refresh loop
        import time
        st.caption("Auto-refresh active. Next update in 15 seconds...")
        time.sleep(15)
        st.rerun()

    users = admin_service.get_active_users_data()

    if not users:
        st.info("No user sessions found.")
    else:
        for user in users:
            status = "🟢 Active" if user.get("is_active") else "⚪ Inactive"
            col1, col2, col3, col4 = st.columns([2, 2, 1, 3])
            with col1:
                st.markdown(f"**{user['name'] or 'Unknown'}**")
                st.caption(f"📱 {user['phone'] or 'N/A'}")
            with col2:
                st.caption(f"📧 {user['email'] or 'N/A'}")
                st.caption(f"🆔 `{user['session_id'][:8]}...`")
            with col3:
                st.markdown(status)
                st.caption(f"💬 {user['message_count']} msgs")
            with col4:
                if user.get("latest_question"):
                    st.caption(f"Last Q: {user['latest_question']}")
                if user.get("last_message_at"):
                    st.caption(f"Last: {user['last_message_at'][:19]}")
            st.divider()


# ---------------------------------------------------------------------------
# TAB B: Chat History
# ---------------------------------------------------------------------------

with tab_history:
    st.subheader("Chat History")

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_phone = st.text_input("Filter by phone", key="hist_phone")
    with col2:
        filter_name = st.text_input("Filter by name", key="hist_name")
    with col3:
        filter_session = st.text_input("Filter by session ID", key="hist_session")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_from = st.date_input("From date", value=None, key="hist_from")
    with col_d2:
        date_to = st.date_input("To date", value=None, key="hist_to")

    date_from_str = date_from.isoformat() if date_from else ""
    date_to_str = date_to.isoformat() + "T23:59:59" if date_to else ""

    messages = admin_service.get_chat_history(
        phone=filter_phone,
        name=filter_name,
        session_id=filter_session,
        date_from=date_from_str,
        date_to=date_to_str,
    )

    if messages:
        st.caption(f"{len(messages)} messages found")

        # CSV export
        csv_data = admin_service.export_chat_history_csv(
            phone=filter_phone,
            name=filter_name,
            session_id=filter_session,
            date_from=date_from_str,
            date_to=date_to_str,
        )
        st.download_button(
            "📥 Export CSV",
            data=csv_data,
            file_name="chat_history.csv",
            mime="text/csv",
        )

        # Group by session for conversation view
        sessions_grouped: dict[str, list] = {}
        for msg in messages:
            sid = msg["session_id"]
            if sid not in sessions_grouped:
                sessions_grouped[sid] = []
            sessions_grouped[sid].append(msg)

        for sid, msgs in sessions_grouped.items():
            first = msgs[-1] if msgs else {}
            label = (
                f"Session `{sid[:8]}...` — "
                f"{first.get('name', 'Unknown')} "
                f"({first.get('phone', 'N/A')})"
            )
            with st.expander(label):
                for msg in reversed(msgs):
                    role_icon = "👤" if msg["role"] == "user" else "🤖"
                    st.markdown(
                        f"{role_icon} **{msg['role'].title()}** "
                        f"({msg['created_at'][:19]})"
                    )
                    st.markdown(msg["content"])
                    if msg["citations_json"] and msg["citations_json"] != "[]":
                        try:
                            cites = json.loads(msg["citations_json"])
                            if cites:
                                st.caption(
                                    f"Citations: {', '.join(c.get('document_name', '') for c in cites)}"
                                )
                        except json.JSONDecodeError:
                            pass
                    if msg.get("model"):
                        st.caption(f"Model: {msg['model']}")
                    st.divider()
    else:
        st.info("No messages found with the current filters.")


# ---------------------------------------------------------------------------
# TAB C: Leads Tracking
# ---------------------------------------------------------------------------

with tab_leads:
    st.subheader("Leads")

    leads_data = admin_service.get_leads_data()

    if not leads_data:
        st.info("No leads captured yet.")
    else:
        for lead in leads_data:
            # Calculate dynamic lead score and detected intent
            scoring = lead_service.calculate_lead_score_and_intent(lead["id"])
            
            with st.expander(
                f"#{lead['id']} — {lead['name'] or 'Unknown'} "
                f"| 📱 {lead['phone'] or 'N/A'} "
                f"| Status: {lead['status']} "
                f"| Score: {scoring['score']} ({scoring['rating']})"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Name:** {lead['name']}")
                    st.markdown(f"**Phone:** {lead['phone']}")
                    st.markdown(f"**Email:** {lead['email'] or 'N/A'}")
                    st.markdown(f"**Stated Intent:** {lead['intent'] or 'N/A'}")
                    st.markdown(f"**Detected Intent:** {scoring['detected_intent']}")
                with col2:
                    st.markdown(f"**Lead Score:** {scoring['score']}/100 ({scoring['rating']})")
                    st.markdown(f"**First seen:** {(lead['first_seen_at'] or '')[:19]}")
                    st.markdown(f"**Last seen:** {(lead['last_seen_at'] or '')[:19]}")
                    st.markdown(f"**Conversations:** {lead['total_conversations']} | **Messages:** {lead['total_messages']}")

                # Editable status
                status_options = [
                    "New", "Contacted", "Qualified", "Converted", "Closed",
                ]
                current_idx = (
                    status_options.index(lead["status"])
                    if lead["status"] in status_options else 0
                )
                new_status = st.selectbox(
                    "Status",
                    status_options,
                    index=current_idx,
                    key=f"lead_status_{lead['id']}",
                )
                if new_status != lead["status"]:
                    lead_service.update_lead_status(lead["id"], new_status)
                    st.success(f"Status updated to {new_status}")
                    st.rerun()

                # Editable notes
                new_notes = st.text_area(
                    "Notes",
                    value=lead.get("notes", ""),
                    key=f"lead_notes_{lead['id']}",
                )
                if st.button("Save Notes", key=f"save_notes_{lead['id']}"):
                    lead_service.update_lead_notes(lead["id"], new_notes)
                    st.success("Notes saved.")

                # Conversation timeline
                st.markdown("---")
                st.markdown("**Conversation Timeline**")
                conversations = lead_service.get_lead_conversations(lead["id"])
                if conversations:
                    for conv in conversations:
                        st.caption(
                            f"Session `{conv['session_id'][:8]}...` — "
                            f"{conv['started_at'][:19] if conv['started_at'] else 'N/A'}"
                        )
                        for msg in conv["messages"]:
                            role_icon = "👤" if msg["role"] == "user" else "🤖"
                            st.text(
                                f"  {role_icon} [{msg['created_at'][:19]}] "
                                f"{msg['content'][:120]}"
                            )
                else:
                    st.caption("No conversations yet.")


# ---------------------------------------------------------------------------
# TAB D: File Training
# ---------------------------------------------------------------------------

with tab_files:
    st.subheader("Document Management")

    # Upload new Document
    st.markdown("#### Upload Knowledge Document")
    uploaded = st.file_uploader(
        "Choose a file (PDF, TXT, DOCX, MD, CSV, ZIP)",
        type=["pdf", "txt", "docx", "md", "csv", "zip"],
        accept_multiple_files=False,
        key="admin_document_upload",
    )


    if uploaded:
        if st.button("Upload & Track", key="upload_track"):
            try:
                doc, is_dup = document_service.upload_and_track(uploaded)
                if is_dup:
                    st.warning(
                        f"Duplicate detected: '{doc.file_name}' (hash: {doc.file_hash[:12]}...) "
                        f"already exists as document #{doc.id}."
                    )
                else:
                    st.success(f"Uploaded '{doc.file_name}' (ID: {doc.id})")
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

    st.markdown("---")

    # Rebuild vector DB
    if st.button("🔄 Rebuild entire vector database", key="rebuild_vdb"):
        try:
            with st.spinner("Rebuilding Chroma database..."):
                count = document_service.rebuild_all()
            st.success(f"Rebuilt vector database with {count} chunks.")
        except Exception as exc:
            st.error(f"Rebuild failed: {exc}")

    st.markdown("---")

    # List tracked documents
    st.markdown("#### Tracked Documents")
    docs = document_service.list_tracked_documents()

    if not docs:
        st.info("No documents tracked yet.")
    else:
        for doc in docs:
            status_icon = {
                "uploaded": "📤",
                "ingesting": "⏳",
                "ingested": "✅",
                "error": "❌",
            }.get(doc.status, "❓")

            with st.expander(
                f"{status_icon} {doc.file_name} — {doc.status} "
                f"({doc.chunk_count} chunks)"
            ):
                st.markdown(f"**ID:** {doc.id}")
                st.markdown(f"**Hash:** `{doc.file_hash[:16]}...`")
                st.markdown(f"**Path:** `{doc.file_path}`")
                st.markdown(f"**Uploaded:** {(doc.uploaded_at or '')[:19]}")
                st.markdown(f"**Ingested:** {(doc.ingested_at or '')[:19]}")
                if doc.error_message:
                    st.error(f"Error: {doc.error_message}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("▶️ Ingest", key=f"ingest_{doc.id}"):
                        try:
                            with st.spinner("Ingesting..."):
                                count = document_service.ingest_document(doc.id)
                            st.success(f"Ingested {count} chunks")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Ingestion failed: {exc}")
                with col2:
                    if st.button("🔁 Re-ingest", key=f"reingest_{doc.id}"):
                        try:
                            with st.spinner("Re-ingesting..."):
                                count = document_service.reingest_document(doc.id)
                            st.success(f"Re-ingested {count} chunks")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Re-ingestion failed: {exc}")
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_{doc.id}"):
                        document_service.delete_tracked_document(doc.id)
                        st.success("Document deleted.")
                        st.rerun()


# ---------------------------------------------------------------------------
# TAB E: Chat Training (FAQ)
# ---------------------------------------------------------------------------

with tab_training:
    st.subheader("FAQ / Knowledge Training")
    st.markdown(
        "Add question-answer pairs that the chatbot can use for retrieval. "
        "These entries are automatically ingested into the vector database."
    )

    # Add new entry form
    st.markdown("#### Add New Entry")
    with st.form("add_training"):
        t_question = st.text_area("Question *", placeholder="What is your return policy?")
        t_answer = st.text_area(
            "Answer *",
            placeholder="Our return policy allows returns within 30 days...",
        )
        t_category = st.text_input("Category", placeholder="e.g. Policy, FAQ, Product")
        t_tags = st.text_input("Tags (comma-separated)", placeholder="returns, refund")
        t_submitted = st.form_submit_button("Add Training Entry")

    if t_submitted:
        if not t_question.strip() or not t_answer.strip():
            st.error("Question and answer are required.")
        else:
            try:
                entry = training_service.add_training_entry(
                    question=t_question.strip(),
                    answer=t_answer.strip(),
                    category=t_category.strip(),
                    tags=t_tags.strip(),
                )
                st.success(f"Training entry #{entry.id} created and ingested!")
            except Exception as exc:
                st.error(f"Failed to add training entry: {exc}")

    st.markdown("---")

    # Reindex all
    if st.button("🔄 Reindex all training entries", key="reindex_training"):
        try:
            with st.spinner("Reindexing..."):
                count = training_service.reindex_all_training()
            st.success(f"Reindexed {count} training entries.")
        except Exception as exc:
            st.error(f"Reindex failed: {exc}")

    st.markdown("---")

    # List existing entries
    st.markdown("#### Existing Training Entries")
    entries = training_service.list_training_entries()

    if not entries:
        st.info("No training entries yet.")
    else:
        for entry in entries:
            with st.expander(
                f"#{entry.id} — {entry.question[:60]}{'...' if len(entry.question) > 60 else ''} "
                f"[{entry.category or 'Uncategorized'}]"
            ):
                st.markdown(f"**Question:** {entry.question}")
                st.markdown(f"**Answer:** {entry.answer}")
                st.markdown(f"**Category:** {entry.category or 'N/A'}")
                st.markdown(f"**Tags:** {entry.tags or 'N/A'}")
                st.markdown(f"**Status:** {entry.status}")
                st.markdown(f"**Created:** {(entry.created_at or '')[:19]}")

                # Edit form
                with st.form(f"edit_training_{entry.id}"):
                    e_question = st.text_area("Question", value=entry.question)
                    e_answer = st.text_area("Answer", value=entry.answer)
                    e_category = st.text_input("Category", value=entry.category)
                    e_tags = st.text_input("Tags", value=entry.tags)
                    e_submitted = st.form_submit_button("Update & Re-ingest")

                if e_submitted:
                    try:
                        training_service.update_training_entry(
                            entry_id=entry.id,
                            question=e_question.strip(),
                            answer=e_answer.strip(),
                            category=e_category.strip(),
                            tags=e_tags.strip(),
                        )
                        st.success(f"Entry #{entry.id} updated and re-ingested!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

                if st.button("🗑️ Delete", key=f"del_training_{entry.id}"):
                    training_service.delete_training_entry(entry.id)
                    st.success(f"Entry #{entry.id} deleted.")
                    st.rerun()
