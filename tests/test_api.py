import unittest
from fastapi.testclient import TestClient
from server import app
from repositories import sqlite_repository as repo
from config import ADMIN_PASSWORD

class ApiEndpointTests(unittest.TestCase):
    """Integration and routing tests for the FastAPI backend app."""

    def setUp(self) -> None:
        # Use fresh in-memory database for API test separation
        repo.reset_connection(":memory:")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        repo.close_connection()

    def test_status_endpoint(self) -> None:
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rag_pipeline"], "Active")
        self.assertIn("chromadb", data)

    def test_lead_capture_and_session(self) -> None:
        payload = {
            "name": "API Tester",
            "phone": "9998887777",
            "email": "tester@test.com",
            "intent": "Pricing",
            "organization": "Test Corp"
        }
        response = self.client.post("/api/leads", json=payload)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["session_id"])
        self.assertEqual(data["lead"]["name"], "API Tester")
        self.assertEqual(data["lead"]["phone"], "9998887777")
        self.assertEqual(data["lead"]["organization"], "Test Corp")

    def test_admin_endpoints_unauthorized_by_default(self) -> None:
        # Requesting metrics without X-Admin-Password header should fail
        response = self.client.get("/api/admin/metrics")
        self.assertEqual(response.status_code, 401)

        # Requesting sessions without X-Admin-Password header should fail
        response = self.client.get("/api/admin/sessions")
        self.assertEqual(response.status_code, 401)

    def test_admin_endpoints_authorized_with_header(self) -> None:
        headers = {"x-admin-password": ADMIN_PASSWORD}
        
        response = self.client.get("/api/admin/metrics", headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("total_leads", data)
        self.assertIn("active_users", data)

        response = self.client.get("/api/admin/sessions", headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_admin_document_upload_and_delete(self) -> None:
        headers = {"x-admin-password": ADMIN_PASSWORD}
        import io
        import os
        from unittest.mock import patch
        from config import DATA_PATH
        
        # Create a dummy PDF content
        dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy content")
        
        with patch("services.document_service.ingest_pdf_paths", return_value=5):
            response = self.client.post(
                "/api/admin/documents/upload",
                headers=headers,
                files={"file": ("test_upload_api.pdf", dummy_pdf, "application/pdf")}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            doc_id = data["document"]["id"]
            
            # Clean up the file created by the test
            uploaded_file_path = os.path.join(DATA_PATH, "test_upload_api.pdf")
            if os.path.exists(uploaded_file_path):
                os.remove(uploaded_file_path)

            # Test deletion
            with patch("services.document_service.get_vector_store"):
                del_response = self.client.delete(
                    f"/api/admin/documents/{doc_id}",
                    headers=headers
                )
                self.assertEqual(del_response.status_code, 200)
                self.assertEqual(del_response.json()["status"], "success")

if __name__ == "__main__":
    unittest.main()
