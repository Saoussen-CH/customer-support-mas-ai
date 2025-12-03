"""
Order-related tools for the customer support system.

This module contains all tools for order tracking and order history.
"""

import logging
from typing import Dict
from google.cloud.firestore_v1.base_query import FieldFilter
from google.adk.tools.tool_context import ToolContext

# Import database client
from customer_support_agent.database import db_client


def track_order(order_id: str) -> dict:
    """Track an order by order ID.

    Args:
        order_id: The order ID to track (e.g., "ORD-12345")
    """
    doc = db_client.collection("orders").document(order_id).get()
    if doc.exists:
        data = doc.to_dict()
        return {"status": "success", "order": {
            "order_id": doc.id,
            "status": data.get("status"),
            "carrier": data.get("carrier"),
            "tracking_number": data.get("tracking_number"),
            "estimated_delivery": data.get("estimated_delivery"),
            "timeline": data.get("timeline", []),
        }}
    return {"status": "not_found"}


def get_order_history(customer_id: str) -> dict:
    """Get order history for a specific customer ID.

    Args:
        customer_id: The customer ID to get order history for
    """
    query = db_client.collection("orders").where(filter=FieldFilter("customer_id", "==", customer_id))
    orders = [{"order_id": doc.id, **doc.to_dict()} for doc in query.stream()]
    if orders:
        summaries = [{"order_id": o["order_id"], "date": o["date"], "total": o["total"], "status": o["status"]} for o in orders]
        return {"status": "success", "orders": summaries}
    return {"status": "no_orders"}


def get_my_order_history(tool_context: ToolContext) -> dict:
    """Get order history for the authenticated user. Automatically uses the logged-in user's ID.

    Args:
        tool_context: ADK ToolContext (automatically injected)
    """
    user_id = tool_context.user_id
    logging.info(f"[ORDER HISTORY] Fetching orders for authenticated user: {user_id}")

    # Query orders by user_id (not customer_id)
    # Note: We need to check if orders are indexed by user_id or customer_id
    # For now, assume customer_id == user_id from authentication
    query = db_client.collection("orders").where(filter=FieldFilter("customer_id", "==", user_id))
    orders = [{"order_id": doc.id, **doc.to_dict()} for doc in query.stream()]

    if orders:
        summaries = [{"order_id": o["order_id"], "date": o["date"], "total": o["total"], "status": o["status"]} for o in orders]
        logging.info(f"[ORDER HISTORY] Found {len(summaries)} orders for user {user_id}")
        return {"status": "success", "orders": summaries, "user_id": user_id}

    logging.info(f"[ORDER HISTORY] No orders found for user {user_id}")
    return {"status": "no_orders", "message": f"No orders found for your account.", "user_id": user_id}
