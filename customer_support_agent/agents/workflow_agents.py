"""
Workflow agents for the customer support system.

This module contains ParallelAgent, SequentialAgent, and LoopAgent patterns.
"""

import logging
from google.adk.agents import Agent, SequentialAgent  # ParallelAgent, LoopAgent - DISABLED

# Import centralized configuration
from customer_support_agent.config import get_agent_config

# Import tools
from customer_support_agent.tools import (
    # get_product_details,  # DISABLED - used by ParallelAgent
    # check_inventory,  # DISABLED - used by ParallelAgent
    # get_product_reviews,  # DISABLED - used by ParallelAgent
    validate_order_id,
    check_refund_eligibility,
    process_refund,
    # get_next_product_to_detail,  # DISABLED - used by LoopAgent
    # exit_product_loop,  # DISABLED - used by LoopAgent
)


# =============================================================================
# PARALLELAGENT: Concurrent Execution Pattern - DISABLED (not used anymore)
# =============================================================================
# Use case: Get comprehensive product info (details + inventory + reviews) in one shot
# Sub-agents: details_agent, inventory_agent, reviews_agent
# Execution: All 3 agents run SIMULTANEOUSLY (concurrent)
# Performance: 180ms total vs. 450ms sequential (3x speedup!)
# Benefit: Faster responses by parallelizing independent data fetching

# details_config = get_agent_config("details_fetcher")
# details_agent = Agent(
#     name=details_config["name"],
#     model=details_config["model"],
#     instruction=details_config["instruction"],
#     tools=[get_product_details]
# )
#
# inventory_config = get_agent_config("inventory_checker")
# inventory_agent = Agent(
#     name=inventory_config["name"],
#     model=inventory_config["model"],
#     instruction=inventory_config["instruction"],
#     tools=[check_inventory]
# )
#
# reviews_config = get_agent_config("reviews_fetcher")
# reviews_agent = Agent(
#     name=reviews_config["name"],
#     model=reviews_config["model"],
#     instruction=reviews_config["instruction"],
#     tools=[get_product_reviews]
# )
#
# parallel_product_lookup = ParallelAgent(
#     name="comprehensive_product_lookup",
#     description="""Get comprehensive information for ONE product including details, inventory, AND reviews all at once.
#
# USE THIS TOOL WHEN:
# - User asks for "full details including inventory and reviews"
# - User asks for "everything about PROD-XXX"
# - User explicitly mentions wanting inventory OR reviews OR both
# - User asks for "complete information" or "all info"
#
# DO NOT USE for simple detail-only requests.""",
#     sub_agents=[details_agent, inventory_agent, reviews_agent]
# )  # All 3 sub-agents execute concurrently!


# =============================================================================
# SEQUENTIALAGENT: Step-by-Step Workflow Pattern
# =============================================================================
# Use case: Refund requests require validation gates (order exists? → eligible? → process)
# Sub-agents: validation_agent → eligibility_agent → refund_processor
# Execution: Agents run IN ORDER (sequential, one after another)
# Benefit: Each step must PASS before proceeding (prevents invalid refunds)
# Example: If validation fails (order doesn't exist), workflow stops immediately

validator_config = get_agent_config("order_validator")
validation_agent = Agent(
    name=validator_config["name"],
    model=validator_config["model"],
    description="Validates that the order ID exists in the system",
    instruction=validator_config["instruction"],
    tools=[validate_order_id],
    output_key="order_status"  # Save validation result to state
)

eligibility_config = get_agent_config("eligibility_checker")
eligibility_agent = Agent(
    name=eligibility_config["name"],
    model=eligibility_config["model"],
    description="Checks if the order is eligible for a refund based on business rules",
    instruction=eligibility_config["instruction"],
    tools=[check_refund_eligibility],
    output_key="eligibility_status"  # Save eligibility result to state
)

refund_config = get_agent_config("refund_processor")
refund_processor = Agent(
    name=refund_config["name"],
    model=refund_config["model"],
    description="Processes the refund after validation and eligibility checks pass",
    instruction=refund_config["instruction"],
    tools=[process_refund]
)

sequential_refund_workflow = SequentialAgent(
    name="refund_workflow",
    description="""Validated refund processing workflow. Handles refund requests by validating order, checking eligibility, and processing refund in sequence.

CRITICAL PREREQUISITES (CHECK BEFORE CALLING):
- Order ID MUST be present in conversation (format: ORD-XXXXX)
- Refund reason MUST be present in conversation (e.g., "broken item", "defective", "wrong item")
- DO NOT call this workflow if either is missing - ask the user first

WORKFLOW STEPS:
1. Validate Order - Confirm the order exists in the system
2. Check Eligibility - Verify the order qualifies for a refund
3. Process Refund - Execute the refund transaction

CONTEXT HANDLING:
Each sub-agent extracts order_id and reason from conversation history. Users should not be asked to repeat information already provided.

VALIDATION GATES:
If validation fails at any step, the workflow stops immediately.""",
    sub_agents=[validation_agent, eligibility_agent, refund_processor]
)  # Sub-agents execute one-by-one with validation gates


# =============================================================================
# LOOPAGENT: Iterative Execution Pattern - DISABLED (not used anymore)
# =============================================================================
# Use case: Get details for MULTIPLE products (when user asks for "both", "all", etc.)

# Product details loop controller
# loop_detail_config = get_agent_config("product_details_loop")
# product_details_fetcher = Agent(
#     name=loop_detail_config["name"],
#     model=loop_detail_config["model"],
#     description=loop_detail_config["description"],
#     instruction="""Fetch product details in a loop.
# 1. Call get_next_product_to_detail to get next product ID
# 2. If status="next_product": Call get_product_details with that product_id
# 3. If status="all_done": Call exit_product_loop to end loop""",
#     tools=[get_next_product_to_detail, get_product_details, exit_product_loop]
# )
#
# # LoopAgent that fetches details for multiple products
# multi_product_details_loop = LoopAgent(
#     name="multi_product_details",
#     description="""Get details for MULTIPLE products iteratively.
#
# USE THIS TOOL WHEN:
# - User asks for details on "all of them", "all three", "both", "all"
# - User wants details on multiple products from a previous search
# - User says "on all of them" after seeing search results
#
# This tool automatically retrieves product IDs from session state (saved by search_products).
# The loop fetches details for each product one by one until all are processed.""",
#     sub_agents=[product_details_fetcher],
#     max_iterations=10  # Safety limit to prevent infinite loops
# )
