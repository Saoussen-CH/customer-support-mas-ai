"""
Alternative callback implementation using explicit VertexAiMemoryBankService.

This follows the notebook pattern where we create VertexAiMemoryBankService
explicitly instead of relying on the auto-provided service.
"""

import time
import os
import sys
from datetime import datetime
from google.adk.memory import VertexAiMemoryBankService


# Cached memory service (created once, reused across callbacks)
_memory_bank_service = None


def get_memory_bank_service(callback_context=None):
    """Get or create the VertexAiMemoryBankService instance."""
    global _memory_bank_service

    if _memory_bank_service is None:
        # Get configuration from environment
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        agent_engine_id = None

        # Try multiple sources for agent_engine_id:

        # 0. Try to get from callback_context (BEST option - no env vars or metadata needed!)
        if callback_context:
            try:
                inv_ctx = callback_context._invocation_context

                # Check if memory_service has the agent_engine_id
                # VertexAiMemoryBankService is initialized with agent_engine_id
                if hasattr(inv_ctx, 'memory_service'):
                    mem_svc = inv_ctx.memory_service
                    print(f"[MEMORY] Checking memory_service for agent_engine_id...")
                    print(f"[MEMORY] Memory service type: {type(mem_svc).__name__}")

                    # Try to get agent_engine_id from memory service
                    for attr_name in ['agent_engine_id', '_agent_engine_id', 'reasoning_engine_id', '_reasoning_engine_id']:
                        if hasattr(mem_svc, attr_name):
                            value = getattr(mem_svc, attr_name)
                            if value:
                                agent_engine_id = str(value)
                                print(f"[MEMORY] ✅ Found agent_engine_id in memory_service.{attr_name}: {agent_engine_id}")
                                sys.stdout.flush()
                                break

                # If not found in memory service, inspect other attributes
                if not agent_engine_id:
                    print(f"[MEMORY] Not found in memory_service, checking other attributes...")
                    for attr_name in ['resource_name', 'agent_engine_id', 'reasoning_engine_id']:
                        if hasattr(inv_ctx, attr_name):
                            value = getattr(inv_ctx, attr_name)
                            if value and isinstance(value, str):
                                if '/' in value:
                                    agent_engine_id = value.split("/")[-1]
                                else:
                                    agent_engine_id = value
                                print(f"[MEMORY] ✅ Found agent_engine_id from invocation_context.{attr_name}: {agent_engine_id}")
                                sys.stdout.flush()
                                break
            except Exception as e:
                print(f"[MEMORY] Could not inspect invocation_context: {e}")
                import traceback
                traceback.print_exc()
                sys.stdout.flush()

        # 1. From environment variable (if set during deployment)
        if not agent_engine_id:
            env_agent_id = os.getenv("AGENT_ENGINE_ID")
            if env_agent_id:
                agent_engine_id = env_agent_id
                print(f"[MEMORY] Using AGENT_ENGINE_ID from environment: {agent_engine_id}")

        # 2. From AGENT_ENGINE_RESOURCE_NAME env var
        if not agent_engine_id:
            agent_engine_resource = os.getenv("AGENT_ENGINE_RESOURCE_NAME")
            if agent_engine_resource:
                agent_engine_id = agent_engine_resource.split("/")[-1]
                print(f"[MEMORY] Extracted from AGENT_ENGINE_RESOURCE_NAME: {agent_engine_id}")

        # 3. Try to get from GCP metadata service (when running on Agent Engine)
        if not agent_engine_id:
            print(f"[MEMORY] Attempting to get agent_engine_id from GCP metadata...")
            sys.stdout.flush()

            # Try multiple metadata endpoints
            metadata_attempts = [
                "http://metadata.google.internal/computeMetadata/v1/instance/name",
                "http://metadata.google.internal/computeMetadata/v1/instance/attributes/container-name",
                "http://metadata.google.internal/computeMetadata/v1/instance/hostname",
            ]

            for metadata_url in metadata_attempts:
                try:
                    import requests
                    headers = {"Metadata-Flavor": "Google"}
                    response = requests.get(metadata_url, headers=headers, timeout=2)

                    if response.status_code == 200:
                        value = response.text
                        print(f"[MEMORY] Metadata {metadata_url.split('/')[-1]}: {value}")
                        sys.stdout.flush()

                        # Try to extract reasoning engine ID from various formats
                        # Format 1: "reasoning-engine-<ID>-..."
                        if "reasoning-engine-" in value or "reasoningengine" in value.lower():
                            # Extract numeric ID
                            import re
                            match = re.search(r'(\d{18,20})', value)
                            if match:
                                agent_engine_id = match.group(1)
                                print(f"[MEMORY] ✅ Extracted agent_engine_id from GCP metadata: {agent_engine_id}")
                                sys.stdout.flush()
                                break
                except Exception as e:
                    print(f"[MEMORY] Metadata attempt failed ({metadata_url.split('/')[-1]}): {e}")
                    sys.stdout.flush()

            if not agent_engine_id:
                print(f"[MEMORY] ⚠️  Could not extract agent_engine_id from metadata")

        # 4. Last resort: hardcoded value (update after first deployment)
        if not agent_engine_id:
            agent_engine_id = "6799850497143472128"  # Updated from latest deployment
            print(f"[MEMORY] Using hardcoded AGENT_ENGINE_ID: {agent_engine_id}")

        print(f"[MEMORY] Checking configuration...")
        print(f"[MEMORY]   GOOGLE_CLOUD_PROJECT: {project}")
        print(f"[MEMORY]   GOOGLE_CLOUD_LOCATION: {location}")
        print(f"[MEMORY]   AGENT_ENGINE_ID: {agent_engine_id}")
        sys.stdout.flush()

        if not agent_engine_id:
            error_msg = "AGENT_ENGINE_ID not available"
            print(f"[MEMORY] ❌ ERROR: {error_msg}")
            sys.stdout.flush()
            raise ValueError(error_msg)

        print(f"[MEMORY] Initializing VertexAiMemoryBankService")
        print(f"[MEMORY]   Project: {project}")
        print(f"[MEMORY]   Location: {location}")
        print(f"[MEMORY]   Agent Engine ID: {agent_engine_id}")
        sys.stdout.flush()

        # Create explicit VertexAiMemoryBankService (notebook pattern)
        _memory_bank_service = VertexAiMemoryBankService(
            agent_engine_id=agent_engine_id,
            project=project,
            location=location,
        )

        print(f"[MEMORY] ✅ VertexAiMemoryBankService initialized")
        sys.stdout.flush()

    return _memory_bank_service


async def auto_save_to_memory_explicit(callback_context):
    """
    Alternative callback using explicit VertexAiMemoryBankService.

    This follows the pattern shown in the Memory Bank notebook:
    - Create explicit VertexAiMemoryBankService
    - Call add_session_to_memory() directly on it

    Benefits:
    - More explicit and easier to debug
    - Follows documented notebook pattern
    - Not dependent on invocation context internals
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

        # Extract session_id
        session_id = 'unknown'
        if session:
            session_id = (
                getattr(session, 'session_id', None) or
                getattr(session, 'id', None) or
                getattr(session, 'name', None) or
                str(session) if not str(session).startswith('<') else 'unknown'
            )

        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"[CALLBACK EXPLICIT] [{timestamp}] Starting callback for agent: {agent_name}")
        sys.stdout.flush()  # Force flush to see logs immediately

        print(f"[CALLBACK EXPLICIT]   Session: {session_id}")
        print(f"[CALLBACK EXPLICIT]   User: {user_id}")
        print(f"[CALLBACK EXPLICIT]   App: {app_name}")
        sys.stdout.flush()

        if app_name == 'NOT_SET' or app_name is None:
            print(f"[MEMORY] ⚠️  WARNING: app_name is NOT SET!")

        if not session:
            print(f"[MEMORY] ⚠️ Session not available")
            return

        # Skip evaluation sessions - they use special IDs not compatible with Memory Bank
        if isinstance(session_id, str) and session_id.startswith('___eval___session___'):
            print(f"[MEMORY] ⏭️ Skipping Memory Bank save for evaluation session")
            sys.stdout.flush()
            return

        # Get explicit VertexAiMemoryBankService (notebook pattern)
        try:
            memory_bank_service = get_memory_bank_service(callback_context)
        except Exception as e:
            print(f"[MEMORY] ❌ Failed to get VertexAiMemoryBankService: {e}")
            print(f"[MEMORY] 🔍 Error type: {type(e).__name__}")
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            sys.stderr.flush()
            return

        # Save session to Memory Bank (exactly like notebook)
        try:
            events = getattr(session, 'events', [])

            print(f"[MEMORY] 📝 Calling add_session_to_memory (explicit)")
            print(f"[MEMORY]   Method: memory_bank_service.add_session_to_memory(session)")
            print(f"[MEMORY]   App Name: {app_name}")
            print(f"[MEMORY]   User ID: {user_id}")
            print(f"[MEMORY]   Session ID: {session_id}")
            print(f"[MEMORY]   Events count: {len(events)}")
            print(f"[MEMORY]   Scope: {{app_name: '{app_name}', user_id: '{user_id}'}}")
            sys.stdout.flush()

            # Call add_session_to_memory exactly like the notebook
            result = await memory_bank_service.add_session_to_memory(session)

            print(f"[MEMORY] ✅ Session sent to Memory Bank (explicit)")
            print(f"[MEMORY] 📊 Result: {result}")
            print(f"[MEMORY] ℹ️  Consolidation happens async (may take a few minutes)")
            sys.stdout.flush()

        except Exception as save_error:
            print(f"[MEMORY] ❌ Save failed: {save_error}")
            print(f"[MEMORY] 🔍 Error type: {type(save_error).__name__}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"[CALLBACK EXPLICIT] ❌ Callback error: {e}")
        print(f"[CALLBACK EXPLICIT] 🔍 Error type: {type(e).__name__}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
    finally:
        duration = time.time() - callback_start_time
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[CALLBACK EXPLICIT] [{timestamp}] ✅ Callback completed for {agent_name} in {duration:.2f}s")
        sys.stdout.flush()
