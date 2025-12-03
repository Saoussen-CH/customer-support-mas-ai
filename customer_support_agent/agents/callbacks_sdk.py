"""
Callback using Vertex AI Client SDK approach (from official documentation).

This uses client.agent_engines.memories.generate() which is the recommended
pattern and doesn't require knowing agent_engine_id upfront.
"""

import os
import sys
import time
from datetime import datetime
from vertexai import Client


async def auto_save_to_memory_sdk(callback_context):
    """
    Save session to Memory Bank using Vertex AI Client SDK.

    This follows the official Google Cloud documentation pattern:
    https://docs.cloud.google.com/agent-builder/agent-engine/memory-bank/quickstart-api

    Benefits:
    - Uses official SDK client (no custom service creation)
    - Extracts agent_engine_id from session metadata
    - Follows documented best practices
    """
    callback_start_time = time.time()
    agent_name = "unknown"

    try:
        # Access session from invocation context
        session = callback_context._invocation_context.session

        # Get agent metadata
        agent_name = getattr(callback_context, 'agent_name', 'unknown')
        user_id = getattr(session, 'user_id', 'unknown') if session else 'unknown'
        app_name = getattr(callback_context._invocation_context, 'app_name', 'NOT_SET')

        # Extract session_id - use only the 'id' attribute which is the actual session ID
        session_id = 'unknown'
        if session:
            # The session.id attribute contains the actual session ID (numeric or UUID)
            session_id = getattr(session, 'id', 'unknown')

        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"[CALLBACK SDK] [{timestamp}] Starting callback for agent: {agent_name}")
        print(f"[CALLBACK SDK]   Session: {session_id}")
        print(f"[CALLBACK SDK]   User: {user_id}")
        print(f"[CALLBACK SDK]   App: {app_name}")
        sys.stdout.flush()

        if not session:
            print(f"[MEMORY SDK] ⚠️ Session not available")
            return

        # Skip evaluation sessions - they use special IDs not compatible with Memory Bank
        if isinstance(session_id, str) and session_id.startswith('___eval___session___'):
            print(f"[MEMORY SDK] ⏭️ Skipping Memory Bank save for evaluation session")
            sys.stdout.flush()
            return

        # Extract session resource name - ADK sessions have 'id' which is just the ID part
        # We need to build the full resource path
        session_resource_name = None

        # Get configuration from environment
        # NOTE: AGENT_ENGINE_ID is set via env_vars during two-stage deployment
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        agent_engine_id_from_env = os.getenv("AGENT_ENGINE_ID")  # Set during deployment!

        # IMPORTANT: Memory Bank requires NUMERIC project ID, not string ID
        # Agent Engine runs in project 773461168680 (numeric ID)
        numeric_project_id = "773461168680"  # Hardcoded numeric project ID

        # Fallback for local testing
        agent_engine_resource = os.getenv("AGENT_ENGINE_RESOURCE_NAME")  # Only works locally

        if not project:
            print(f"[MEMORY SDK] ⚠️ GOOGLE_CLOUD_PROJECT not set")
            return

        print(f"[MEMORY SDK] Configuration:")
        print(f"[MEMORY SDK]   Project: {project}")
        print(f"[MEMORY SDK]   Location: {location}")
        print(f"[MEMORY SDK]   Agent Engine Resource: {agent_engine_resource}")
        sys.stdout.flush()

        # Build agent engine name
        agent_engine_name = None

        # Option 1: From AGENT_ENGINE_ID env var (set during two-stage deployment)
        if agent_engine_id_from_env:
            # Use hardcoded numeric project ID (Memory Bank requires numeric ID)
            agent_engine_name = f"projects/{numeric_project_id}/locations/{location}/reasoningEngines/{agent_engine_id_from_env}"
            print(f"[MEMORY SDK] ✅ Using AGENT_ENGINE_ID from env: {agent_engine_name}")

        # Option 2: From session resource name
        if not agent_engine_name and session_resource_name:
            parts = session_resource_name.split('/')
            if 'reasoningEngines' in parts:
                re_index = parts.index('reasoningEngines')
                agent_engine_name = '/'.join(parts[:re_index+2])
                print(f"[MEMORY SDK] ✅ Extracted from session: {agent_engine_name}")

        # Option 3: From AGENT_ENGINE_RESOURCE_NAME env var (local testing)
        if not agent_engine_name and agent_engine_resource:
            agent_engine_name = agent_engine_resource
            print(f"[MEMORY SDK] ✅ Using from env (local): {agent_engine_name}")

        # Option 3: Extract from invocation context
        if not agent_engine_name:
            try:
                inv_ctx = callback_context._invocation_context
                print(f"[MEMORY SDK] 🔍 Checking invocation_context for resource info...")

                # Check all attributes that might have the resource path
                for attr in ['resource_name', 'agent_resource_name', 'parent', 'reasoning_engine_name']:
                    if hasattr(inv_ctx, attr):
                        val = getattr(inv_ctx, attr)
                        print(f"[MEMORY SDK]   inv_ctx.{attr}: {val}")
                        if val and isinstance(val, str) and 'reasoningEngine' in val:
                            agent_engine_name = val
                            break

            except Exception as e:
                print(f"[MEMORY SDK] Could not inspect invocation_context: {e}")

        # Option 4: Get from GCP metadata (reasoning engine instance info)
        if not agent_engine_name:
            try:
                import requests
                # The reasoning engine instance should expose its own resource name via metadata
                metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/resource-name"
                headers = {"Metadata-Flavor": "Google"}
                resp = requests.get(metadata_url, headers=headers, timeout=2)
                if resp.status_code == 200:
                    agent_engine_name = resp.text
                    print(f"[MEMORY SDK] ✅ Got from GCP metadata: {agent_engine_name}")
            except Exception as e:
                print(f"[MEMORY SDK] Metadata query failed: {e}")

        if not agent_engine_name:
            print(f"[MEMORY SDK] ❌ Cannot determine agent engine resource name")
            print(f"[MEMORY SDK] 💡 Set AGENT_ENGINE_RESOURCE_NAME in deployment env vars")
            return

        # Build session resource name using agent engine name and session ID
        # The session.id is just the ID part (numeric or UUID), not the full resource path
        session_resource_name = f"{agent_engine_name}/sessions/{session_id}"
        print(f"[MEMORY SDK] Built session resource name: {session_resource_name}")

        # Initialize Vertex AI Client
        # IMPORTANT: Use NUMERIC project ID for Memory Bank operations
        print(f"[MEMORY SDK] Initializing Vertex AI Client...")
        print(f"[MEMORY SDK]   Using numeric project ID: {numeric_project_id}")
        sys.stdout.flush()

        client = Client(project=numeric_project_id, location=location)

        # Build scope for memory consolidation (up to 5 key-value pairs allowed)
        scope = {"user_id": user_id}
        if app_name and app_name != "NOT_SET":
            scope["app_name"] = app_name

        print(f"[MEMORY SDK] 📝 Triggering memory generation")
        print(f"[MEMORY SDK]   Agent Engine: {agent_engine_name}")
        print(f"[MEMORY SDK]   Session: {session_resource_name}")
        print(f"[MEMORY SDK]   User ID: {user_id}")
        print(f"[MEMORY SDK]   App Name: {app_name}")
        print(f"[MEMORY SDK]   Scope: {scope}")

        events = getattr(session, 'events', [])
        print(f"[MEMORY SDK]   Events count: {len(events)}")
        sys.stdout.flush()

        # Use the SDK approach from Google's documentation
        # This triggers async memory generation/consolidation
        result = client.agent_engines.memories.generate(
            name=agent_engine_name,
            vertex_session_source={"session": session_resource_name},
            scope=scope
        )

        print(f"[MEMORY SDK] ✅ Memory generation triggered!")
        print(f"[MEMORY SDK] 📊 Operation: {result.operation.name if hasattr(result, 'operation') else result}")
        print(f"[MEMORY SDK] ℹ️  Consolidation happens async (may take a few minutes)")
        sys.stdout.flush()

    except Exception as e:
        print(f"[CALLBACK SDK] ❌ Callback error: {e}")
        print(f"[CALLBACK SDK] 🔍 Error type: {type(e).__name__}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
    finally:
        duration = time.time() - callback_start_time
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[CALLBACK SDK] [{timestamp}] ✅ Callback completed for {agent_name} in {duration:.2f}s")
        sys.stdout.flush()
