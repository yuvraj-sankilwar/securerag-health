"""SpiceDB schema loader — loads .zed schema on application startup."""

import asyncio
import logging
import os

from app.authz.spicedb_client import SpiceDBClient

logger = logging.getLogger(__name__)

SCHEMA_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "spicedb", "schema.zed")


async def load_spicedb_schema(client: SpiceDBClient, max_retries: int = 5, backoff_seconds: float = 2.0) -> bool:
    """
    Load the SpiceDB authorization schema from the .zed file.

    Implements retry logic since SpiceDB may take 5-10 seconds to become
    ready after Docker start.

    Args:
        client: SpiceDB client instance
        max_retries: Maximum number of retry attempts (default: 5)
        backoff_seconds: Seconds to wait between retries (default: 2.0)

    Returns:
        True if schema was loaded successfully, False otherwise
    """
    # Resolve schema file path
    schema_path = os.path.abspath(SCHEMA_FILE_PATH)
    if not os.path.exists(schema_path):
        logger.error(f"SpiceDB schema file not found at: {schema_path}")
        return False

    with open(schema_path, "r") as f:
        schema_text = f.read()

    if not schema_text.strip():
        logger.error("SpiceDB schema file is empty")
        return False

    logger.info(f"Loading SpiceDB schema from {schema_path}")

    for attempt in range(1, max_retries + 1):
        try:
            success = await client.write_schema(schema_text)
            if success:
                logger.info(f"SpiceDB schema loaded successfully (attempt {attempt})")
                return True
            else:
                logger.warning(f"SpiceDB schema write returned False (attempt {attempt}/{max_retries})")
        except Exception as e:
            logger.warning(f"SpiceDB schema load attempt {attempt}/{max_retries} failed: {e}")

        if attempt < max_retries:
            logger.info(f"Retrying in {backoff_seconds}s...")
            await asyncio.sleep(backoff_seconds)

    logger.error(f"Failed to load SpiceDB schema after {max_retries} attempts")
    return False
