"""
Billing agent for the customer support system.

This module contains the billing specialist agent that handles invoices, payments, and refunds.
"""

from google.adk.agents import Agent
from google.adk.tools import preload_memory_tool

# Import centralized configuration
from customer_support_agent.config import get_agent_config

# Import tools
from customer_support_agent.tools import (
    get_invoice,
    get_invoice_by_order_id,
    check_payment_status,
    # process_refund,  # REMOVED - use refund_workflow for proper validation
)

# Import callbacks
from customer_support_agent.agents.callbacks import auto_save_to_memory, track_agent_start
from customer_support_agent.agents.callbacks_explicit import auto_save_to_memory_explicit
from customer_support_agent.agents.callbacks_sdk import auto_save_to_memory_sdk


# =============================================================================
# BILLING AGENT
# =============================================================================

billing_config = get_agent_config("billing_agent")
billing_agent = Agent(
    name=billing_config["name"],
    model=billing_config["model"],
    description=billing_config["description"],
    instruction="""You handle billing inquiries, invoices, and payment status.

MEMORY-AWARE BEHAVIOR:
- Check preloaded memories for preferred payment methods or past billing issues
- If customer had payment problems before, offer proactive assistance
- Remember refund history to provide better context
- Recognize patterns like "customer always pays with credit card"

Key behaviors:
- Use get_invoice_by_order_id() when customer asks for invoice by order (e.g., "invoice for ORD-12345")
- Use get_invoice() when customer provides specific invoice ID (e.g., "show me INV-2025-001")
- Use check_payment_status() for payment inquiries
- For REFUND requests: Do NOT process them here - inform the user that refunds require validation and the coordinator will route them to the refund workflow
- REMEMBER invoice and order IDs from the conversation
- Understand follow-ups like "what's the status?" refer to previously mentioned invoice/order

Be clear about payment amounts and due dates.""",
    tools=[
        get_invoice,
        get_invoice_by_order_id,
        check_payment_status,
        # process_refund,  # REMOVED - use refund_workflow for proper validation
        preload_memory_tool.PreloadMemoryTool()
    ],
    #before_agent_callback=track_agent_start,  # Track when agent starts
    # after_agent_callback=auto_save_to_memory,  # IMPLICIT (invocation context)
    # after_agent_callback=auto_save_to_memory_explicit,  # EXPLICIT (notebook pattern)
    after_agent_callback=auto_save_to_memory_sdk,  # SDK (official approach)
)
