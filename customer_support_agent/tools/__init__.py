"""
Tools for the customer support multi-agent system.

This module exports all tools used by the agents.

Security: All user-specific tools verify ownership using decorators from
customer_support_agent.auth. Users can only access their own data.

Tool Categories:
- Product tools: Global data, no ownership required
- Order tools: User's orders only (ownership verified)
- Billing tools: User's invoices/payments only (ownership verified)
- Workflow tools: Refund processing (ownership verified)
"""

# Product tools (global data - no ownership required)
# Billing tools (ownership verified)
from customer_support_agent.tools.billing_tools import (
    check_payment_status,  # Verifies ownership
    get_invoice,  # Verifies ownership
    get_invoice_by_order_id,  # Verifies ownership
    get_my_invoices,  # Uses authenticated user
    get_my_payments,  # Uses authenticated user
)

# Order tools (ownership verified)
from customer_support_agent.tools.order_tools import (
    get_my_order_history,  # Uses authenticated user (summary)
    get_order_details,  # Verifies ownership
    get_order_history,  # Uses authenticated user
    track_order,  # Verifies ownership
)
from customer_support_agent.tools.product_tools import (
    check_inventory,
    get_all_saved_products_info,  # Get all products from last search
    get_last_mentioned_product,
    get_product_details,
    get_product_info,  # Smart unified tool (recommended)
    get_product_reviews,
    search_products,
)

# Workflow tools (ownership verified)
from customer_support_agent.tools.workflow_tools import (
    # Pre-check tool for conversational refund flow
    check_if_refundable,  # Pre-check eligibility before asking for reason
    check_refund_eligibility,  # Step 2: Dynamic eligibility (30-day window, duplicates)
    get_acceptable_refund_reasons,  # Helper: List acceptable/unacceptable reasons
    get_refundable_items,  # Helper: Check what items can still be refunded
    process_refund,  # Step 3: Creates refund record (validates reason)
    # Sequential refund workflow tools (all verify ownership)
    validate_refund_request,  # Step 1: Validates ownership, delivery status, items
)

__all__ = [
    # Product tools (global - no auth required)
    "search_products",
    "get_product_details",
    "get_last_mentioned_product",
    "check_inventory",
    "get_product_reviews",
    "get_product_info",
    "get_all_saved_products_info",
    # Order tools (ownership verified)
    "track_order",
    "get_order_history",
    "get_my_order_history",
    "get_order_details",
    # Billing tools (ownership verified)
    "get_invoice",
    "get_invoice_by_order_id",
    "get_my_invoices",
    "check_payment_status",
    "get_my_payments",
    # Workflow tools (ownership verified)
    "check_if_refundable",
    "validate_refund_request",
    "check_refund_eligibility",
    "process_refund",
    "get_refundable_items",
    "get_acceptable_refund_reasons",
]
