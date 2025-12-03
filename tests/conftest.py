"""
Pytest configuration for agent evaluation tests.

This file configures the test environment before running tests.
"""

import sys
import os
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
    print(f"\n[SETUP] Loading environment variables from .env...")
    # Load .env from project root
    dotenv_path = os.path.join(ROOT, ".env")
    dotenv.load_dotenv(dotenv_path)

    # Configuration - read from environment or use defaults
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    STAGING_BUCKET = f"gs://{os.environ.get('GOOGLE_CLOUD_STORAGE_BUCKET', 'customer-support-adk-staging')}"

    print(f"[SETUP] Initializing Vertex AI...")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Use Vertex AI: {os.environ.get('GOOGLE_GENAI_USE_VERTEXAI', 'not set')}")

    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )

    print("[SETUP] Vertex AI initialized successfully ✓")

    yield  # Tests run here

    print("\n[TEARDOWN] Test session complete")
