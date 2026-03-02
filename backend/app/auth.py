"""
Authentication and user management.

Simple token-based auth for now (can upgrade to JWT, OAuth later).

SECURITY NOTES:
- Uses bcrypt for password hashing (secure, with salt)
- Token storage is in-memory (use Redis for production multi-instance deployments)
- Tokens expire after 30 days
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

import bcrypt

logger = logging.getLogger(__name__)


# In-memory token store
# TODO: For production multi-instance deployments, replace with Redis:
#   import redis
#   redis_client = redis.Redis(host='redis-server', decode_responses=True)
_active_tokens: Dict[str, Dict] = {}


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with automatic salt generation.

    Args:
        password: Plain text password

    Returns:
        Hashed password (includes salt)
    """
    # bcrypt automatically generates a salt and includes it in the hash
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its bcrypt hash.

    Args:
        password: Plain text password
        password_hash: Stored bcrypt hash (includes salt)

    Returns:
        True if password matches
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError) as e:
        logger.warning(f"Password verification failed: {e}")
        return False


def generate_token(user_id: str) -> str:
    """
    Generate a secure authentication token.

    Args:
        user_id: User ID to associate with token

    Returns:
        Auth token
    """
    token = secrets.token_urlsafe(32)

    _active_tokens[token] = {
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30),
    }

    logger.info(f"Generated token for user: {user_id}")
    return token


def verify_token(token: str) -> Optional[str]:
    """
    Verify an auth token and return user_id.

    Args:
        token: Auth token

    Returns:
        user_id if valid, None if invalid/expired
    """
    if token not in _active_tokens:
        return None

    token_data = _active_tokens[token]

    # Check expiration
    if datetime.utcnow() > token_data["expires_at"]:
        del _active_tokens[token]
        logger.info(f"Token expired: {token[:8]}...")
        return None

    return token_data["user_id"]


def revoke_token(token: str):
    """
    Revoke an auth token (logout).

    Args:
        token: Auth token to revoke
    """
    if token in _active_tokens:
        user_id = _active_tokens[token]["user_id"]
        del _active_tokens[token]
        logger.info(f"Revoked token for user: {user_id}")
