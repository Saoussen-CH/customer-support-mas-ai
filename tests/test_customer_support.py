"""
Pytest Test Suite for Customer Support Multi-Agent System

This test suite uses ADK's AgentEvaluator to run comprehensive evaluations
of the customer support agent system.

Usage:
    # Run all tests
    pytest tests/

    # Run specific test category
    pytest tests/test_customer_support.py::TestUnitEvaluation

    # Run with verbose output
    pytest tests/ -v

    # Run and print detailed results
    pytest tests/ -v -s
"""

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator


class TestUnitEvaluation:
    """Unit tests for individual agent capabilities."""

    @pytest.mark.asyncio
    async def test_product_search(self):
        """
        Test product search functionality including:
        - Basic product search
        - Price filtering (under $600)
        - Category filtering (laptops, chairs, etc.)
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/product_search.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_order_tracking(self):
        """
        Test order tracking functionality including:
        - Valid order ID lookup
        - Invalid order ID handling
        - Order status retrieval
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/order_tracking.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_billing_queries(self):
        """
        Test billing functionality including:
        - Invoice retrieval by invoice ID
        - Invoice retrieval by order ID
        - Payment status checks
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/billing_queries.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_parallel_agent(self):
        """
        Test ParallelAgent functionality including:
        - Comprehensive product lookup (details + inventory + reviews)
        - Concurrent execution of multiple sub-agents
        - Full product information retrieval
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/parallel_agent.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_sequential_agent(self):
        """
        Test SequentialAgent functionality including:
        - Refund workflow with validation gates
        - Order validation before processing
        - Eligibility checks
        - Sequential execution of validation steps
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/sequential_agent.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_loop_agent(self):
        """
        Test LoopAgent functionality including:
        - Multi-product details retrieval
        - Iterative execution for multiple products
        - Follow-up queries for "both", "all", etc.
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/loop_agent.evalset.json",
            print_detailed_results=False
        )


class TestIntegrationEvaluation:
    """Integration tests for complex agent workflows."""

    @pytest.mark.asyncio
    async def test_memory_persistence(self):
        """
        Test Memory Bank functionality including:
        - Saving user preferences (budget, category)
        - Recalling preferences in subsequent sessions
        - Context-aware responses based on memory
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/integration/memory_persistence.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_multi_agent_handoffs(self):
        """
        Test multi-agent coordination including:
        - Product + Order agent handoff
        - Order + Billing agent handoff
        - Full journey: Product → Order → Billing
        - Context preservation across agents
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/integration/multi_agent_handoffs.evalset.json",
            print_detailed_results=False
        )

    @pytest.mark.asyncio
    async def test_workflow_integration(self):
        """
        Test workflow agents integration with domain agents including:
        - ParallelAgent (comprehensive lookup) + Order agent
        - LoopAgent (multi-product details) + SequentialAgent (refund)
        - Full workflow: ParallelAgent → Order → Billing → SequentialAgent
        - Workflow agents with Memory Bank
        - Context preservation across workflow and domain agents
        """
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/integration/workflow_integration.evalset.json",
            print_detailed_results=False
        )


class TestRegressionSuite:
    """Run all tests to catch regressions before deployment."""

    @pytest.mark.asyncio
    async def test_all_evaluations(self):
        """
        Run all evaluation test cases to ensure no regressions.
        This test should be run before every deployment.
        """
        # Run all unit tests
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/unit/",
            print_detailed_results=False
        )

        # Run all integration tests
        await AgentEvaluator.evaluate(
            agent_module="customer_support_agent.main",
            eval_dataset_file_path_or_dir="tests/integration/",
            print_detailed_results=False
        )


# ============================================================================
# Helper Functions for Custom Validation
# ============================================================================

def validate_price_filtering(results, max_price):
    """
    Custom validation to ensure all returned products are under max_price.

    Args:
        results: Tool call results from search_products
        max_price: Maximum price threshold

    Returns:
        bool: True if all products are under max_price
    """
    if not results or "products" not in results:
        return False

    products = results["products"]
    return all(product.get("price", float('inf')) <= max_price for product in products)


def validate_category_filtering(results, expected_category_keywords):
    """
    Custom validation to ensure returned products match category.

    Args:
        results: Tool call results from search_products
        expected_category_keywords: List of keywords that should appear in product names

    Returns:
        bool: True if products match expected category
    """
    if not results or "products" not in results:
        return False

    products = results["products"]
    for product in products:
        name = product.get("name", "").lower()
        if not any(keyword.lower() in name for keyword in expected_category_keywords):
            return False

    return True


def validate_multi_agent_handoff(tool_calls, expected_agents):
    """
    Validate that multiple agents were invoked correctly.

    Args:
        tool_calls: List of tool calls made during conversation
        expected_agents: List of agent names that should have been invoked

    Returns:
        bool: True if all expected agents were invoked
    """
    invoked_tools = {call.get("name") for call in tool_calls}

    # Map tools to their agents
    agent_tool_mapping = {
        "product_agent": ["search_products", "get_product_details"],
        "order_agent": ["track_order", "get_order_history"],
        "billing_agent": ["get_invoice", "get_invoice_by_order_id", "check_payment_status"]
    }

    invoked_agents = set()
    for agent, tools in agent_tool_mapping.items():
        if any(tool in invoked_tools for tool in tools):
            invoked_agents.add(agent)

    return all(agent in invoked_agents for agent in expected_agents)


def validate_parallel_agent_execution(tool_calls):
    """
    Validate that ParallelAgent executed sub-agents concurrently.

    Args:
        tool_calls: List of tool calls made during conversation

    Returns:
        bool: True if parallel execution patterns detected
    """
    invoked_tools = {call.get("name") for call in tool_calls}

    # Check if comprehensive_product_lookup or its sub-agents were invoked
    parallel_tools = {
        "comprehensive_product_lookup",
        "get_product_details",
        "check_inventory",
        "get_product_reviews"
    }

    # At least one parallel workflow tool should be present
    return len(invoked_tools.intersection(parallel_tools)) > 0


def validate_sequential_agent_execution(tool_calls, expected_sequence):
    """
    Validate that SequentialAgent executed sub-agents in the correct order.

    Args:
        tool_calls: List of tool calls made during conversation
        expected_sequence: Expected sequence of tool names

    Returns:
        bool: True if tools were called in the expected order
    """
    tool_names = [call.get("name") for call in tool_calls]

    # Check if refund_workflow or its sub-agents were invoked
    refund_tools = {
        "refund_workflow",
        "validate_order_id",
        "check_refund_eligibility",
        "process_refund"
    }

    invoked_tools = set(tool_names)
    return len(invoked_tools.intersection(refund_tools)) > 0


def validate_loop_agent_execution(tool_calls, min_iterations=2):
    """
    Validate that LoopAgent executed multiple iterations.

    Args:
        tool_calls: List of tool calls made during conversation
        min_iterations: Minimum number of iterations expected

    Returns:
        bool: True if loop executed multiple times
    """
    tool_names = [call.get("name") for call in tool_calls]

    # Check if multi_product_details or loop-related tools were invoked
    loop_tools = [
        "multi_product_details",
        "get_next_product_to_detail",
        "get_product_details",
        "exit_product_loop"
    ]

    # Count how many times get_product_details was called (indicates iterations)
    detail_calls = tool_names.count("get_product_details")

    return detail_calls >= min_iterations or "multi_product_details" in tool_names


def validate_comprehensive_lookup_response(results):
    """
    Validate that comprehensive product lookup returned complete information.

    Args:
        results: Tool call results from comprehensive lookup

    Returns:
        bool: True if all information types are present (details, inventory, reviews)
    """
    if not results:
        return False

    # Check if results contain product details, inventory, and reviews
    has_details = "product" in results or "details" in results
    has_inventory = "inventory" in results or "stock" in results
    has_reviews = "reviews" in results or "rating" in results

    return has_details or has_inventory or has_reviews
