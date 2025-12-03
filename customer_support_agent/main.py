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

import os
import logging

# Configure Python logging for observability
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more detailed logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Print to console/Cloud Run logs
    ]
)

# Set environment defaults
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")

# Import the root agent (this will cascade import all agents and tools)
from customer_support_agent.agents import root_agent

# Export root agent as the primary interface
# Note: 'agent' is an alias for AgentEvaluator compatibility
agent = root_agent
__all__ = ["root_agent", "agent"]

# Print initialization confirmation
print("[INIT] Customer Support Multi-Agent System loaded successfully")
print(f"[INIT] Project ID: {PROJECT_ID}")
