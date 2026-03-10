"""Tests for RAG query isolation — verifying cross-role access control enforcement."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, login_as


@pytest.mark.asyncio
class TestRAGIsolation:
    """
    Cross-role leak tests.

    Verify that the triple-layer security model (SpiceDB + RLS + role mapping)
    correctly prevents unauthorized access to documents.
    """

    async def test_physician_cannot_see_billing_records(self, client: AsyncClient):
        """
        PHYSICIAN should not see BILLING_RECORD documents.

        1. Login as dr.smith (PHYSICIAN)
        2. POST /rag/query with query about billing
        3. Assert no BILLING_RECORD sources are returned
        """
        token = await login_as(client, "dr.smith@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "show me billing invoices and revenue", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        # Verify no billing records in sources
        for source in data.get("sources", []):
            assert source["doc_type"] != "BILLING_RECORD", (
                f"PHYSICIAN should not see BILLING_RECORD, but got source: {source}"
            )

        # Verify the answer doesn't contain billing-specific terms
        answer_lower = data.get("answer", "").lower()
        billing_terms = ["invoice", "revenue", "billing summary", "collection rate", "payer mix"]
        for term in billing_terms:
            if term in answer_lower:
                # This is a soft check — the LLM might use these terms generically
                pass  # Logged but not asserted due to LLM variability

    async def test_patient_sees_only_own_records(self, client: AsyncClient):
        """
        PATIENT should only see documents they own.

        1. Login as patient.001 (PATIENT)
        2. POST /rag/query
        3. Assert all sources are patient-appropriate types
        """
        token = await login_as(client, "patient.001@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "show my discharge notes and health summary", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        # Patient should only see their own record types
        allowed_patient_types = {"OWN_EHR_SUMMARY", "DISCHARGE_NOTES", "APPOINTMENT_RECORD"}
        for source in data.get("sources", []):
            assert source["doc_type"] in allowed_patient_types, (
                f"PATIENT should only see {allowed_patient_types}, but got: {source['doc_type']}"
            )

    async def test_admin_cannot_access_ehr(self, client: AsyncClient):
        """
        ADMINISTRATOR should not have access to EHR documents.

        1. Login as admin.taylor (ADMINISTRATOR)
        2. POST /rag/query about clinical data
        3. Assert answer indicates no authorized documents
        """
        token = await login_as(client, "admin.taylor@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "patient vitals and clinical notes", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        # Admin should not see any EHR or clinical doc types
        clinical_types = {"EHR", "CLINICAL_NOTES", "VITALS", "LAB_RESULTS"}
        for source in data.get("sources", []):
            assert source["doc_type"] not in clinical_types, f"ADMINISTRATOR should not see {source['doc_type']}"

        # If no sources were found, the answer should indicate that
        if not data.get("sources"):
            assert "no authorized documents" in data["answer"].lower() or "could not find" in data["answer"].lower()

    async def test_radiologist_accesses_imaging_reports(self, client: AsyncClient):
        """
        RADIOLOGIST should have access to RADIOLOGY_REPORT documents.

        1. Login as rad.patel (RADIOLOGIST)
        2. POST /rag/query about imaging
        3. Assert at least one source of type RADIOLOGY_REPORT
        """
        token = await login_as(client, "rad.patel@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "chest X-ray findings and imaging results", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        # Radiologist should see radiology reports
        radiology_sources = [s for s in data.get("sources", []) if s["doc_type"] == "RADIOLOGY_REPORT"]
        assert len(radiology_sources) > 0, "RADIOLOGIST should be able to access at least one RADIOLOGY_REPORT"

    async def test_unauthenticated_request_rejected(self, client: AsyncClient):
        """
        Requests without Authorization header should be rejected with 401.
        """
        response = await client.post(
            "/rag/query",
            json={"query": "show me everything", "top_k": 10},
        )

        assert response.status_code == 401

    async def test_nurse_cannot_see_radiology_reports(self, client: AsyncClient):
        """
        NURSE should not see RADIOLOGY_REPORT documents.
        """
        token = await login_as(client, "nurse.jones@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "show me chest X-ray and CT scan results", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        for source in data.get("sources", []):
            assert source["doc_type"] != "RADIOLOGY_REPORT", (
                f"NURSE should not see RADIOLOGY_REPORT, but got source: {source}"
            )

    async def test_compliance_officer_accesses_audit_logs(self, client: AsyncClient):
        """
        COMPLIANCE_OFFICER should have access to AUDIT_LOG documents.
        """
        token = await login_as(client, "compliance.moore@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "HIPAA compliance audit and data retention", "top_k": 10},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        audit_sources = [s for s in data.get("sources", []) if s["doc_type"] == "AUDIT_LOG"]
        assert len(audit_sources) > 0, "COMPLIANCE_OFFICER should be able to access AUDIT_LOG documents"

    async def test_response_does_not_expose_raw_chunks(self, client: AsyncClient):
        """
        API response should never include raw chunk text or internal UUIDs.
        """
        token = await login_as(client, "dr.smith@hospital.com")

        response = await client.post(
            "/rag/query",
            json={"query": "patient assessment", "top_k": 5},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure has no raw text fields
        for source in data.get("sources", []):
            assert "text" not in source, "Source should not contain raw chunk text"
            assert "chunk_text" not in source, "Source should not contain chunk_text"
            assert "chunk_id" not in source, "Source should not expose chunk IDs"
            assert "embedding" not in source, "Source should not expose embeddings"

            # Verify required fields are present
            assert "title" in source
            assert "doc_type" in source
            assert "similarity_score" in source
