"""
Billing-related tools for the customer support system.

This module contains all tools for invoices, payments, and refunds.
"""

import logging
from typing import Dict
from google.cloud.firestore_v1.base_query import FieldFilter

# Import database client
from customer_support_agent.database import db_client


def get_invoice(invoice_id: str) -> dict:
    """Get invoice by invoice ID (e.g., INV-2025-001).

    Args:
        invoice_id: The invoice ID to retrieve
    """
    doc = db_client.collection("invoices").document(invoice_id).get()
    if doc.exists:
        return {"status": "success", "invoice": {"invoice_id": doc.id, **doc.to_dict()}}
    return {"status": "not_found"}


def get_invoice_by_order_id(order_id: str) -> dict:
    """Get invoice by order ID (e.g., ORD-12345). Use this when customer asks for invoice for a specific order.

    Args:
        order_id: The order ID to get the invoice for
    """
    query = db_client.collection("invoices").where(filter=FieldFilter("order_id", "==", order_id))
    invoices = list(query.stream())
    if invoices:
        doc = invoices[0]  # Assume one invoice per order
        return {"status": "success", "invoice": {"invoice_id": doc.id, **doc.to_dict()}}
    return {"status": "not_found", "message": f"No invoice found for order {order_id}"}


def check_payment_status(order_id: str) -> dict:
    """Check payment status for an order.

    Args:
        order_id: The order ID to check payment status for
    """
    doc = db_client.collection("payments").document(order_id).get()
    if doc.exists:
        return {"status": "success", "payment": {"order_id": doc.id, **doc.to_dict()}}
    return {"status": "not_found"}
