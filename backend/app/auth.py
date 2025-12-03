"""
Authentication and user management.

Simple token-based auth for now (can upgrade to JWT, OAuth later).
"""

import secrets
import hashlib
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# In-memory token store (use Redis in production)
_active_tokens: Dict[str, Dict] = {}


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256 (use bcrypt in production).

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password
        password_hash: Stored hash

    Returns:
        True if password matches
    """
    return hash_password(password) == password_hash


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
