"""
Agent module for ADK CLI compatibility.

The adk eval CLI looks for agent_module.agent.root_agent
This module provides that structure.
"""

from customer_support_agent.agents import root_agent

# Export for adk eval CLI
root_agent = root_agent
