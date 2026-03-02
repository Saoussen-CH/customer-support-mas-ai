"""
Agents for the customer support multi-agent system.

This module exports all agents used in the system.
"""

# Import workflow agents first (they're used by other agents)
from customer_support_agent.agents.billing_agent import billing_agent

# Import callbacks
from customer_support_agent.agents.callbacks import (
    auto_save_to_memory,
    check_hanging_agents,
    track_agent_start,
)
from customer_support_agent.agents.order_agent import order_agent

# Import domain agents
from customer_support_agent.agents.product_agent import product_agent

# Import root agent
from customer_support_agent.agents.root_agent import root_agent
from customer_support_agent.agents.workflow_agents import (
    eligibility_agent,
    refund_processor,
    sequential_refund_workflow,
    validation_agent,
)

__all__ = [
    # Root agent
    "root_agent",
    # Domain agents
    "product_agent",
    "order_agent",
    "billing_agent",
    "sequential_refund_workflow",
    "validation_agent",
    "eligibility_agent",
    "refund_processor",
    # Callbacks
    "auto_save_to_memory",
    "track_agent_start",
    "check_hanging_agents",
]
