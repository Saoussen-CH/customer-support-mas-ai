import vertexai
from vertexai import agent_engines
from typing import Optional
import uuid
import logging
from .config import settings
from google.api_core import retry
from google.api_core import exceptions

logger = logging.getLogger(__name__)

# Configure retry policy for Agent Engine calls
# Handles transient errors with exponential backoff
AGENT_RETRY_POLICY = retry.Retry(
    initial=1.0,          # Initial delay: 1 second
    maximum=60.0,         # Maximum delay: 60 seconds
    multiplier=2.0,       # Exponential backoff multiplier
    deadline=180.0,       # Total deadline: 3 minutes
    predicate=retry.if_exception_type(
        exceptions.ResourceExhausted,    # 429 Rate Limit
        exceptions.ServiceUnavailable,   # 503 Service Unavailable
        exceptions.DeadlineExceeded,     # 504 Gateway Timeout
        exceptions.InternalServerError,  # 500 Internal Server Error
        exceptions.TooManyRequests,      # 429 Too Many Requests
    )
)


class AgentEngineClient:
    def __init__(self):
        """Initialize the Agent Engine client."""
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        self.resource_name = settings.agent_engine_resource_name

        # Get the remote agent engine app
        try:
            self.remote_app = agent_engines.get(self.resource_name)
            logger.info(f"Connected to Agent Engine: {self.resource_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Agent Engine: {e}")
            raise

    async def query_agent(
        self,
        user_id: str,
        agent_engine_session_id: Optional[str],
        message: str
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

        Returns:
            Tuple of (response_text, agent_engine_session_id)
        """
        try:
            # Check if we need to create a new session on Agent Engine
            if not agent_engine_session_id:
                logger.info(f"Creating new Agent Engine session for user: {user_id}")

                # Create session on Agent Engine with retry logic
                @AGENT_RETRY_POLICY
                async def _create_session():
                    return await self.remote_app.async_create_session(user_id=user_id)

                try:
                    remote_session = await _create_session()
                except Exception as e:
                    logger.error(f"Failed to create session after retries: {e}")
                    raise Exception(f"Unable to create session: Service temporarily unavailable")

                # Extract the actual session_id from Agent Engine's response
                agent_engine_session_id = remote_session['id']

                logger.info(f"Agent Engine session created: {agent_engine_session_id} for user: {user_id}")
            else:
                logger.info(f"Using existing Agent Engine session: {agent_engine_session_id} for user: {user_id}")

            logger.info(f"Querying agent with message: {message[:50]}...")

            # Stream the query to the agent using Agent Engine's session
            response_text = ""
            event_count = 0

            async for event in self.remote_app.async_stream_query(
                user_id=user_id,
                session_id=agent_engine_session_id,
                message=message
            ):
                event_count += 1
                logger.info(f"[Event {event_count}] Received event from author: {event.get('author', 'unknown')}")
                logger.info(f"[Event {event_count}] Full event keys: {list(event.keys())}")
                logger.info(f"[Event {event_count}] Full event: {event}")

                # Extract text from event
                if isinstance(event, dict):
                    content = event.get("content", event.get("parts", {}))

                    if isinstance(content, dict):
                        parts = content.get("parts", [])
                        logger.info(f"[Event {event_count}] Found {len(parts)} parts in content")

                        for i, part in enumerate(parts):
                            if isinstance(part, dict):
                                if part.get("text"):
                                    # Append text parts (this is the agent's response)
                                    text = part["text"]
                                    response_text += text
                                    logger.info(f"[Event {event_count}] Part {i}: Extracted text ({len(text)} chars): {text[:100]}...")
                                elif part.get("function_call"):
                                    # Log function calls (these are tool invocations)
                                    fn = part["function_call"]
                                    logger.info(f"[Event {event_count}] Part {i}: Tool call: {fn.get('name')}({fn.get('args', {})})")
                                else:
                                    logger.info(f"[Event {event_count}] Part {i}: Other part type: {list(part.keys())}")
                    else:
                        logger.info(f"[Event {event_count}] Content is not a dict: {type(content)}")

                    # Also check for direct text field
                    if "text" in event:
                        direct_text = event["text"]
                        response_text += direct_text
                        logger.info(f"[Event {event_count}] Found direct text field: {direct_text[:100]}...")

            logger.info(f"Processing complete: {event_count} events, {len(response_text)} chars extracted")

            if not response_text:
                logger.error(f"No response text extracted from {event_count} events! Check logs above for event details.")
                response_text = "I apologize, but I didn't receive a response. Please try again."

            logger.info(f"Final response ({len(response_text)} chars): {response_text[:100]}...")

            # Return agent_engine_session_id so it can be tracked in our database
            return response_text, agent_engine_session_id

        except Exception as e:
            logger.error(f"Error querying agent: {str(e)}", exc_info=True)
            raise Exception(f"Failed to query agent: {str(e)}")


agent_client = AgentEngineClient()
