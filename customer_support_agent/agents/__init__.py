"""
Agents for the customer support multi-agent system.

This module exports all agents used in the system.
"""

# Import workflow agents first (they're used by other agents)
from customer_support_agent.agents.workflow_agents import (
    # parallel_product_lookup,  # DISABLED - not used anymore
    sequential_refund_workflow,
    # multi_product_details_loop,  # DISABLED - not used anymore
    # details_agent,  # DISABLED - used by ParallelAgent
    # inventory_agent,  # DISABLED - used by ParallelAgent
    # reviews_agent,  # DISABLED - used by ParallelAgent
    validation_agent,
    eligibility_agent,
    refund_processor,
    # product_details_fetcher,  # DISABLED - used by LoopAgent
)

# Import domain agents
from customer_support_agent.agents.product_agent import product_agent
from customer_support_agent.agents.order_agent import order_agent
from customer_support_agent.agents.billing_agent import billing_agent

# Import root agent
from customer_support_agent.agents.root_agent import root_agent

# Import callbacks
from customer_support_agent.agents.callbacks import (
    auto_save_to_memory,
    track_agent_start,
    check_hanging_agents,
)

__all__ = [
    # Root agent
    "root_agent",
    # Domain agents
    "product_agent",
    "order_agent",
    "billing_agent",
    # Workflow agents
    # "parallel_product_lookup",  # DISABLED - not used anymore
    "sequential_refund_workflow",
    # "multi_product_details_loop",  # DISABLED - not used anymore
    # Sub-agents (for testing/debugging)
    # "details_agent",  # DISABLED - used by ParallelAgent
    # "inventory_agent",  # DISABLED - used by ParallelAgent
    # "reviews_agent",  # DISABLED - used by ParallelAgent
    "validation_agent",
    "eligibility_agent",
    "refund_processor",
    # "product_details_fetcher",  # DISABLED - used by LoopAgent
    # Callbacks
    "auto_save_to_memory",
    "track_agent_start",
    "check_hanging_agents",
]
