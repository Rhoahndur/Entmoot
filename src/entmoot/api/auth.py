"""
API key authentication for the Entmoot API.

When ``ENTMOOT_AUTH_ENABLED=true`` (the default) every request that
hits a protected router must include a valid ``X-API-Key`` header.
Public routes (``/``, ``/health``, ``/docs``, ``/redoc``, ``/openapi.json``)
are excluded at the router level, not here.
"""

import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from entmoot.core.config import settings

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(_api_key_header),
) -> Optional[str]:
    """FastAPI dependency that validates the ``X-API-Key`` header.

    When authentication is disabled (``ENTMOOT_AUTH_ENABLED=false`` or no
    keys configured) this dependency is a no-op.

    Returns:
        The validated API key, or ``None`` when auth is disabled.

    Raises:
        HTTPException 401: If auth is enabled and the key is missing or invalid.
    """
    if not settings.auth_enabled or not settings.api_keys:
        return None

    valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
    if not valid_keys:
        return None

    if not api_key or api_key not in valid_keys:
        logger.warning("Rejected request with invalid or missing API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Invalid or missing API key"},
        )

    return api_key
