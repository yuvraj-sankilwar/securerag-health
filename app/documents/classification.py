"""Role-to-document-type classification and permission validation for document operations."""

from app.authz.permissions import (
    get_roles_for_doc_type,
    is_role_authorized_for_doc_type,
)


def validate_upload_permission(role_name: str, doc_type: str) -> bool:
    """
    Validate that a user with the given role can upload a document of the given type.

    Args:
        role_name: The user's role
        doc_type: The document type being uploaded

    Returns:
        True if the role can upload this document type
    """
    return is_role_authorized_for_doc_type(role_name, doc_type)


def get_authorized_roles_for_document(doc_type: str) -> list[str]:
    """
    Determine which roles should have access to a document of the given type.

    This is used during document ingestion to populate the authorized_roles
    array on both the document and its chunks.

    Args:
        doc_type: The document type

    Returns:
        List of role names authorized to access this document type
    """
    return get_roles_for_doc_type(doc_type)
