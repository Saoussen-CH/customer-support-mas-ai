"""
Deployment Script for Multi-Agent Customer Support System
==========================================================
Deploys to Vertex AI Agent Engine with Memory Bank using a two-stage approach:

  Stage 1: Deploy AdkApp → get agent_engine_id
  Stage 2: Update with Memory Bank configuration

This solves the chicken-and-egg problem where the agent_engine_id is only
known after deployment but is required to configure memory callbacks.

Usage:
    python deployment/deploy.py --action [test_local|deploy|test_remote|cleanup]
"""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

import vertexai
from dotenv import load_dotenv
from google.adk.plugins.logging_plugin import LoggingPlugin
from vertexai import Client, agent_engines

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from customer_support_agent.main import root_agent  # noqa: E402

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is required")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
if not STAGING_BUCKET:
    raise ValueError("GOOGLE_CLOUD_STORAGE_BUCKET environment variable is required")
DISPLAY_NAME = "customer-support-multiagent"


# =============================================================================
# HELPERS
# =============================================================================


def get_numeric_project_id(project_id: str) -> str:
    """Get the numeric project ID using gcloud (required for Memory Bank model paths)."""
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to get numeric project ID: {e.stderr}")
        return project_id


def init_vertex_ai():
    """Initialize Vertex AI SDK with project settings."""
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )
    print("✓ Initialized Vertex AI")
    print(f"  Project:  {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Staging:  {STAGING_BUCKET}")


# =============================================================================
# LOCAL TESTING
# =============================================================================


async def test_locally():
    """Test the agent locally before deployment."""
    print("\n" + "=" * 60)
    print("LOCAL TESTING")
    print("=" * 60)

    app = agent_engines.AdkApp(
        agent=root_agent,
        app_name="customer_support",
        enable_tracing=True,
        plugins=[LoggingPlugin()],
    )

    session = await app.async_create_session(user_id="test_user_001")
    print(f"\n✓ Created local session: {session.id}")

    test_queries = [
        "Hi, I need some help today",
        "Can you search for laptops?",
        "Where is my order ORD-12345?",
        "I need the invoice INV-2025-001",
    ]

    for i, query in enumerate(test_queries):
        if i > 0:
            print("  (waiting 5s to avoid rate limits...)")
            await asyncio.sleep(5)

        print(f"\n{'─' * 40}")
        print(f"USER: {query}")
        print(f"{'─' * 40}")

        try:
            async for event in app.async_stream_query(
                user_id="test_user_001",
                session_id=session.id,
                message=query,
            ):
                content = event.get("content", {})
                for part in content.get("parts", []):
                    if part.get("text") and not part.get("function_call"):
                        print(f"\nAGENT: {part['text']}")
                    elif part.get("function_call"):
                        fn = part["function_call"]
                        print(f"\n  → Tool: {fn['name']}({fn.get('args', {})})")
        except Exception as e:
            print(f"\n⚠️  Query failed: {e}")
            print("   Continuing with next query...")

    print("\n✓ Local testing complete!")


# =============================================================================
# DEPLOYMENT (Two-Stage with Memory Bank)
# =============================================================================


def deploy_to_agent_engine():
    """
    Deploy to Vertex AI Agent Engine with Memory Bank (two-stage).

    Stage 1: Deploy AdkApp → get agent_engine_id
    Stage 2: Update Agent Engine with Memory Bank configuration
    """
    print("\n" + "=" * 70)
    print("DEPLOYING TO VERTEX AI AGENT ENGINE (with Memory Bank)")
    print("=" * 70)

    init_vertex_ai()

    numeric_project_id = get_numeric_project_id(PROJECT_ID)
    print(f"✓ Numeric Project ID: {numeric_project_id}")

    client = Client(project=numeric_project_id, location=LOCATION)

    # -------------------------------------------------------------------------
    # Stage 1: Deploy AdkApp
    # -------------------------------------------------------------------------
    print("\n⏳ Stage 1/2: Deploying ADK agent...")

    adk_app = agent_engines.AdkApp(
        agent=root_agent,
        app_name="customer_support",
        enable_tracing=True,
        plugins=[LoggingPlugin()],
    )

    remote_app = agent_engines.create(
        agent_engine=adk_app,
        requirements=[
            "google-cloud-aiplatform[adk,agent_engines]>=1.112",
            "google-cloud-firestore>=2.16.0",
            "requests",
            "numpy>=1.24.0",
            "vertexai>=1.38.0",
        ],
        extra_packages=["customer_support_agent"],
        display_name=DISPLAY_NAME,
        env_vars={
            "FIRESTORE_DATABASE": os.getenv("FIRESTORE_DATABASE", "customer-support-db"),
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
        },
    )

    resource_name = remote_app.resource_name
    agent_engine_id = resource_name.split("/")[-1]

    print("\n✓ Agent deployed!")
    print(f"  Resource: {resource_name}")
    print(f"  ID:       {agent_engine_id}")

    # -------------------------------------------------------------------------
    # Stage 2: Configure Memory Bank
    # -------------------------------------------------------------------------
    print("\n⏳ Stage 2/2: Configuring Memory Bank...")

    client.agent_engines.update(
        name=resource_name,
        config={
            "context_spec": {
                "memory_bank_config": {
                    "generation_config": {
                        "model": f"projects/{numeric_project_id}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash"
                    },
                    "similarity_search_config": {
                        "embedding_model": f"projects/{numeric_project_id}/locations/{LOCATION}/publishers/google/models/gemini-embedding-001"
                    },
                }
            }
        },
    )

    print("\n" + "=" * 70)
    print("✅ DEPLOYMENT SUCCESSFUL!")
    print("=" * 70)
    print(f"\nResource Name:  {resource_name}")
    print(f"Agent Engine ID: {agent_engine_id}")
    print("\n✓ Memory Bank configured:")
    print("  - Generation:  gemini-2.5-flash")
    print("  - Embeddings:  gemini-embedding-001")
    print("  - PreloadMemoryTool loads memories at session start")
    print("  - Callbacks consolidate memories after each turn")
    print("\nUpdate your .env:")
    print(f'  AGENT_ENGINE_RESOURCE_NAME="{resource_name}"')
    print("\nView in Cloud Console:")
    print(f"  https://console.cloud.google.com/vertex-ai/agents/agent-engines?project={PROJECT_ID}")

    return remote_app


# =============================================================================
# TEST DEPLOYED AGENT
# =============================================================================


async def test_remote_agent(resource_name: str):
    """Test the deployed agent on Agent Engine."""
    print("\n" + "=" * 60)
    print("TESTING DEPLOYED AGENT")
    print("=" * 60)

    init_vertex_ai()

    remote_app = agent_engines.get(resource_name)
    print(f"✓ Connected to: {resource_name}")

    session = await remote_app.async_create_session(user_id="remote_test_user")
    print(f"✓ Created session: {session['id']}")

    test_query = "Hi! Can you help me track order ORD-12345 and show me the invoice for it?"
    print(f"\n{'─' * 60}")
    print(f"USER: {test_query}")
    print(f"{'─' * 60}")

    async for event in remote_app.async_stream_query(
        user_id="remote_test_user",
        session_id=session["id"],
        message=test_query,
    ):
        content = event.get("content", {})
        for part in content.get("parts", []):
            if part.get("text") and not part.get("function_call"):
                print(f"\nAGENT: {part['text']}")

    print("\n✓ Remote testing complete!")


# =============================================================================
# CLEANUP
# =============================================================================


def cleanup_deployment(resource_name: str):
    """Delete the deployed agent to avoid charges."""
    print("\n" + "=" * 60)
    print("CLEANING UP DEPLOYMENT")
    print("=" * 60)

    init_vertex_ai()

    remote_app = agent_engines.get(resource_name)
    remote_app.delete(force=True)

    print(f"✓ Deleted: {resource_name}")
    print("✓ Cleanup complete!")


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Multi-Agent Customer Support to Vertex AI Agent Engine with Memory Bank"
    )
    parser.add_argument(
        "--action",
        choices=["test_local", "deploy", "test_remote", "cleanup"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument(
        "--resource_name",
        type=str,
        help="Resource name for test_remote or cleanup actions",
    )

    args = parser.parse_args()

    if args.action == "test_local":
        asyncio.run(test_locally())

    elif args.action == "deploy":
        deploy_to_agent_engine()

    elif args.action == "test_remote":
        if not args.resource_name:
            print("ERROR: --resource_name required for test_remote")
            return
        asyncio.run(test_remote_agent(args.resource_name))

    elif args.action == "cleanup":
        if not args.resource_name:
            print("ERROR: --resource_name required for cleanup")
            return
        cleanup_deployment(args.resource_name)


if __name__ == "__main__":
    main()
