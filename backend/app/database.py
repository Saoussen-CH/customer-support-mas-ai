"""
Database layer for user management and session tracking.

Uses Firestore for storing:
- Users: User accounts and profiles
- Sessions: Conversation threads for each user
- Session state is managed by Agent Engine, but we track metadata here
"""

from google.cloud import firestore
from typing import Optional, Dict, List
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, project_id: str, database_id: str):
        """Initialize Firestore database client."""
        self.db = firestore.Client(project=project_id, database=database_id)
        logger.info(f"Connected to Firestore: {project_id}/{database_id}")

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================

    def create_user(self, email: str, name: str, password_hash: str) -> str:
        """
        Create a new user account.

        Args:
            email: User email (unique identifier)
            name: User display name
            password_hash: Hashed password (use bcrypt in production)

        Returns:
            user_id: Generated user ID
        """
        user_id = str(uuid.uuid4())

        user_data = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "last_login": None,
        }

        self.db.collection("users").document(user_id).set(user_data)
        logger.info(f"Created user: {user_id} ({email})")

        return user_id

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            User data dict or None if not found
        """
        query = self.db.collection("users").where("email", "==", email).limit(1)
        results = list(query.stream())

        if results:
            user_data = results[0].to_dict()
            logger.info(f"Found user: {user_data['user_id']} ({email})")
            return user_data

        logger.info(f"User not found: {email}")
        return None

    def get_user(self, user_id: str) -> Optional[Dict]:
        """
        Get user by user_id.

        Args:
            user_id: User ID

        Returns:
            User data dict or None if not found
        """
        doc = self.db.collection("users").document(user_id).get()

        if doc.exists:
            return doc.to_dict()

        return None

    def update_last_login(self, user_id: str):
        """Update user's last login timestamp."""
        self.db.collection("users").document(user_id).update({
            "last_login": datetime.utcnow()
        })

    def create_anonymous_user(self) -> str:
        """
        Create an anonymous user (for users who don't register).

        Returns:
            user_id: Generated anonymous user ID
        """
        user_id = f"anon-{uuid.uuid4()}"

        user_data = {
            "user_id": user_id,
            "is_anonymous": True,
            "created_at": datetime.utcnow(),
        }

        self.db.collection("users").document(user_id).set(user_data)
        logger.info(f"Created anonymous user: {user_id}")

        return user_id

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def create_session(
        self,
        user_id: str,
        agent_engine_session_id: str,
        session_name: Optional[str] = None
    ) -> str:
        """
        Create a new conversation session for a user.

        Args:
            user_id: User ID who owns this session
            agent_engine_session_id: The session ID from Agent Engine
            session_name: Optional name for the session

        Returns:
            session_id: Our internal session ID
        """
        session_id = str(uuid.uuid4())

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_engine_session_id": agent_engine_session_id,
            "session_name": session_name or f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "message_count": 0,
            "is_active": True,
        }

        self.db.collection("sessions").document(session_id).set(session_data)
        logger.info(f"Created session: {session_id} for user: {user_id}")

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get session by session_id.

        Args:
            session_id: Session ID

        Returns:
            Session data dict or None if not found
        """
        doc = self.db.collection("sessions").document(session_id).get()

        if doc.exists:
            return doc.to_dict()

        return None

    def get_user_sessions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum number of sessions to return

        Returns:
            List of session data dicts, ordered by updated_at desc
        """
        # Simplified query - only filter by user_id to avoid composite index requirement
        # We'll sort and filter active sessions in Python
        query = (
            self.db.collection("sessions")
            .where("user_id", "==", user_id)
            .limit(limit * 2)  # Get more to account for inactive sessions
        )

        sessions = [doc.to_dict() for doc in query.stream()]

        # Filter for active sessions and sort by updated_at
        active_sessions = [s for s in sessions if s.get("is_active", True)]
        active_sessions.sort(key=lambda x: x.get("updated_at", datetime.min), reverse=True)

        # Limit to requested number
        result = active_sessions[:limit]

        logger.info(f"Found {len(result)} active sessions for user: {user_id}")

        return result

    def update_session(self, session_id: str):
        """
        Update session's updated_at timestamp and increment message count.

        Args:
            session_id: Session ID
        """
        self.db.collection("sessions").document(session_id).update({
            "updated_at": datetime.utcnow(),
            "message_count": firestore.Increment(1),
        })

    def rename_session(self, session_id: str, new_name: str):
        """
        Rename a session.

        Args:
            session_id: Session ID
            new_name: New session name
        """
        self.db.collection("sessions").document(session_id).update({
            "session_name": new_name,
            "updated_at": datetime.utcnow(),
        })
        logger.info(f"Renamed session {session_id} to: {new_name}")

    def delete_session(self, session_id: str):
        """
        Mark session as inactive (soft delete).

        Args:
            session_id: Session ID
        """
        self.db.collection("sessions").document(session_id).update({
            "is_active": False,
            "updated_at": datetime.utcnow(),
        })
        logger.info(f"Deleted session: {session_id}")

    # =========================================================================
    # MESSAGE MANAGEMENT
    # =========================================================================

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None
    ) -> str:
        """
        Save a message to a session.

        Args:
            session_id: Session ID
            role: Message role ('user' or 'assistant')
            content: Message content
            message_id: Optional custom message ID

        Returns:
            message_id: The message ID
        """
        if not message_id:
            message_id = str(uuid.uuid4())

        message_data = {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
        }

        # Store in subcollection: sessions/{session_id}/messages/{message_id}
        self.db.collection("sessions").document(session_id).collection("messages").document(message_id).set(message_data)

        logger.info(f"Saved {role} message to session {session_id}")

        return message_id

    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict]:
        """
        Get all messages for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts, ordered by timestamp asc
        """
        query = (
            self.db.collection("sessions")
            .document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .limit(limit)
        )

        messages = [doc.to_dict() for doc in query.stream()]

        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")

        return messages


# Global database instance
_db_instance: Optional[Database] = None


def get_database(project_id: str, database_id: str) -> Database:
    """Get or create global database instance."""
    global _db_instance

    if _db_instance is None:
        _db_instance = Database(project_id, database_id)

    return _db_instance
