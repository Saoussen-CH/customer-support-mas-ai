"""
Deployment Script for Multi-Agent Customer Support System
==========================================================
This script handles:
1. Local testing of the agent
2. Deployment to Vertex AI Agent Engine
3. Testing the deployed agent

Prerequisites:
- Google Cloud Project with Vertex AI API enabled
- Authenticated via `gcloud auth application-default login`
- A GCS bucket for staging

Usage:
    python deployment/deploy.py --action [test_local|deploy|test_remote|cleanup]

    Or from project root:
    python deployment/deploy.py --action [test_local|deploy|test_remote|cleanup]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines
from google.adk.plugins.logging_plugin import LoggingPlugin

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from customer_support_agent.main import root_agent

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION - Loaded from environment variables
# =============================================================================

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", "gs://customer-support-adk-staging")
DISPLAY_NAME = "customer-support-multiagent"

# For Express Mode (no GCP project required):
# API_KEY = "your-express-mode-api-key"


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_vertex_ai():
    """Initialize Vertex AI SDK with project settings."""
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )
    print(f"✓ Initialized Vertex AI")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Staging: {STAGING_BUCKET}")


# For Express Mode initialization:
# def init_vertex_ai_express():
#     """Initialize Vertex AI in Express Mode (no GCP project needed)."""
#     vertexai.init(key=API_KEY)
#     print("✓ Initialized Vertex AI in Express Mode")


# =============================================================================
# LOCAL TESTING
# =============================================================================

async def test_locally():
    """Test the agent locally before deployment."""
    print("\n" + "=" * 60)
    print("LOCAL TESTING")
    print("=" * 60)
    
    # Wrap agent in AdkApp for local testing
    app = agent_engines.AdkApp(
        agent=root_agent,
        app_name="customer_support",  # CRITICAL: Required for Memory Bank scope
        enable_tracing=True,
        plugins=[LoggingPlugin()],  # Enable observability logging
    )
    
    # Create a local session
    session = await app.async_create_session(user_id="test_user_001")
    print(f"\n✓ Created local session: {session.id}")
    
    # Test queries that exercise different specialist agents
    test_queries = [
        "Hi, I need some help today",
        "Can you search for laptops?",
        "Where is my order ORD-12345?",
        "I need the invoice INV-2025-001",
    ]
    
    for query in test_queries:
        print(f"\n{'─' * 40}")
        print(f"USER: {query}")
        print(f"{'─' * 40}")
        
        events = []
        async for event in app.async_stream_query(
            user_id="test_user_001",
            session_id=session.id,
            message=query,
        ):
            events.append(event)
        
        # Extract and display final text response
        for event in events:
            content = event.get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if part.get("text") and not part.get("function_call"):
                    print(f"\nAGENT: {part['text']}")
                elif part.get("function_call"):
                    fn = part["function_call"]
                    print(f"\n  → Calling tool: {fn['name']}({fn.get('args', {})})")
    
    print("\n✓ Local testing complete!")


# =============================================================================
# DEPLOYMENT
# =============================================================================

def deploy_to_agent_engine():
    """Deploy the agent to Vertex AI Agent Engine with Memory Bank."""
    print("\n" + "=" * 60)
    print("DEPLOYING TO VERTEX AI AGENT ENGINE")
    print("=" * 60)

    init_vertex_ai()

    # Initialize Vertex AI client (needed for update call)
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    # Wrap agent in AdkApp with observability
    # Memory Bank will be enabled via update() after deployment
    adk_app = agent_engines.AdkApp(
        agent=root_agent,
        app_name="customer_support",  # CRITICAL: Required for Memory Bank scope
        enable_tracing=True,
        plugins=[LoggingPlugin()],  # Enable comprehensive observability logging
    )

    print("\n⏳ Step 1/3: Deploying agent (this may take several minutes)...")

    # Step 1: Deploy agent using module-level agent_engines.create()
    # Note: We need to know the agent_engine_id upfront for env vars, but we get it after creation
    # So we'll create first, then update with env vars
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
    )

    # Store resource name before updates (it may change after update calls)
    resource_name = remote_app.resource_name
    agent_engine_id = resource_name.split("/")[-1]

    print(f"✓ Agent deployed: {resource_name}")
    print(f"  Agent Engine ID: {agent_engine_id}")

    print("\n⏳ Step 2/3: Enabling Memory Bank...")

    # Step 2: Update Agent Engine with Memory Bank configuration
    # This enables VertexAiMemoryBankService instead of InMemoryMemoryService
    remote_app = client.agent_engines.update(
        name=resource_name,
        config={
            "context_spec": {
                "memory_bank_config": {
                    "generation_config": {
                        "model": f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash-001"
                    },
                    "similarity_search_config": {
                        "embedding_model": f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/text-embedding-004"
                    }
                }
            }
        },
    )

    # Note: env_vars cannot be set via update(), only during create()
    # Since we don't know the agent_engine_id until after creation,
    # we'll use a config file approach or hardcode it in the callback

    print("✓ Memory Bank enabled with:")
    print("  - Generation Model: Gemini 2.5 Flash")
    print("  - Embedding Model: text-embedding-004")
    print("  - Memory Service: VertexAiMemoryBankService (persistent)")

    print("\n" + "=" * 60)
    print("✓ DEPLOYMENT SUCCESSFUL!")
    print("=" * 60)
    print(f"\nResource Name: {resource_name}")
    print(f"Agent Engine ID: {agent_engine_id}")
    print(f"\n✓ Memory Bank configured:")
    print(f"  - Memory generation: gemini-2.5-flash-001")
    print(f"  - Memory search: text-embedding-004")
    print(f"✓ PreloadMemoryTool will load user memories at session start")
    print(f"✓ Callbacks will save memories after each agent turn")

    print(f"\n⚠️  IMPORTANT: Update callback with agent engine ID")
    print(f"Edit customer_support_agent/agents/callbacks_explicit.py:")
    print(f"Set AGENT_ENGINE_ID = \"{agent_engine_id}\" (line ~27)")

    print(f"\nUpdate your .env file with:")
    print(f'AGENT_ENGINE_RESOURCE_NAME="{resource_name}"')
    print(f"\nView in Cloud Console:")
    print(f"https://console.cloud.google.com/vertex-ai/agents/agent-engines?project={PROJECT_ID}")

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
    
    # Connect to deployed agent
    remote_app = agent_engines.get(resource_name)
    print(f"✓ Connected to: {resource_name}")
    
    # Create remote session
    remote_session = await remote_app.async_create_session(user_id="remote_test_user")
    print(f"✓ Created remote session: {remote_session['id']}")
    
    # Test query
    test_query = "Hi! Can you help me track order ORD-12345 and also show me the invoice for it?"
    print(f"\n{'─' * 40}")
    print(f"USER: {test_query}")
    print(f"{'─' * 40}")
    
    async for event in remote_app.async_stream_query(
        user_id="remote_test_user",
        session_id=remote_session["id"],
        message=test_query,
    ):
        content = event.get("content", event.get("parts", {}))
        if isinstance(content, dict):
            parts = content.get("parts", [])
            for part in parts:
                if part.get("text"):
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
    remote_app.delete(force=True)  # force=True also deletes sessions
    
    print(f"✓ Deleted: {resource_name}")
    print("✓ Cleanup complete!")


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Deploy Multi-Agent Customer Support to Vertex AI Agent Engine"
    )
    parser.add_argument(
        "--action",
        choices=["test_local", "deploy", "test_remote", "cleanup"],
        required=True,
        help="Action to perform"
    )
    parser.add_argument(
        "--resource_name",
        type=str,
        help="Resource name for test_remote or cleanup actions"
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