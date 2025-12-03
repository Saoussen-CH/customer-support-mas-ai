"""
Order agent for the customer support system.

This module contains the order specialist agent that handles order tracking and history.
"""

from google.adk.agents import Agent
from google.adk.tools import preload_memory_tool

# Import centralized configuration
from customer_support_agent.config import get_agent_config

# Import tools
from customer_support_agent.tools import (
    track_order,
    get_my_order_history,
)

# Import callbacks
from customer_support_agent.agents.callbacks import auto_save_to_memory, track_agent_start
from customer_support_agent.agents.callbacks_explicit import auto_save_to_memory_explicit
from customer_support_agent.agents.callbacks_sdk import auto_save_to_memory_sdk


# =============================================================================
# ORDER AGENT
# =============================================================================

order_config = get_agent_config("order_agent")
order_agent = Agent(
    name=order_config["name"],
    model=order_config["model"],
    description=order_config["description"],
    instruction="""You help customers track orders and view order history.

AUTHENTICATED USER BEHAVIOR:
- The user is already logged in - their identity is automatically available
- NEVER ask for customer ID - use get_my_order_history() which automatically uses the authenticated user
- For specific order tracking, use track_order() with the order ID

MEMORY-AWARE BEHAVIOR:
- Check preloaded memories for recurring delivery issues or patterns
- If customer had past delivery problems, acknowledge and provide extra tracking details
- Remember preferred delivery times or locations mentioned previously
- Identify patterns like "customer always asks about orders on Fridays"

Key behaviors:
- Use track_order() to get tracking details for specific order IDs (e.g., "track ORD-12345")
- Use get_my_order_history() to show all orders for the LOGGED-IN user (NEVER ask for customer ID!)
- **CRITICAL: REMEMBER order IDs from conversation history** - Check previous messages for order IDs
- When user asks follow-up questions ("what's the tracking number?", "when will it arrive?"), look back in conversation for the order ID
- **NEVER ask "what is the order id?" if an order ID was just discussed** - extract it from conversation history
- Provide clear tracking information with estimated delivery dates

CRITICAL: When user asks "show my orders", "my recent orders", or "order history", immediately call get_my_order_history() - do NOT ask for customer ID!

Be helpful and proactive - if you see delays, mention them.""",
    tools=[
        track_order,
        get_my_order_history,  # Uses authenticated user automatically
        preload_memory_tool.PreloadMemoryTool()
    ],
    #before_agent_callback=track_agent_start,  # Track when agent starts
    # after_agent_callback=auto_save_to_memory,  # IMPLICIT (invocation context)
    # after_agent_callback=auto_save_to_memory_explicit,  # EXPLICIT (notebook pattern)
    after_agent_callback=auto_save_to_memory_sdk,  # SDK (official approach)
)
