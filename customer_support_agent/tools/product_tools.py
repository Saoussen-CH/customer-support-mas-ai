"""
Product-related tools for the customer support system.

This module contains all tools for product search, details, inventory, and reviews.
"""

import logging
from typing import Dict
from google.adk.tools.tool_context import ToolContext

# Import database client
from customer_support_agent.database import db_client

# Import RAG search
try:
    from customer_support_agent.services import get_rag_search
    USE_RAG = True
    print("[INIT] RAG search enabled in product_tools")
except Exception as e:
    print(f"[INIT] RAG search not available in product_tools: {e}")
    USE_RAG = False


def search_products(query: str, tool_context: ToolContext) -> dict:
    """Search for products using RAG (semantic) or keyword fallback.

    Automatically saves the first result to session state for follow-up questions.

    Args:
        query: Search query string
        tool_context: ADK ToolContext (automatically injected)
    """

    if USE_RAG:
        # Use RAG semantic search
        try:
            rag = get_rag_search()
            products = rag.search(query, limit=5)

            if products:
                # Save first product to persistent session state
                if len(products) > 0 and "id" in products[0]:
                    tool_context.state['last_product_id'] = products[0]["id"]
                    tool_context.state['last_product_name'] = products[0].get("name", "")
                    tool_context.state['last_search_query'] = query
                    print(f"[SESSION STATE] Saved: {products[0]['id']} - {products[0].get('name')}")
                    print(f"[DEBUG] State keys: last_product_id={products[0]['id']}, last_product_name={products[0].get('name')}")

                # Save ALL product IDs for multi-product details loop
                product_ids = [p["id"] for p in products if "id" in p]
                tool_context.state['products_to_detail'] = product_ids
                tool_context.state['detailed_product_ids'] = []  # Reset for new search
                print(f"[SESSION STATE] Saved {len(product_ids)} product IDs for multi-detail: {product_ids}")

                return {"status": "success", "products": products, "count": len(products), "method": "RAG"}
            return {"status": "no_results", "message": f"No products found matching '{query}'"}

        except Exception as e:
            print(f"[TOOL] RAG search failed: {e}, falling back to keyword")

    # Fallback: keyword search with plural/singular handling
    results = []
    query_lower = query.lower().strip()
    search_terms = [query_lower]
    if query_lower.endswith('s'):
        search_terms.append(query_lower[:-1])
    else:
        search_terms.append(query_lower + 's')

    for doc in db_client.collection("products").stream():
        data = doc.to_dict()
        name = data.get("name", "").lower()
        category = data.get("category", "").lower()
        keywords = data.get("keywords", [])

        match = any(term in name or term in category or term in keywords for term in search_terms)

        if match:
            results.append({
                "id": doc.id,
                "name": data.get("name"),
                "price": data.get("price"),
                "category": data.get("category")
            })

    if results:
        # Save first result to persistent session state
        if len(results) > 0:
            tool_context.state['last_product_id'] = results[0]["id"]
            tool_context.state['last_product_name'] = results[0]["name"]
            tool_context.state['last_search_query'] = query
            print(f"[SESSION STATE] Saved: {results[0]['id']} - {results[0]['name']}")
            print(f"[DEBUG] State keys: last_product_id={results[0]['id']}, last_product_name={results[0]['name']}")

        # Save ALL product IDs for multi-product details loop
        product_ids = [p["id"] for p in results if "id" in p]
        tool_context.state['products_to_detail'] = product_ids
        tool_context.state['detailed_product_ids'] = []  # Reset for new search
        print(f"[SESSION STATE] Saved {len(product_ids)} product IDs for multi-detail: {product_ids}")

        return {"status": "success", "products": results, "count": len(results), "method": "keyword"}
    return {"status": "no_results", "message": f"No products found matching '{query}'"}


def get_product_details(product_id: str) -> dict:
    """Get detailed information about a specific product by its ID.

    Args:
        product_id: The product ID (e.g., "PROD-001")
    """
    doc = db_client.collection("products").document(product_id).get()
    if doc.exists:
        data = doc.to_dict()
        # Remove embedding from response (too large)
        data.pop("embedding", None)
        return {"status": "success", "product": {"id": doc.id, **data}}
    return {"status": "not_found", "message": f"Product {product_id} not found"}


def get_last_mentioned_product(tool_context: ToolContext) -> dict:
    """IMPORTANT: Use this tool when customer asks for details about a product you just showed them.

    Triggers: "yes", "yes please", "sure", "ok", "tell me more", "details", "get details",
              "more info", "this one", "that one", "show me details", "I want details"

    This tool requires NO parameters - it automatically retrieves the last product from session state.
    DO NOT ask "which product?" - just call this tool directly!

    Args:
        tool_context: ADK ToolContext (automatically injected)
    """
    # Read from persistent session state (safe with default)
    last_product_id = tool_context.state.get("last_product_id")
    last_product_name = tool_context.state.get("last_product_name", "Unknown")

    print(f"[DEBUG] get_last_mentioned_product() called!")
    print(f"[DEBUG] Retrieved from state: product_id={last_product_id}, product_name={last_product_name}")

    if not last_product_id:
        print(f"[DEBUG] No last_product_id found in state!")
        return {
            "status": "error",
            "message": "No product was recently discussed. Please search for a product first."
        }

    print(f"[SESSION STATE] Retrieving: {last_product_id} - {last_product_name}")

    # Fetch the product details
    doc = db_client.collection("products").document(last_product_id).get()
    if doc.exists:
        data = doc.to_dict()
        data.pop("embedding", None)
        return {
            "status": "success",
            "product": {"id": doc.id, **data},
            "context_note": f"This is the {last_product_name} you asked about."
        }

    return {"status": "not_found", "message": f"Product {last_product_id} not found"}


def check_inventory(product_id: str) -> dict:
    """Check inventory levels.

    Args:
        product_id: The product ID to check inventory for
    """
    doc = db_client.collection("inventory").document(product_id).get()
    if doc.exists:
        return {"status": "success", "inventory": {"product_id": doc.id, **doc.to_dict()}}
    return {"status": "not_found"}


def get_product_reviews(product_id: str) -> dict:
    """Get customer reviews for a product.

    Args:
        product_id: The product ID to get reviews for
    """
    doc = db_client.collection("reviews").document(product_id).get()
    if doc.exists:
        return {"status": "success", "reviews": {"product_id": doc.id, **doc.to_dict()}}
    return {"status": "not_found"}


def get_all_saved_products_info(tool_context: ToolContext) -> dict:
    """
    Get comprehensive information for ALL products from the last search.

    This tool retrieves all product IDs saved in session state and fetches
    comprehensive information (details + inventory + reviews) for each.

    **Use this tool when:**
    - User asks for "details on all of them", "all three", "both", "show me all"
    - User wants information about multiple products from the previous search

    This is MORE EFFICIENT than using LoopAgent because it fetches directly
    without iteration overhead and timeout issues.

    Args:
        tool_context: ADK ToolContext (automatically injected)

    Returns:
        Dictionary with comprehensive info for all saved products
    """
    products_to_detail = tool_context.state.get("products_to_detail", [])

    if not products_to_detail:
        return {
            "status": "error",
            "message": "No products were recently searched. Please search for products first."
        }

    print(f"[ALL PRODUCTS] Fetching info for {len(products_to_detail)} products: {products_to_detail}")

    results = {
        "status": "success",
        "count": len(products_to_detail),
        "products": []
    }

    # Fetch comprehensive info for each product
    for product_id in products_to_detail:
        product_info = get_product_info(product_id)
        if product_info.get("status") == "success":
            results["products"].append(product_info)
        else:
            results["products"].append({
                "product_id": product_id,
                "status": "not_found",
                "message": f"Product {product_id} not found"
            })

    print(f"[ALL PRODUCTS] Successfully fetched {len(results['products'])} products")

    return results


def get_product_info(
    product_id: str,
    include_details: bool = True,
    include_inventory: bool = True,
    include_reviews: bool = True
) -> dict:
    """
    Smart unified product information fetcher with automatic comprehensive data retrieval.

    **DEFAULT BEHAVIOR**: Fetches ALL information (details + inventory + reviews) for complete product info.
    This is the RECOMMENDED tool for most product queries as it provides comprehensive information efficiently.

    **Use this tool when:**
    - User asks for product information (any details about a product)
    - User mentions "full details", "everything", "complete info"
    - User explicitly asks for inventory, reviews, or stock levels
    - User wants comprehensive product data

    **Only use individual tools (get_product_details, check_inventory, get_product_reviews) when:**
    - User explicitly says "ONLY details" or "JUST the basic info"
    - User specifically requests a single piece of information

    Args:
        product_id: The product ID (e.g., "PROD-001")
        include_details: Whether to fetch product details (default: True)
        include_inventory: Whether to fetch inventory levels (default: True)
        include_reviews: Whether to fetch customer reviews (default: True)

    Returns:
        Comprehensive product information with all requested data
    """
    print(f"[SMART TOOL] get_product_info called for {product_id}")
    print(f"[SMART TOOL] Fetching - Details: {include_details}, Inventory: {include_inventory}, Reviews: {include_reviews}")

    result = {
        "status": "success",
        "product_id": product_id,
        "data_fetched": [],
        "fetch_method": "comprehensive"
    }

    # Fetch details
    if include_details:
        details = get_product_details(product_id)
        if details.get("status") == "success":
            result["details"] = details.get("product", {})
            result["data_fetched"].append("details")
        else:
            result["details_error"] = "Product not found"

    # Fetch inventory
    if include_inventory:
        inventory = check_inventory(product_id)
        if inventory.get("status") == "success":
            result["inventory"] = inventory.get("inventory", {})
            result["data_fetched"].append("inventory")
        else:
            result["inventory_error"] = "Inventory not found"

    # Fetch reviews
    if include_reviews:
        reviews = get_product_reviews(product_id)
        if reviews.get("status") == "success":
            result["reviews"] = reviews.get("reviews", {})
            result["data_fetched"].append("reviews")
        else:
            result["reviews_error"] = "Reviews not found"

    # Update status if nothing was found
    if not result["data_fetched"]:
        result["status"] = "not_found"
        result["message"] = f"No information found for product {product_id}"

    print(f"[SMART TOOL] Successfully fetched: {', '.join(result['data_fetched'])}")

    return result
