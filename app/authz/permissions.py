"""Role-to-document-type permission mapping and authorization helpers."""


# ─────────────────────────────────────────────────────────────────
# ROLE → DOCUMENT TYPE ACCESS MAPPING
# Defines which document types each hospital role can access.
# ─────────────────────────────────────────────────────────────────

ROLE_DOCUMENT_TYPE_MAP: dict[str, list[str]] = {
    "PHYSICIAN": [
        "EHR",
        "CLINICAL_NOTES",
        "LAB_RESULTS",
        "PRESCRIPTIONS",
        "DISCHARGE_SUMMARY",
        "RADIOLOGY_REPORT",
    ],
    "NURSE": [
        "PATIENT_CARE_PLAN",
        "MEDICATION_SCHEDULE",
        "VITALS",
        "CLINICAL_NOTES",
    ],
    "RADIOLOGIST": [
        "RADIOLOGY_REPORT",
        "DICOM_METADATA",
        "IMAGING_PROTOCOL",
    ],
    "PHARMACIST": [
        "DRUG_FORMULARY",
        "PRESCRIPTION_ORDER",
        "DRUG_INTERACTION_ALERT",
    ],
    "PATIENT": [
        "OWN_EHR_SUMMARY",
        "DISCHARGE_NOTES",
        "APPOINTMENT_RECORD",
    ],
    "LAB_TECHNICIAN": [
        "LAB_ORDER",
        "SPECIMEN_REPORT",
        "REFERENCE_RANGES",
    ],
    "ADMINISTRATOR": [
        "BILLING_RECORD",
        "INSURANCE_AUTH",
        "HR_DOCUMENT",
        "APPOINTMENT_RECORD",
    ],
    "COMPLIANCE_OFFICER": [
        "AUDIT_LOG",
        "REGULATORY_FILING",
        "POLICY_DOCUMENT",
        "ALL_ANONYMIZED",
    ],
}

# Reverse mapping: document_type → list of roles that can access it
DOC_TYPE_TO_ROLES: dict[str, list[str]] = {}
for role, doc_types in ROLE_DOCUMENT_TYPE_MAP.items():
    for dt in doc_types:
        if dt not in DOC_TYPE_TO_ROLES:
            DOC_TYPE_TO_ROLES[dt] = []
        DOC_TYPE_TO_ROLES[dt].append(role)


def get_authorized_doc_types(role_name: str) -> list[str]:
    """
    Get the list of document types a role can access.

    Args:
        role_name: Role name (e.g., "PHYSICIAN")

    Returns:
        List of document type strings the role can access.
        Returns empty list if role is unknown.
    """
    return ROLE_DOCUMENT_TYPE_MAP.get(role_name.upper(), [])


def is_role_authorized_for_doc_type(role_name: str, doc_type: str) -> bool:
    """
    Check if a role is authorized to access a specific document type.

    Args:
        role_name: Role name (e.g., "PHYSICIAN")
        doc_type: Document type (e.g., "EHR")

    Returns:
        True if the role can access the document type
    """
    authorized_types = get_authorized_doc_types(role_name)
    return doc_type.upper() in authorized_types


def get_roles_for_doc_type(doc_type: str) -> list[str]:
    """
    Get all roles that can access a specific document type.

    Args:
        doc_type: Document type (e.g., "EHR")

    Returns:
        List of role names that can access this document type.
        Returns empty list if document type is unknown.
    """
    return DOC_TYPE_TO_ROLES.get(doc_type.upper(), [])
