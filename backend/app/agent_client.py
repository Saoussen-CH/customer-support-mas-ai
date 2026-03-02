import asyncio
from typing import Optional

import vertexai
from google.api_core import exceptions, retry
from vertexai import agent_engines

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)

# Timeout configuration
DEFAULT_QUERY_TIMEOUT_SECONDS = 120  # 2 minutes for agent queries
SESSION_CREATE_TIMEOUT_SECONDS = 30  # 30 seconds for session creation

# Configure retry policy for Agent Engine calls
# Handles transient errors with exponential backoff
AGENT_RETRY_POLICY = retry.Retry(
    initial=1.0,  # Initial delay: 1 second
    maximum=60.0,  # Maximum delay: 60 seconds
    multiplier=2.0,  # Exponential backoff multiplier
    deadline=180.0,  # Total deadline: 3 minutes
    predicate=retry.if_exception_type(
        exceptions.ResourceExhausted,  # 429 Rate Limit
        exceptions.ServiceUnavailable,  # 503 Service Unavailable
        exceptions.DeadlineExceeded,  # 504 Gateway Timeout
        exceptions.InternalServerError,  # 500 Internal Server Error
        exceptions.TooManyRequests,  # 429 Too Many Requests
    ),
)


class AgentEngineClient:
    def __init__(self):
        """Initialize the Agent Engine client (lazy — no network calls at import time)."""
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        self.resource_name = settings.agent_engine_resource_name
        self._remote_app = None

    def _get_remote_app(self):
        """Lazily connect to Agent Engine on first use."""
        if self._remote_app is None:
            try:
                self._remote_app = agent_engines.get(self.resource_name)
                self.agent_engine_app = self._remote_app  # Alias for health checks
                logger.info("Connected to Agent Engine", resource_name=self.resource_name)
            except Exception as e:
                logger.error("Failed to connect to Agent Engine", error=str(e))
                raise
        return self._remote_app

    @property
    def remote_app(self):
        return self._get_remote_app()

    async def query_agent(
        self,
        user_id: str,
        agent_engine_session_id: Optional[str],
        message: str,
        timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
    ) -> tuple[str, str]:
        """
        Query the deployed Agent Engine using async_stream_query with retry logic.

        Implements automatic retry with exponential backoff for transient errors:
        - Rate limiting (429)
        - Service unavailability (503)
        - Gateway timeouts (504)
        - Internal server errors (500)

        Architecture:
        - user_id: Identifies the user (from auth or anonymous)
        - agent_engine_session_id: Agent Engine's session ID for this conversation
        - If agent_engine_session_id is None, creates a new session on Agent Engine

        Args:
            user_id: User ID (from auth or anonymous)
            agent_engine_session_id: Agent Engine session ID (None for new session)
            message: User message
            timeout_seconds: Maximum time to wait for response (default: 120s)

        Returns:
            Tuple of (response_text, agent_engine_session_id)

        Raises:
            TimeoutError: If the operation exceeds timeout_seconds
            Exception: For other failures
        """
        try:
            async with asyncio.timeout(timeout_seconds):
                # Check if we need to create a new session on Agent Engine
                if not agent_engine_session_id:
                    logger.info("Creating new Agent Engine session", user_id=user_id)

                    # Create session on Agent Engine with retry logic
                    @AGENT_RETRY_POLICY
                    async def _create_session():
                        async with asyncio.timeout(SESSION_CREATE_TIMEOUT_SECONDS):
                            return await self.remote_app.async_create_session(user_id=user_id)

                    try:
                        remote_session = await _create_session()
                    except asyncio.TimeoutError:
                        logger.error("Session creation timed out", user_id=user_id)
                        raise TimeoutError("Session creation timed out. Please try again.")
                    except Exception as e:
                        logger.error("Failed to create session after retries", error=str(e))
                        raise Exception("Unable to create session: Service temporarily unavailable")

                    # Extract the actual session_id from Agent Engine's response
                    agent_engine_session_id = remote_session["id"]

                    logger.info("Agent Engine session created", session_id=agent_engine_session_id, user_id=user_id)
                else:
                    logger.info(
                        "Using existing Agent Engine session", session_id=agent_engine_session_id, user_id=user_id
                    )

                logger.info("Querying agent", message_preview=message[:50])

                # Stream the query to the agent using Agent Engine's session
                response_text = ""
                event_count = 0

                async for event in self.remote_app.async_stream_query(
                    user_id=user_id, session_id=agent_engine_session_id, message=message
                ):
                    event_count += 1
                    logger.debug(
                        "Received event",
                        event_num=event_count,
                        author=event.get("author", "unknown") if isinstance(event, dict) else "unknown",
                    )

                    # Extract text from event
                    if isinstance(event, dict):
                        content = event.get("content", event.get("parts", {}))

                        if isinstance(content, dict):
                            parts = content.get("parts", [])

                            for part in parts:
                                if isinstance(part, dict):
                                    if part.get("text"):
                                        response_text += part["text"]
                                    elif part.get("function_call"):
                                        fn = part["function_call"]
                                        logger.debug("Tool call", tool=fn.get("name"), args=fn.get("args", {}))

                        # Also check for direct text field
                        if "text" in event:
                            response_text += event["text"]

                logger.info("Query processing complete", event_count=event_count, response_length=len(response_text))

                if not response_text:
                    logger.error("No response text extracted", event_count=event_count)
                    response_text = "I apologize, but I didn't receive a response. Please try again."

                # Return agent_engine_session_id so it can be tracked in our database
                return response_text, agent_engine_session_id

        except asyncio.TimeoutError:
            logger.error("Agent query timed out", timeout_seconds=timeout_seconds, user_id=user_id)
            raise TimeoutError(
                f"Request timed out after {timeout_seconds} seconds. " "The system is busy. Please try again."
            )
        except TimeoutError:
            # Re-raise TimeoutError from session creation
            raise
        except Exception as e:
            logger.error("Error querying agent", error=str(e), exc_info=True)
            raise Exception(f"Failed to query agent: {str(e)}")


agent_client = AgentEngineClient()
