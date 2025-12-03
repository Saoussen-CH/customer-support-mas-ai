"""
Workflow-related tools for the customer support system.

This module contains tools for loop workflows (multi-product details)
and sequential refund workflow tools.
"""

import logging
from typing import Dict
from google.adk.tools.tool_context import ToolContext

# Import database client for refund workflow tools
from customer_support_agent.database import db_client


# def exit_product_loop(tool_context: ToolContext):
#     """Exit the product details loop when all requested products have been processed.

#     Args:
#         tool_context: ADK ToolContext (automatically injected)
#     """
#     logging.info(f"[LoopAgent] exit_product_loop called by {tool_context.agent_name}")
#     tool_context.actions.escalate = True
#     return {"status": "All products processed, exiting loop"}


# def get_next_product_to_detail(tool_context: ToolContext) -> dict:
#     """Get the next product ID that needs details from the session state.

#     Args:
#         tool_context: ADK ToolContext (automatically injected)
#     """
#     products_to_detail = tool_context.state.get("products_to_detail", [])
#     detailed_product_ids = tool_context.state.get("detailed_product_ids", [])

#     logging.info(f"[LoopAgent] Products to detail: {products_to_detail}, Already detailed: {detailed_product_ids}")

#     # Find first product that hasn't been detailed yet
#     for product_id in products_to_detail:
#         if product_id not in detailed_product_ids:
#             detailed_product_ids.append(product_id)
#             tool_context.state['detailed_product_ids'] = detailed_product_ids
#             logging.info(f"[LoopAgent] Next product to detail: {product_id}")
#             return {"status": "next_product", "product_id": product_id}

#     # All products have been detailed
#     logging.info(f"[LoopAgent] All products detailed")
#     return {"status": "all_done", "message": "All products have been detailed"}


# =============================================================================
# Sequential Refund Workflow Tools
# =============================================================================

def validate_order_id(order_id: str, tool_context: ToolContext) -> dict:
    """Validate that an order exists in the system.

    This is the first step in the refund workflow (SequentialAgent).

    Args:
        order_id: The order ID to validate (e.g., "ORD-12345")
        tool_context: ADK ToolContext (automatically injected)

    Returns:
        dict: {"status": "valid"} if order exists, {"status": "invalid"} otherwise
    """
    logging.info(f"[Refund Workflow - Step 1] Validating order: {order_id}")
    exists = db_client.collection("orders").document(order_id).get().exists
    status = "valid" if exists else "invalid"
    logging.info(f"[Refund Workflow - Step 1] Order {order_id} validation: {status}")

    # CRITICAL: Stop workflow if order doesn't exist
    if not exists:
        logging.warning(f"[Refund Workflow - Step 1] STOPPING workflow - order {order_id} not found")
        tool_context.actions.escalate = True

    return {"status": status}


def check_refund_eligibility(order_id: str, tool_context: ToolContext) -> dict:
    """Check if an order is eligible for refund based on business rules.

    This is the second step in the refund workflow (SequentialAgent).
    Only executes if validate_order_id passes.

    Args:
        order_id: The order ID to check refund eligibility for
        tool_context: ADK ToolContext (automatically injected)

    Returns:
        dict: {
            "status": "success",
            "eligible": bool,
            "reason": str,
            "max_refund": float (if eligible)
        } or {"status": "not_found"} if eligibility record doesn't exist
    """
    logging.info(f"[Refund Workflow - Step 2] Checking eligibility for order: {order_id}")
    doc = db_client.collection("refund_eligibility").document(order_id).get()

    if doc.exists:
        result = {"status": "success", **doc.to_dict()}
        eligible = result.get("eligible", False)
        reason = result.get("reason", "Unknown")
        logging.info(f"[Refund Workflow - Step 2] Order {order_id} eligible: {eligible}, reason: {reason}")

        # CRITICAL: Stop workflow if order is not eligible for refund
        if not eligible:
            logging.warning(f"[Refund Workflow - Step 2] STOPPING workflow - order {order_id} not eligible: {reason}")
            tool_context.actions.escalate = True

        return result
    else:
        logging.warning(f"[Refund Workflow - Step 2] No eligibility record found for order: {order_id}")
        tool_context.actions.escalate = True  # Stop workflow if no eligibility data
        return {"status": "not_found"}


def process_refund(order_id: str, reason: str) -> dict:
    """Process a refund for an order.

    This is the third and final step in the refund workflow (SequentialAgent).
    Only executes if both validate_order_id and check_refund_eligibility pass.

    Args:
        order_id: The order ID to refund
        reason: The reason for the refund (e.g., "damaged", "wrong item")

    Returns:
        dict: {
            "status": "success",
            "refund_id": str,
            "message": str
        } or {"status": "error", "message": str} if order not found
    """
    logging.info(f"[Refund Workflow - Step 3] Processing refund for order: {order_id}, reason: {reason}")

    # Double-check order exists (should always pass if we got here in SequentialAgent)
    order_doc = db_client.collection("orders").document(order_id).get()
    if not order_doc.exists:
        logging.error(f"[Refund Workflow - Step 3] Order {order_id} not found (unexpected)")
        return {"status": "error", "message": "Order not found"}

    # Create refund record
    refund_id = f"REF-{order_id.replace('ORD-', '')}"
    db_client.collection("refunds").document(refund_id).set({
        "order_id": order_id,
        "reason": reason,
        "status": "pending"
    })

    logging.info(f"[Refund Workflow - Step 3] Refund created: {refund_id}")
    return {
        "status": "success",
        "refund_id": refund_id,
        "message": "Refund submitted"
    }
