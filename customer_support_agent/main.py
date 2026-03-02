"""
Main entry point for the customer support multi-agent system.

This module provides the primary interface for importing and using the agent system.

USAGE:
    # Local testing
    from customer_support_agent.main import root_agent
    from vertexai import agent_engines

    app = agent_engines.AdkApp(agent=root_agent)
    session = await app.async_create_session(user_id="user123")
    response = await app.async_query(
        user_id="user123",
        session_id=session.id,
        message="Show me laptops under $600"
    )

    # Production deployment
    remote_app = agent_engines.create(
        agent_engine=app,
        requirements=[...],
        extra_packages=["customer_support_agent"],
        display_name="customer-support-multiagent"
    )
"""

import logging
import os

# Load .env file FIRST before any env var checks
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, assume env vars set externally

# Configure Python logging for observability
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "WARNING")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

# Get project ID from environment (required)
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set")

# Import the root agent (this will cascade import all agents and tools)
from customer_support_agent.agents import root_agent  # noqa: E402

# Export root agent as the primary interface
# Note: 'agent' is an alias for AgentEvaluator compatibility
agent = root_agent
__all__ = ["root_agent", "agent"]

logger = logging.getLogger(__name__)
logger.debug("Customer Support Multi-Agent System loaded (project: %s)", PROJECT_ID)
