"""
Tools for the customer support multi-agent system.

This module exports all tools used by the agents.
"""

# Product tools
from customer_support_agent.tools.product_tools import (
    search_products,
    get_product_details,
    get_last_mentioned_product,
    check_inventory,
    get_product_reviews,
    get_product_info,  # Smart unified tool (recommended)
    get_all_saved_products_info,  # Get all products from last search
)

# Order tools
from customer_support_agent.tools.order_tools import (
    track_order,
    get_order_history,
    get_my_order_history,
)

# Billing tools
from customer_support_agent.tools.billing_tools import (
    get_invoice,
    get_invoice_by_order_id,
    check_payment_status,
)

# Workflow tools
from customer_support_agent.tools.workflow_tools import (
    #exit_product_loop,
    #get_next_product_to_detail,
    # Sequential refund workflow tools
    validate_order_id,
    check_refund_eligibility,
    process_refund,
)

__all__ = [
    # Product tools
    "search_products",
    "get_product_details",
    "get_last_mentioned_product",
    "check_inventory",
    "get_product_reviews",
    "get_product_info",  # Smart unified tool
    "get_all_saved_products_info",  # Get all products from last search
    # Order tools
    "track_order",
    "get_order_history",
    "get_my_order_history",
    # Billing tools
    "get_invoice",
    "get_invoice_by_order_id",
    "check_payment_status",
    "process_refund",
    "validate_order_id",
    "check_refund_eligibility",
    # Workflow tools
    "exit_product_loop",
    "get_next_product_to_detail",
]
