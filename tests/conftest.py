"""
Pytest configuration for agent evaluation tests.

This file configures the test environment before running tests.
"""

import os
import sys
from unittest.mock import patch

import dotenv
import pytest
import vertexai

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session", autouse=True)
def load_env_and_initialize():
    """
    Load environment variables and initialize Vertex AI before running tests.

    This fixture runs once per test session and:
    1. Loads .env file with GOOGLE_GENAI_USE_VERTEXAI and other configs
    2. Initializes Vertex AI with the project configuration

    This is required for the agents to call Gemini models via Vertex AI.
    """
    dotenv_path = os.path.join(ROOT, ".env")
    dotenv.load_dotenv(dotenv_path)

    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    STAGING_BUCKET = f"gs://{os.environ.get('GOOGLE_CLOUD_STORAGE_BUCKET', 'customer-support-adk-staging')}"

    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )

    yield


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    """Patch Firestore with an in-memory mock backed by seed data."""
    from tests.mock_firestore import MockFirestoreClient

    mock_client = MockFirestoreClient()

    with (
        patch("customer_support_agent.database.db_client", mock_client),
        patch("customer_support_agent.database.get_db_client", return_value=mock_client),
        patch("customer_support_agent.database.client.get_db_client", return_value=mock_client),
        patch("customer_support_agent.database.client.db_client", mock_client),
    ):
        # Also patch in the tools modules that import db_client at the top
        with (
            patch("customer_support_agent.tools.product_tools.db_client", mock_client),
            patch("customer_support_agent.tools.order_tools.db_client", mock_client),
            patch("customer_support_agent.tools.billing_tools.db_client", mock_client),
            patch("customer_support_agent.tools.workflow_tools.db_client", mock_client),
        ):
            yield mock_client


@pytest.fixture(scope="session", autouse=True)
def mock_rag():
    """Patch RAG search with keyword-based mock."""
    from tests.mock_rag_search import MockRAGProductSearch

    mock_instance = MockRAGProductSearch()

    with (
        patch("customer_support_agent.services.rag_search.RAGProductSearch", MockRAGProductSearch),
        patch("customer_support_agent.services.rag_search._rag_search", mock_instance),
        patch("customer_support_agent.services.rag_search.get_rag_search", return_value=mock_instance),
        patch("customer_support_agent.services.get_rag_search", return_value=mock_instance),
        patch("customer_support_agent.tools.product_tools.get_rag_search", return_value=mock_instance),
        patch("customer_support_agent.tools.product_tools.USE_RAG", True),
    ):
        yield


@pytest.fixture(autouse=True)
def verify_mock_active(mock_db):
    """Sanity check: fail fast if mock is not applied."""
    from tests.mock_firestore import MockFirestoreClient

    assert isinstance(mock_db, MockFirestoreClient), "Mock Firestore not active — tests would hit live DB!"
