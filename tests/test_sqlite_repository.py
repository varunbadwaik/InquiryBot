"""Tests for the SQLite repository layer."""

import unittest

from repositories import sqlite_repository as repo


class SqliteRepositoryTests(unittest.TestCase):
    """Each test method gets a fresh in-memory database."""

    def setUp(self) -> None:
        repo.reset_connection(":memory:")

    def tearDown(self) -> None:
        repo.close_connection()

    # --- Schema ---

    def test_init_db_creates_all_tables(self) -> None:
        conn = repo._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = sorted(row["name"] for row in cursor.fetchall())
        for expected in ["documents", "leads", "messages", "sessions", "training_entries"]:
            self.assertIn(expected, tables)

    # --- Leads ---

    def test_create_lead_and_retrieve_by_phone(self) -> None:
        lead = repo.create_lead(name="Alice", phone="1234567890", email="a@b.com")
        self.assertIsNotNone(lead.id)
        self.assertEqual(lead.name, "Alice")

        found = repo.get_lead_by_phone("1234567890")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, lead.id)
        self.assertEqual(found.name, "Alice")

    def test_get_lead_by_email(self) -> None:
        lead = repo.create_lead(name="Bob", phone="9999999999", email="bob@test.com")
        found = repo.get_lead_by_email("bob@test.com")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, lead.id)

    def test_get_lead_by_email_empty_returns_none(self) -> None:
        repo.create_lead(name="Carol", phone="1111111111", email="")
        found = repo.get_lead_by_email("")
        self.assertIsNone(found)

    def test_find_or_create_lead_creates_new(self) -> None:
        lead = repo.find_or_create_lead(
            name="Dan", phone="5551234567", email="dan@x.com", intent="Services",
        )
        self.assertIsNotNone(lead.id)
        self.assertEqual(lead.name, "Dan")
        self.assertEqual(lead.phone, "5551234567")

    def test_find_or_create_lead_matches_by_phone(self) -> None:
        original = repo.create_lead(name="Eve", phone="5559876543", email="eve@x.com")
        found = repo.find_or_create_lead(
            name="Eve Updated", phone="5559876543", email="new@x.com",
        )
        self.assertEqual(found.id, original.id)

    def test_find_or_create_lead_matches_by_email(self) -> None:
        original = repo.create_lead(
            name="Frank", phone="1112223333", email="frank@x.com",
        )
        found = repo.find_or_create_lead(
            name="Frank", phone="9998887777", email="frank@x.com",
        )
        self.assertEqual(found.id, original.id)

    def test_update_lead_status(self) -> None:
        lead = repo.create_lead(name="Grace", phone="4445556666")
        self.assertEqual(lead.status, "New")
        repo.update_lead_status(lead.id, "Contacted")
        updated = repo.get_lead_by_id(lead.id)
        self.assertEqual(updated.status, "Contacted")

    def test_update_lead_notes(self) -> None:
        lead = repo.create_lead(name="Hank", phone="7778889999")
        repo.update_lead_notes(lead.id, "Important customer")
        updated = repo.get_lead_by_id(lead.id)
        self.assertEqual(updated.notes, "Important customer")

    def test_list_leads(self) -> None:
        repo.create_lead(name="A", phone="1000000001")
        repo.create_lead(name="B", phone="1000000002")
        leads = repo.list_leads()
        self.assertEqual(len(leads), 2)

    # --- Sessions ---

    def test_create_and_get_session(self) -> None:
        lead = repo.create_lead(name="Test", phone="0000000000")
        session = repo.create_session("sess-1", lead.id)
        self.assertEqual(session.id, "sess-1")
        self.assertEqual(session.lead_id, lead.id)

        found = repo.get_session("sess-1")
        self.assertIsNotNone(found)
        self.assertEqual(found.lead_id, lead.id)

    # --- Messages ---

    def test_create_message_and_retrieve(self) -> None:
        lead = repo.create_lead(name="Test", phone="0000000001")
        repo.create_session("sess-2", lead.id)
        msg = repo.create_message(
            session_id="sess-2", role="user", content="Hello",
        )
        self.assertIsNotNone(msg.id)
        self.assertEqual(msg.content, "Hello")

        messages = repo.get_messages_by_session("sess-2")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, "Hello")

    def test_count_messages(self) -> None:
        lead = repo.create_lead(name="Test", phone="0000000002")
        repo.create_session("sess-3", lead.id)
        repo.create_message(session_id="sess-3", role="user", content="Q1")
        repo.create_message(session_id="sess-3", role="assistant", content="A1")
        self.assertEqual(repo.count_messages_by_session("sess-3"), 2)

    def test_message_persistence_with_citations(self) -> None:
        lead = repo.create_lead(name="Test", phone="0000000003")
        repo.create_session("sess-4", lead.id)
        msg = repo.create_message(
            session_id="sess-4",
            role="assistant",
            content="Answer",
            citations_json='[{"doc": "test.pdf"}]',
            model="gpt-4.1-mini",
        )
        found = repo.get_messages_by_session("sess-4")
        self.assertEqual(found[0].citations_json, '[{"doc": "test.pdf"}]')
        self.assertEqual(found[0].model, "gpt-4.1-mini")

    # --- Documents ---

    def test_create_document_and_duplicate_detection(self) -> None:
        doc = repo.create_document(
            file_name="test.pdf",
            file_path="/data/test.pdf",
            file_hash="abc123",
        )
        self.assertIsNotNone(doc.id)

        dup = repo.get_document_by_hash("abc123")
        self.assertIsNotNone(dup)
        self.assertEqual(dup.id, doc.id)

    def test_no_duplicate_for_different_hash(self) -> None:
        repo.create_document(
            file_name="a.pdf", file_path="/data/a.pdf", file_hash="hash1",
        )
        found = repo.get_document_by_hash("hash2")
        self.assertIsNone(found)

    def test_update_document_status(self) -> None:
        doc = repo.create_document(
            file_name="b.pdf", file_path="/data/b.pdf", file_hash="hash_b",
        )
        repo.update_document_status(doc.id, status="ingested", chunk_count=42)
        updated = repo.get_document_by_id(doc.id)
        self.assertEqual(updated.status, "ingested")
        self.assertEqual(updated.chunk_count, 42)

    def test_delete_document_record(self) -> None:
        doc = repo.create_document(
            file_name="c.pdf", file_path="/data/c.pdf", file_hash="hash_c",
        )
        repo.delete_document_record(doc.id)
        self.assertIsNone(repo.get_document_by_id(doc.id))

    # --- Training Entries ---

    def test_create_training_entry(self) -> None:
        entry = repo.create_training_entry(
            question="What is X?",
            answer="X is Y.",
            category="FAQ",
            tags="general",
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.question, "What is X?")
        self.assertEqual(entry.status, "active")

    def test_list_training_entries(self) -> None:
        repo.create_training_entry(question="Q1", answer="A1")
        repo.create_training_entry(question="Q2", answer="A2")
        entries = repo.list_training_entries()
        self.assertEqual(len(entries), 2)

    def test_update_training_entry(self) -> None:
        entry = repo.create_training_entry(question="Old Q", answer="Old A")
        repo.update_training_entry(
            entry.id, question="New Q", answer="New A",
            category="Updated", tags="v2",
        )
        updated = repo.get_training_entry(entry.id)
        self.assertEqual(updated.question, "New Q")
        self.assertEqual(updated.category, "Updated")

    def test_delete_training_entry(self) -> None:
        entry = repo.create_training_entry(question="Del Q", answer="Del A")
        repo.delete_training_entry(entry.id)
        self.assertIsNone(repo.get_training_entry(entry.id))


if __name__ == "__main__":
    unittest.main()
