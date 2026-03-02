"""
Pytest configuration for CI/CD unit tests.

Uses Vertex AI Gemini API for LLM calls (NOT Agent Engine).
Runs agent locally via AgentEvaluator.
Mock backends are applied so evaluation re-runs see the same data
that was used to generate the eval datasets.
"""

import logging
import os
import sys
from unittest.mock import patch

import dotenv
import pytest
import vertexai

logger = logging.getLogger(__name__)

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session", autouse=True)
def ci_environment_setup():
    """
    Setup for CI environment - Uses Vertex AI Gemini API (NOT Agent Engine).

    This fixture:
    1. Loads .env for GCP credentials
    2. Initializes Vertex AI for Gemini API calls
    3. Does NOT use Agent Engine deployed resource
    """
    logger.info("[CI SETUP] Loading environment for CI/CD testing...")

    # Load .env from project root
    dotenv_path = os.path.join(ROOT, ".env")
    if os.path.exists(dotenv_path):
        dotenv.load_dotenv(dotenv_path)
        logger.info("[CI SETUP] Loaded .env from %s", dotenv_path)

    # Configuration
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not PROJECT_ID:
        pytest.skip("GOOGLE_CLOUD_PROJECT not set - skipping CI tests")

    logger.info("[CI SETUP] Initializing Vertex AI Gemini API...")
    logger.info("  Project: %s", PROJECT_ID)
    logger.info("  Location: %s", LOCATION)
    logger.info("  Mode: Local agent execution (NOT Agent Engine)")

    # Initialize Vertex AI for Gemini API calls only
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
    )

    # Ensure we're using Vertex AI for Gemini
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

    logger.info("[CI SETUP] Vertex AI Gemini API ready")

    yield

    logger.info("[CI TEARDOWN] CI test session complete")


@pytest.fixture(autouse=True)
def mock_backends():
    """Apply mock Firestore + RAG backends for agent evaluation re-runs.

    The eval datasets were generated with mocked backends (MockFirestoreClient
    and MockRAGProductSearch). The AgentEvaluator re-runs the agent during
    evaluation, so the same mocks must be active for tool trajectories to match.
    """
    from tests.mock_firestore import MockFirestoreClient
    from tests.mock_rag_search import MockRAGProductSearch

    mock_db = MockFirestoreClient()
    mock_rag = MockRAGProductSearch()

    patches = [
        patch("customer_support_agent.database.db_client", mock_db),
        patch("customer_support_agent.database.get_db_client", return_value=mock_db),
        patch("customer_support_agent.database.client.get_db_client", return_value=mock_db),
        patch("customer_support_agent.database.client.db_client", mock_db),
        patch("customer_support_agent.tools.product_tools.db_client", mock_db),
        patch("customer_support_agent.tools.order_tools.db_client", mock_db),
        patch("customer_support_agent.tools.billing_tools.db_client", mock_db),
        patch("customer_support_agent.tools.workflow_tools.db_client", mock_db),
        patch("customer_support_agent.services.rag_search.RAGProductSearch", MockRAGProductSearch),
        patch("customer_support_agent.services.rag_search._rag_search", mock_rag),
        patch("customer_support_agent.services.rag_search.get_rag_search", return_value=mock_rag),
        patch("customer_support_agent.services.get_rag_search", return_value=mock_rag),
        patch("customer_support_agent.tools.product_tools.get_rag_search", return_value=mock_rag),
        patch("customer_support_agent.tools.product_tools.USE_RAG", True),
    ]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()
