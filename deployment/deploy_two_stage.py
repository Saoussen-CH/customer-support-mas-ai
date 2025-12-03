"""
Two-Stage Deployment for Agent Engine with Memory Bank
=======================================================
This approach solves the chicken-and-egg problem where callbacks need the
agent_engine_id but we don't know it until after deployment.

Two-Stage Process:
1. Create Agent Engine resource with Memory Bank config (get ID)
2. Deploy agent code to it with env_vars={'AGENT_ENGINE_ID': id}

This way, callbacks can read the ID from os.getenv("AGENT_ENGINE_ID")!
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines, Client
from google.adk.plugins.logging_plugin import LoggingPlugin

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from customer_support_agent.main import root_agent

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", "gs://customer-support-adk-staging")
DISPLAY_NAME = "customer-support-multiagent"


def init_vertex_ai():
    """Initialize Vertex AI SDK."""
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )
    print(f"✓ Initialized Vertex AI")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Staging: {STAGING_BUCKET}")


def deploy_two_stage():
    """Deploy using two-stage approach to solve chicken-and-egg problem."""
    print("\n" + "=" * 70)
    print("TWO-STAGE DEPLOYMENT: Agent Engine with Memory Bank")
    print("=" * 70)

    init_vertex_ai()

    # Initialize client
    # IMPORTANT: Agent Engine runs under numeric project ID
    NUMERIC_PROJECT_ID = "773461168680"
    client = Client(project=NUMERIC_PROJECT_ID, location=LOCATION)

    # =========================================================================
    # STAGE 1: Create Agent Engine Resource (No Code Yet)
    # =========================================================================
    print("\n⏳ STAGE 1: Creating Agent Engine resource...")
    print("   (This creates the resource and gets the ID, no code deployed yet)")

    # CRITICAL: Use NUMERIC project ID for Memory Bank model paths
    agent_engine_resource = client.agent_engines.create(
        config={
            "display_name": DISPLAY_NAME,
            "context_spec": {
                "memory_bank_config": {
                    "generation_config": {
                        "model": f"projects/{NUMERIC_PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash"
                    },

                    "similarity_search_config": {
                        "embedding_model": f"projects/{NUMERIC_PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-embedding-001"
                    }
                }
            }
        }
    )

    # Extract resource name and ID
    resource_name = agent_engine_resource.api_resource.name
    agent_engine_id = resource_name.split("/")[-1]

    print(f"\n✓ Agent Engine resource created!")
    print(f"  Resource: {resource_name}")
    print(f"  ID: {agent_engine_id}")
    print(f"\n✓ Memory Bank configured:")
    print(f"  - Generation Model: Gemini 2.5 Flash")
    print(f"  - Embedding Model: gemini-embedding-001")

    # =========================================================================
    # STAGE 2: Deploy Agent Code with Environment Variables
    # =========================================================================
    print(f"\n⏳ STAGE 2: Deploying agent code to existing resource...")
    print(f"   (Setting AGENT_ENGINE_ID={agent_engine_id} as env var)")

    # Wrap agent in AdkApp
    adk_app = agent_engines.AdkApp(
        agent=root_agent,
        app_name="customer_support",  # Required for Memory Bank scope
        enable_tracing=True,
        plugins=[LoggingPlugin()],
    )

    # Deploy agent code to the existing resource WITH env vars
    remote_app = agent_engines.update(
        resource_name=resource_name,
        agent_engine=adk_app,
        requirements=[
            "google-cloud-aiplatform[adk,agent_engines]>=1.112",
            "google-cloud-firestore>=2.16.0",
            "requests",
            "numpy>=1.24.0",
            "vertexai>=1.38.0",
        ],
        extra_packages=["customer_support_agent"],
        env_vars={
            "AGENT_ENGINE_ID": agent_engine_id,  # 🎯 KEY: Callbacks can read this!
            # Note: GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are auto-set by Agent Engine
        },
    )

    print(f"\n✓ Agent code deployed!")
    print(f"  Environment variables set:")
    print(f"    - AGENT_ENGINE_ID={agent_engine_id}")
    print(f"  (GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are auto-provided by Agent Engine)")

    # =========================================================================
    # SUCCESS
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ TWO-STAGE DEPLOYMENT SUCCESSFUL!")
    print("=" * 70)

    print(f"\nResource Name: {resource_name}")
    print(f"Agent Engine ID: {agent_engine_id}")

    print(f"\n✓ Callbacks can now use:")
    print(f"  agent_engine_id = os.getenv('AGENT_ENGINE_ID')")
    print(f"  → Will return: '{agent_engine_id}'")

    print(f"\n✓ Memory Bank ready:")
    print(f"  - Memories will be generated by Gemini 2.5 Flash")
    print(f"  - Memories will be searchable via gemini-embedding-001")
    print(f"  - PreloadMemoryTool will load memories at session start")
    print(f"  - Callbacks will consolidate memories after each turn")

    print(f"\nUpdate your .env file with:")
    print(f'AGENT_ENGINE_RESOURCE_NAME="{resource_name}"')

    print(f"\nView in Cloud Console:")
    print(f"https://console.cloud.google.com/vertex-ai/agents/agent-engines?project={PROJECT_ID}")

    return remote_app


# =============================================================================
# TESTING
# =============================================================================

async def test_deployed_agent(resource_name: str):
    """Test the deployed agent."""
    print("\n" + "=" * 70)
    print("TESTING DEPLOYED AGENT")
    print("=" * 70)

    init_vertex_ai()

    # Connect to deployed agent
    remote_app = agent_engines.get(resource_name)
    print(f"✓ Connected to: {resource_name}")

    # Create session
    session = await remote_app.async_create_session(user_id="test_two_stage")
    print(f"✓ Created session: {session['id']}")

    # Test query
    test_query = "Hi! I'm looking for a budget laptop under $600. Can you help?"
    print(f"\n{'─' * 70}")
    print(f"USER: {test_query}")
    print(f"{'─' * 70}\n")

    async for event in remote_app.async_stream_query(
        user_id="test_two_stage",
        session_id=session["id"],
        message=test_query,
    ):
        content = event.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if part.get("text") and not part.get("function_call"):
                print(f"AGENT: {part['text']}\n")

    print("=" * 70)
    print("✓ Test complete!")
    print("\nCheck logs to verify callbacks can read AGENT_ENGINE_ID:")
    print(f"gcloud logging read \"resource.labels.reasoning_engine_id={resource_name.split('/')[-1]} AND textPayload:'AGENT_ENGINE_ID'\" --limit=20 --project={PROJECT_ID}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Two-Stage Deployment for Agent Engine"
    )
    parser.add_argument(
        "--action",
        choices=["deploy", "test"],
        required=True,
        help="Action to perform"
    )
    parser.add_argument(
        "--resource_name",
        type=str,
        help="Resource name for test action"
    )

    args = parser.parse_args()

    if args.action == "deploy":
        deploy_two_stage()

    elif args.action == "test":
        if not args.resource_name:
            print("ERROR: --resource_name required for test")
            return
        asyncio.run(test_deployed_agent(args.resource_name))


if __name__ == "__main__":
    main()
