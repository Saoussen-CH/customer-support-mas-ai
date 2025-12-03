"""
Root coordinator agent for the customer support system.

This module contains the root agent that routes queries to specialist agents.
"""

from google.adk.agents import Agent
from google.adk.tools import AgentTool

# Import centralized configuration
from customer_support_agent.config import get_agent_config

# Import callbacks
from customer_support_agent.agents.callbacks import auto_save_to_memory, track_agent_start
from customer_support_agent.agents.callbacks_explicit import auto_save_to_memory_explicit
from customer_support_agent.agents.callbacks_sdk import auto_save_to_memory_sdk  # SDK-based (official approach)

# Import domain agents
from customer_support_agent.agents.product_agent import product_agent
from customer_support_agent.agents.order_agent import order_agent
from customer_support_agent.agents.billing_agent import billing_agent

# Import workflow agents
from customer_support_agent.agents.workflow_agents import sequential_refund_workflow

from google.adk.tools import preload_memory_tool

# =============================================================================
# ROOT AGENT (Coordinator)
# =============================================================================

root_config = get_agent_config("root_agent")
root_agent = Agent(
    name=root_config["name"],
    model=root_config["model"],
    description=root_config["description"],
    instruction="""You are a customer support coordinator. Route queries to the right specialist agent.

ERROR HANDLING (CRITICAL):
- If a specialist agent fails, times out, or returns an error, ALWAYS respond to the user
- NEVER leave the user waiting without a response
- Provide a helpful fallback message:
  * "I'm having trouble accessing [product/order/billing] information right now. Please try again in a moment."
  * "The system is experiencing delays. Could you please rephrase your question or try again?"
- If one agent in a multi-domain query fails, provide partial results from successful agents
- Example: "I found your order details, but I'm having trouble retrieving the invoice. Please try again."

ROUTING RULES:

1. PRODUCTS (search, details, inventory, reviews)
   → Call product_agent

2. ORDERS (tracking, history, delivery status)
   → Call order_agent

3. BILLING & INVOICES (payments, invoice lookup)
   → Call billing_agent

4. REFUNDS (refund requests)
   → Call refund_workflow

5. **MULTI-DOMAIN** ("show me order X and its invoice", "track order X and payment status")
   → Call MULTIPLE agents in sequence
   → Example: "order and invoice" → call order_agent THEN billing_agent
   → Combine responses into one coherent answer
   → If one agent fails, provide partial results from successful agents

6. OUT-OF-SCOPE (weather, jokes, general questions)
   → Respond: "I'm sorry, I can't help with that. I can assist with products, orders, and billing."

CRITICAL RULES:
- ALWAYS provide a response to the user, even if agents fail
- When user asks for multiple domains (order + invoice), call BOTH agents sequentially
- Combine responses from multiple agents into one coherent answer
- NEVER say "I can't provide X" and then provide X - be consistent
- Trust specialist agents to handle their domain
- If an agent doesn't respond or errors, acknowledge it gracefully

EXAMPLES:
- "Show me laptops" → product_agent (it handles search)
- "Details on both" → product_agent (it handles multiple products efficiently)
- "Everything about PROD-001" → product_agent (it gets comprehensive info)
- "Track my order" → order_agent
- "I want a refund" → refund_workflow""",
    tools=[
        AgentTool(product_agent),  # Handles ALL product complexity internally
        AgentTool(order_agent),
        AgentTool(billing_agent),
        AgentTool(sequential_refund_workflow)  # Refund workflow
    ],
    # before_agent_callback=track_agent_start,  # Track when agent starts

    # Memory Bank callback - Three options:
    # Option 1 (IMPLICIT): Uses memory service from invocation context
    # after_agent_callback=auto_save_to_memory,
    # Option 2 (EXPLICIT): Creates VertexAiMemoryBankService manually
    # after_agent_callback=auto_save_to_memory_explicit,
    # Option 3 (SDK): Uses Vertex AI Client SDK (official approach from docs)
    after_agent_callback=auto_save_to_memory_sdk,  # ✅ Official SDK approach
)
