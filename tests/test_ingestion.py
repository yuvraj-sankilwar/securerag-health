"""Tests for document ingestion pipeline."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, login_as


@pytest.mark.asyncio
class TestDocumentIngestion:
    """Tests for document upload and listing endpoints."""

    async def test_physician_can_upload_ehr(self, client: AsyncClient):
        """Test that a physician can upload an EHR document."""
        token = await login_as(client, "dr.smith@hospital.com")

        # Create a test file
        test_content = (
            "Patient: Test Patient\n"
            "Date: 2024-03-20\n"
            "Chief Complaint: Routine checkup\n"
            "Assessment: Patient is in good health.\n"
            "Plan: Annual follow-up in 12 months."
        )

        response = await client.post(
            "/documents/upload",
            files={"file": ("test_ehr.txt", test_content.encode(), "text/plain")},
            data={"doc_type": "EHR", "sensitivity_tier": "2"},
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert data["chunk_count"] > 0
        assert data["message"] == "Document ingested successfully"

    async def test_nurse_cannot_upload_ehr(self, client: AsyncClient):
        """Test that a nurse cannot upload an EHR document (wrong role)."""
        token = await login_as(client, "nurse.jones@hospital.com")

        test_content = "Test EHR content that nurse should not be able to upload."

        response = await client.post(
            "/documents/upload",
            files={"file": ("test_ehr.txt", test_content.encode(), "text/plain")},
            data={"doc_type": "EHR", "sensitivity_tier": "2"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403

    async def test_pharmacist_can_upload_drug_formulary(self, client: AsyncClient):
        """Test that a pharmacist can upload a drug formulary document."""
        token = await login_as(client, "pharm.wilson@hospital.com")

        test_content = (
            "Drug Formulary Update\n"
            "New additions for Q2 2024:\n"
            "- Sacubitril/Valsartan (Entresto) 24/26mg, 49/51mg, 97/103mg\n"
            "- Dapagliflozin (Farxiga) 5mg, 10mg\n"
        )

        response = await client.post(
            "/documents/upload",
            files={"file": ("drug_update.txt", test_content.encode(), "text/plain")},
            data={"doc_type": "DRUG_FORMULARY", "sensitivity_tier": "1"},
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["chunk_count"] > 0

    async def test_admin_cannot_upload_ehr(self, client: AsyncClient):
        """Test that an administrator cannot upload clinical documents."""
        token = await login_as(client, "admin.taylor@hospital.com")

        test_content = "Clinical notes that admin should not upload."

        response = await client.post(
            "/documents/upload",
            files={"file": ("clinical.txt", test_content.encode(), "text/plain")},
            data={"doc_type": "EHR", "sensitivity_tier": "3"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403

    async def test_list_documents_filtered_by_role(self, client: AsyncClient):
        """Test that document listing respects RLS and returns only authorized documents."""
        token = await login_as(client, "dr.smith@hospital.com")

        response = await client.get(
            "/documents/list",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_count" in data

        # Physician should see clinical documents but not billing/compliance
        for doc in data["documents"]:
            assert doc["doc_type"] not in ["BILLING_RECORD", "AUDIT_LOG"], (
                f"Physician should not see {doc['doc_type']} in document list"
            )

    async def test_upload_empty_file_rejected(self, client: AsyncClient):
        """Test that uploading an empty file is rejected."""
        token = await login_as(client, "dr.smith@hospital.com")

        response = await client.post(
            "/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"doc_type": "EHR", "sensitivity_tier": "1"},
            headers=auth_headers(token),
        )

        assert response.status_code == 400

    async def test_upload_without_auth_rejected(self, client: AsyncClient):
        """Test that document upload without authentication is rejected."""
        response = await client.post(
            "/documents/upload",
            files={"file": ("test.txt", b"test content", "text/plain")},
            data={"doc_type": "EHR", "sensitivity_tier": "1"},
        )

        assert response.status_code == 401
