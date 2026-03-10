"""SpiceDB gRPC client wrapper for permission checks and relationship management."""

import logging

from authzed.api.v1 import (
    CheckPermissionRequest,
    CheckPermissionResponse,
    LookupResourcesRequest,
    ObjectReference,
    Relationship,
    RelationshipUpdate,
    SubjectReference,
    WriteRelationshipsRequest,
    WriteSchemaRequest,
)
from grpcutil import insecure_bearer_token_credentials

logger = logging.getLogger(__name__)


class SpiceDBClient:
    """
    gRPC client wrapper for SpiceDB (Authzed).

    Provides methods for:
    - Checking individual permissions
    - Looking up authorized document IDs
    - Writing relationships (role membership, document access)
    """

    def __init__(self, endpoint: str, preshared_key: str):
        """
        Initialize SpiceDB client.

        Args:
            endpoint: SpiceDB gRPC endpoint (e.g., localhost:50051)
            preshared_key: Pre-shared key for authentication
        """
        self.endpoint = endpoint
        self.preshared_key = preshared_key
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the gRPC client (insecure for dev)."""
        try:
            from authzed.api.v1 import Client

            self._client = Client(
                self.endpoint,
                insecure_bearer_token_credentials(self.preshared_key),
            )
            logger.info(f"SpiceDB client initialized at {self.endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize SpiceDB client: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if the SpiceDB client was successfully initialized."""
        return self._client is not None

    async def check_permission(self, user_id: str, object_type: str, object_id: str, permission: str) -> bool:
        """
        Check if a user has a specific permission on an object.

        Args:
            user_id: The user's UUID
            object_type: Object type (e.g., "document")
            object_id: Object's UUID
            permission: Permission to check (e.g., "view")

        Returns:
            True if permission is granted, False otherwise.
            Returns False on error (fail-closed).
        """
        if not self.is_available:
            logger.warning("SpiceDB unavailable — fail-closed, returning False")
            return False

        try:
            response = self._client.CheckPermission(
                CheckPermissionRequest(
                    resource=ObjectReference(object_type=object_type, object_id=object_id),
                    permission=permission,
                    subject=SubjectReference(object=ObjectReference(object_type="user", object_id=user_id)),
                )
            )
            return response.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION
        except Exception as e:
            logger.error(f"SpiceDB CheckPermission failed: {e}")
            return False

    async def get_authorized_doc_ids(self, user_id: str, role_name: str, tenant_id: str) -> list[str]:
        """
        Get list of document IDs the user is authorized to view.

        Uses LookupResources RPC on document#view for the given user.
        Falls back to empty list on error (fail-closed).

        Args:
            user_id: The user's UUID
            role_name: User's role name
            tenant_id: User's tenant UUID

        Returns:
            List of authorized document UUIDs
        """
        if not self.is_available:
            logger.warning("SpiceDB unavailable — fail-closed, returning empty list")
            return []

        try:
            authorized_ids = []
            response_iterator = self._client.LookupResources(
                LookupResourcesRequest(
                    resource_object_type="document",
                    permission="view",
                    subject=SubjectReference(object=ObjectReference(object_type="user", object_id=user_id)),
                )
            )
            for response in response_iterator:
                authorized_ids.append(response.resource_object_id)

            logger.debug(f"SpiceDB LookupResources returned {len(authorized_ids)} documents for user {user_id}")
            return authorized_ids
        except Exception as e:
            logger.error(f"SpiceDB LookupResources failed: {e}")
            return []

    async def write_relationships(self, relationships: list[dict]) -> bool:
        """
        Write relationships to SpiceDB.

        Args:
            relationships: List of dicts with keys:
                - resource_type: str (e.g., "document", "role", "tenant")
                - resource_id: str
                - relation: str (e.g., "authorized_role", "member", "owner")
                - subject_type: str (e.g., "user", "role")
                - subject_id: str

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.warning("SpiceDB unavailable — cannot write relationships")
            return False

        try:
            updates = []
            for rel in relationships:
                updates.append(
                    RelationshipUpdate(
                        operation=RelationshipUpdate.OPERATION_TOUCH,
                        relationship=Relationship(
                            resource=ObjectReference(
                                object_type=rel["resource_type"],
                                object_id=rel["resource_id"],
                            ),
                            relation=rel["relation"],
                            subject=SubjectReference(
                                object=ObjectReference(
                                    object_type=rel["subject_type"],
                                    object_id=rel["subject_id"],
                                )
                            ),
                        ),
                    )
                )

            self._client.WriteRelationships(WriteRelationshipsRequest(updates=updates))
            logger.info(f"Wrote {len(updates)} relationships to SpiceDB")
            return True
        except Exception as e:
            logger.error(f"SpiceDB WriteRelationships failed: {e}")
            return False

    async def write_schema(self, schema_text: str) -> bool:
        """
        Write (or update) the authorization schema to SpiceDB.

        Args:
            schema_text: The .zed schema definition

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.warning("SpiceDB unavailable — cannot write schema")
            return False

        try:
            self._client.WriteSchema(WriteSchemaRequest(schema=schema_text))
            logger.info("SpiceDB schema written successfully")
            return True
        except Exception as e:
            logger.error(f"SpiceDB WriteSchema failed: {e}")
            return False
