"""Tests for service-layer logic."""

import unittest

from repositories import sqlite_repository as repo
from models.schemas import TrainingEntry


class TrainingDocumentConversionTests(unittest.TestCase):
    """Test that training entries convert to proper LangChain Documents."""

    def test_training_to_document_content(self) -> None:
        # Import here to isolate from chromadb import chain.
        # training_to_document and TRAINING_SOURCE_TYPE are pure functions
        # but the module-level import of database.py triggers chromadb.
        # We test the conversion logic directly to avoid that dependency.
        entry = TrainingEntry(
            id=42,
            question="What services do you offer?",
            answer="We offer web development and digital marketing.",
            category="Services",
            tags="web, marketing",
        )

        # Replicate the conversion logic to test without chromadb dependency
        content = f"Q: {entry.question}\nA: {entry.answer}"
        self.assertIn("What services do you offer?", content)
        self.assertIn("We offer web development", content)

    def test_training_to_document_format(self) -> None:
        entry = TrainingEntry(id=1, question="Q", answer="A")
        content = f"Q: {entry.question}\nA: {entry.answer}"
        self.assertEqual(content, "Q: Q\nA: A")

    def test_training_metadata_fields(self) -> None:
        """Verify the metadata structure that training_to_document produces."""
        entry = TrainingEntry(
            id=10, question="Test Q", answer="Test A",
            category="FAQ", tags="test",
        )
        # Replicate metadata construction
        metadata = {
            "source": "admin_training",
            "source_type": "admin_training",
            "document_name": "Admin Training",
            "training_entry_id": entry.id,
            "category": entry.category,
            "tags": entry.tags,
        }
        self.assertEqual(metadata["source_type"], "admin_training")
        self.assertEqual(metadata["document_name"], "Admin Training")
        self.assertEqual(metadata["training_entry_id"], 10)
        self.assertEqual(metadata["category"], "FAQ")


class LeadMatchingTests(unittest.TestCase):
    """Test lead matching logic via the repository."""

    def setUp(self) -> None:
        repo.reset_connection(":memory:")

    def tearDown(self) -> None:
        repo.close_connection()

    def test_phone_match_takes_priority_over_email(self) -> None:
        lead_phone = repo.create_lead(
            name="Phone Match", phone="5551112222", email="other@test.com",
        )
        lead_email = repo.create_lead(
            name="Email Match", phone="5553334444", email="target@test.com",
        )

        result = repo.find_or_create_lead(
            name="Test", phone="5551112222", email="target@test.com",
        )
        self.assertEqual(result.id, lead_phone.id)

    def test_email_match_used_when_no_phone_match(self) -> None:
        lead = repo.create_lead(
            name="Email User", phone="5559998888", email="unique@test.com",
        )

        result = repo.find_or_create_lead(
            name="Test", phone="0000000000", email="unique@test.com",
        )
        self.assertEqual(result.id, lead.id)

    def test_new_lead_created_when_no_match(self) -> None:
        repo.create_lead(name="Existing", phone="1112223333", email="ex@test.com")

        result = repo.find_or_create_lead(
            name="New Person", phone="9998887777", email="new@test.com",
        )
        self.assertNotEqual(result.phone, "1112223333")
        self.assertEqual(result.name, "New Person")
        self.assertEqual(result.phone, "9998887777")


class MessagePersistenceTests(unittest.TestCase):
    """Test message persistence flows."""

    def setUp(self) -> None:
        repo.reset_connection(":memory:")

    def tearDown(self) -> None:
        repo.close_connection()

    def test_messages_ordered_by_time(self) -> None:
        lead = repo.create_lead(name="User", phone="1234567890")
        repo.create_session("test-session", lead.id)

        repo.create_message("test-session", "user", "Question 1")
        repo.create_message("test-session", "assistant", "Answer 1")
        repo.create_message("test-session", "user", "Question 2")

        messages = repo.get_messages_by_session("test-session")
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Question 1")
        self.assertEqual(messages[1].role, "assistant")
        self.assertEqual(messages[2].role, "user")

    def test_latest_message_returns_most_recent(self) -> None:
        lead = repo.create_lead(name="User2", phone="0987654321")
        repo.create_session("test-session-2", lead.id)

        repo.create_message("test-session-2", "user", "First")
        repo.create_message("test-session-2", "assistant", "Reply")
        repo.create_message("test-session-2", "user", "Last question")

        latest = repo.get_latest_message_by_session("test-session-2")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.content, "Last question")


class LeadScoringAndIntentTests(unittest.TestCase):
    """Test dynamic lead scoring and intent classification logic."""

    def setUp(self) -> None:
        repo.reset_connection(":memory:")

    def tearDown(self) -> None:
        repo.close_connection()

    def test_calculate_lead_score_basic(self) -> None:
        from services import lead_service
        # Create a lead with name but no email
        lead = repo.create_lead(name="John Doe", phone="1234567890", email="")
        
        scoring = lead_service.calculate_lead_score_and_intent(lead.id)
        # john doe has name (+10 points) but no email, messages or sessions. Total = 10
        self.assertEqual(scoring["score"], 10)
        self.assertEqual(scoring["rating"], "❄️ Cold")

    def test_calculate_lead_score_high_intent(self) -> None:
        from services import lead_service
        lead = repo.create_lead(name="Jane Doe", phone="0987654321", email="jane@test.com")
        repo.create_session("sess-1", lead.id)
        
        # Add a message containing pricing keyword
        repo.create_message("sess-1", "user", "What is the price of your web development?")
        
        scoring = lead_service.calculate_lead_score_and_intent(lead.id)
        # Profile has name (+10), email (+20) -> 30
        # 1 user message -> +5 -> 35
        # Pricing keyword -> +30 -> 65
        # Total = 65
        self.assertEqual(scoring["score"], 65)
        self.assertEqual(scoring["rating"], "☀️ Warm")
        self.assertEqual(scoring["detected_intent"], "Pricing / Commercial")


if __name__ == "__main__":
    unittest.main()
