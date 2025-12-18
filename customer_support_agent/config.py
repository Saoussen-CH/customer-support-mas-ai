"""
Configuration for Customer Support Multi-Agent System

Centralized configuration for all agents, models, and system settings.
This allows easy model upgrades, cost optimization, and environment-specific settings.

USAGE:
    from customer_support_agent.config import AGENT_CONFIGS, get_agent_config

    # Get specific agent config
    config = get_agent_config("product_agent")
    agent = Agent(
        name=config["name"],
        model=config["model"],
        description=config["description"],
        temperature=config.get("temperature", 0.1),
    )

COST OPTIMIZATION:
    - Main agents use gemini-2.5-pro for complex reasoning
    - Sub-agents use gemini-2.0-flash for simple tool calls (10x cheaper)
    - Potential 40-60% cost reduction with no quality loss
"""

import os
from typing import Dict, Any

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "customer-support-db")
ENVIRONMENT = os.environ.get("ENV", "production")

# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

# Primary model for complex reasoning (root, domain, workflow agents)
DEFAULT_MODEL = "gemini-2.5-pro"

# Fast model for simple tool calls (sub-agents)
# gemini-2.5-flash is ~10x cheaper and sufficient for simple operations
FAST_MODEL = "gemini-2.5-flash"

# Environment-specific overrides
if ENVIRONMENT == "development":
    # Use faster/cheaper models in development
    DEFAULT_MODEL = "gemini-2.5-flash"
    FAST_MODEL = "gemini-2.5-flash"

# =============================================================================
# AGENT CONFIGURATIONS
# =============================================================================

AGENT_CONFIGS = {
    # =========================================================================
    # ROOT COORDINATOR AGENT
    # =========================================================================
    "root_agent": {
        "name": "customer_support",
        "model": DEFAULT_MODEL,
        "description": "Multi-agent customer support system coordinator with routing capabilities",
        "temperature": 0.1,  # Low for consistent routing decisions
        "max_iterations": 10,  # Maximum tool calling iterations to prevent infinite loops
        "timeout": 60,  # 60 seconds timeout for entire agent execution
    },

    # =========================================================================
    # DOMAIN AGENTS (Product, Order, Billing)
    # =========================================================================
    "product_agent": {
        "name": "product_agent",
        "model": FAST_MODEL,
        "description": "Product search, recommendations, and information specialist",
        "temperature": 0.2,  # Slightly higher for helpful suggestions
        "max_iterations": 5,  # Limit tool calls to prevent hanging
        "timeout": 30,  # 30 seconds timeout
    },

    "order_agent": {
        "name": "order_agent",
        "model": FAST_MODEL,
        "description": "Order tracking, history, and status specialist",
        "temperature": 0.1,  # Low for factual order information
        "max_iterations": 3,  # Simple queries, limit iterations
        "timeout": 20,  # 20 seconds timeout
    },

    "billing_agent": {
        "name": "billing_agent",
        "model": FAST_MODEL,
        "description": "Billing, invoices, payments, and refunds specialist",
        "temperature": 0.05,  # Very low for financial accuracy
        "max_iterations": 3,  # Simple queries, limit iterations
        "timeout": 20,  # 20 seconds timeout
    },

    # =========================================================================
    # WORKFLOW PATTERN AGENTS
    # =========================================================================
    # "parallel_comprehensive": {  # DISABLED - not used anymore
    #     "name": "parallel_comprehensive_product_info",
    #     "model": DEFAULT_MODEL,
    #     "description": "Parallel execution pattern for comprehensive product information",
    #     "temperature": 0.1,
    # },

    "sequential_refund": {
        "name": "sequential_refund_workflow",
        "model": DEFAULT_MODEL,
        "description": "Sequential refund workflow with validation gates",
        "temperature": 0.1,
        "max_iterations": 5,  # 3 sub-agents + buffer
        "timeout": 40,  # 40 seconds for full workflow
    },

    # "loop_multi_product": {  # DISABLED - not used anymore
    #     "name": "loop_multi_product_details",
    #     "model": DEFAULT_MODEL,
    #     "description": "Loop pattern for iterative multi-product details",
    #     "temperature": 0.1,
    # },
    #
    # "product_details_loop": {  # DISABLED - not used anymore
    #     "name": "product_details_agent",
    #     "model": FAST_MODEL,
    #     "description": "Product details fetcher for loop iteration",
    #     "temperature": 0.1,
    # },

    # =========================================================================
    # SUB-AGENTS (ParallelAgent components) - DISABLED (not used anymore)
    # =========================================================================
    # These agents perform simple tool calls - use FAST_MODEL for cost savings
    # "details_fetcher": {
    #     "name": "details_fetcher",
    #     "model": FAST_MODEL,
    #     "instruction": """Get product details.
    #
    # TASK: Extract the product_id from the conversation context and call get_product_details(product_id).
    #
    # IMPORTANT: You MUST call the get_product_details tool with the product_id extracted from user messages or conversation history.""",
    #     "temperature": 0.1,
    # },
    #
    # "inventory_checker": {
    #     "name": "inventory_checker",
    #     "model": FAST_MODEL,
    #     "instruction": """Check product inventory levels.
    #
    # TASK: Extract the product_id from the conversation context and call check_inventory(product_id) to get stock levels.
    #
    # IMPORTANT: You MUST call the check_inventory tool with the product_id extracted from user messages or conversation history.""",
    #     "temperature": 0.1,
    # },
    #
    # "reviews_fetcher": {
    #     "name": "reviews_fetcher",
    #     "model": FAST_MODEL,
    #     "instruction": """Get product reviews.
    #
    # TASK: Extract the product_id from the conversation context and call get_product_reviews(product_id).
    #
    # IMPORTANT: You MUST call the get_product_reviews tool with the product_id extracted from user messages or conversation history.""",
    #     "temperature": 0.1,
    # },

    # =========================================================================
    # SUB-AGENTS (SequentialAgent components)
    # =========================================================================
    "order_validator": {
        "name": "order_validator",
        "model": FAST_MODEL,
        "instruction": """Validate the order ID using the validate_order_id tool.

EXTRACT FROM CONTEXT:
- Find the order ID mentioned in the conversation (format: ORD-XXXXX or ORD-12345)
- Look in the current user message and previous messages

THEN:
- Call validate_order_id(order_id="ORD-XXXXX") with the extracted order ID
- DO NOT ask the user for the order ID if it's already in the conversation

OUTPUT:
- If tool returns status="valid": Output ONLY the word "valid"
- If tool returns status="invalid": Output ONLY the word "invalid"

CRITICAL:
- Call the tool exactly ONCE and return the result
- Your final response MUST be a single word: either "valid" or "invalid"
- Do not add explanations or additional text""",
        "temperature": 0.1,
        "max_iterations": 2,  # One tool call max
        "timeout": 10,  # 10 seconds timeout
    },

    "eligibility_checker": {
        "name": "eligibility_checker",
        "model": FAST_MODEL,
        "instruction": """Check refund eligibility using the check_refund_eligibility tool.

CRITICAL VALIDATION GATE:
- First check the session state variable {order_status}
- If order_status == "invalid":
  * DO NOT call any tools
  * Output ONLY: "order_not_found"
  * STOP immediately

IF order_status == "valid":
EXTRACT FROM CONTEXT:
- Find the order ID mentioned in the conversation (format: ORD-XXXXX)

THEN:
- Call check_refund_eligibility(order_id="ORD-XXXXX") with the order ID
- DO NOT ask the user for information already provided

OUTPUT:
- If tool returns eligible=True: Output ONLY "eligible"
- If tool returns eligible=False: Output ONLY "ineligible"
- If tool returns status="not_found": Output ONLY "no_eligibility_data"

CRITICAL:
- Your final response MUST be a single word
- Do not add explanations or additional text""",
        "temperature": 0.1,
        "max_iterations": 2,  # One tool call max
        "timeout": 10,  # 10 seconds timeout
    },

    "refund_processor": {
        "name": "refund_processor",
        "model": FAST_MODEL,
        "instruction": """Process the refund using the process_refund tool.

CRITICAL VALIDATION GATES:
Step 1: Check session state variable {order_status}
- If order_status == "invalid":
  * DO NOT call any tools
  * Respond: "I cannot process the refund because the order was not found in our system."
  * STOP immediately

Step 2: Check session state variable {eligibility_status}
- If eligibility_status == "order_not_found":
  * Respond: "I cannot process the refund because the order was not found."
  * STOP immediately
- If eligibility_status == "ineligible":
  * DO NOT call any tools
  * Respond: "I cannot process the refund because the order is not eligible for a refund."
  * STOP immediately
- If eligibility_status == "no_eligibility_data":
  * Respond: "I cannot process the refund due to missing eligibility information."
  * STOP immediately

IF BOTH CHECKS PASS (order_status=="valid" AND eligibility_status=="eligible"):
EXTRACT FROM CONTEXT:
- Find the order ID mentioned in the conversation (format: ORD-XXXXX)
- Find the refund reason mentioned by the user (e.g., "broken item", "defective", "wrong item", etc.)
- Look through all previous messages in the conversation

CHECK FOR REQUIRED INFORMATION:
- If the refund REASON is MISSING or NOT PROVIDED:
  * DO NOT call process_refund tool yet
  * Ask the user: "I can help you with that refund. Could you please tell me the reason for your refund request?"
  * WAIT for user response with the reason
  * STOP and do not proceed until reason is provided

ONLY WHEN BOTH order_id AND reason ARE AVAILABLE:
- Call process_refund(order_id="ORD-XXXXX", reason="...") with BOTH parameters
- The reason MUST come from the user, never use a default value

CRITICAL:
- ONLY call process_refund if both validation gates passed AND reason is provided
- Do not process refunds for invalid or ineligible orders
- Do not process refunds without a user-provided reason""",
        "temperature": 0.1,
        "max_iterations": 3,  # Allow asking for reason + processing refund
        "timeout": 15,  # 15 seconds timeout (increased for user interaction)
    },
}

# =============================================================================
# RAG SEARCH CONFIGURATION
# =============================================================================

RAG_CONFIG = {
    "embedding_model": "text-embedding-004",
    "embedding_dimension": 768,
    "similarity_threshold": 0.7,
    "max_results": 10,
    "fallback_to_keyword": True,
}

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOGGING_CONFIG = {
    "level": os.environ.get("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_agent_config(agent_key: str) -> Dict[str, Any]:
    """
    Get configuration for a specific agent.

    Args:
        agent_key: Key from AGENT_CONFIGS (e.g., "product_agent")

    Returns:
        Agent configuration dictionary

    Raises:
        KeyError: If agent_key not found in AGENT_CONFIGS
    """
    if agent_key not in AGENT_CONFIGS:
        raise KeyError(
            f"Agent '{agent_key}' not found in AGENT_CONFIGS. "
            f"Available agents: {list(AGENT_CONFIGS.keys())}"
        )
    return AGENT_CONFIGS[agent_key]


def get_model_for_agent(agent_key: str) -> str:
    """
    Get model name for a specific agent.

    Args:
        agent_key: Key from AGENT_CONFIGS

    Returns:
        Model name (e.g., "gemini-2.5-pro")
    """
    return get_agent_config(agent_key)["model"]


def get_temperature_for_agent(agent_key: str) -> float:
    """
    Get temperature for a specific agent.

    Args:
        agent_key: Key from AGENT_CONFIGS

    Returns:
        Temperature value (default: 0.1)
    """
    return get_agent_config(agent_key).get("temperature", 0.1)


def list_agents_by_model() -> Dict[str, list]:
    """
    List all agents grouped by model.

    Returns:
        Dictionary mapping model names to list of agent keys
    """
    agents_by_model = {}
    for agent_key, config in AGENT_CONFIGS.items():
        model = config["model"]
        if model not in agents_by_model:
            agents_by_model[model] = []
        agents_by_model[model].append(agent_key)
    return agents_by_model


def print_config_summary():
    """Print a summary of the current configuration."""
    print("=" * 80)
    print("CUSTOMER SUPPORT AGENT CONFIGURATION")
    print("=" * 80)
    print(f"Environment: {ENVIRONMENT}")
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Database: {FIRESTORE_DATABASE}")
    print(f"\nDefault Model: {DEFAULT_MODEL}")
    print(f"Fast Model: {FAST_MODEL}")
    print(f"\nTotal Agents: {len(AGENT_CONFIGS)}")

    print("\nAgents by Model:")
    for model, agents in list_agents_by_model().items():
        print(f"  {model}: {len(agents)} agents")
        for agent in agents:
            print(f"    - {agent}")
    print("=" * 80)


# Print config summary on import (for debugging)
if __name__ == "__main__":
    print_config_summary()
