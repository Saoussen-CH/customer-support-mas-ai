"""
Agent callbacks for the customer support system.

This module contains callback functions used by agents.
"""

import time
from datetime import datetime


# Dictionary to track agent execution start times
_agent_execution_tracker = {}


async def track_agent_start(callback_context):
    """
    Track when an agent starts execution.

    This callback runs BEFORE the agent executes and logs the start time.
    Useful for detecting agents that hang or don't return.
    """
    try:
        # Access session from invocation context (correct way)
        session = callback_context._invocation_context.session

        # Get agent metadata
        agent_name = getattr(callback_context, 'agent_name', 'unknown')
        user_id = getattr(session, 'user_id', 'unknown') if session else 'unknown'

        # Extract session_id - try multiple attributes
        session_id = 'unknown'
        if session:
            # Try common session ID attributes
            session_id = (
                getattr(session, 'session_id', None) or
                getattr(session, 'id', None) or
                getattr(session, 'name', None) or
                str(session) if not str(session).startswith('<') else 'unknown'
            )

        start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Track this execution
        execution_key = f"{agent_name}:{session_id}"
        _agent_execution_tracker[execution_key] = start_time

        print(f"[AGENT START] [{timestamp}] Agent '{agent_name}' starting (session: {session_id}, user: {user_id})")

    except Exception as e:
        print(f"[AGENT START] ❌ Error tracking agent start: {e}")
        import traceback
        traceback.print_exc()


async def auto_save_to_memory(callback_context):
    """
    Automatically save session to Memory Bank after each agent turn.

    Uses add_session_to_memory() which triggers async background consolidation.
    Note: Memory consolidation may take several minutes to complete.

    Memory Bank will extract facts like:
    - "Customer prefers products under $500"
    - "User had delivery issues with order ORD-12345"
    - "Customer is interested in gaming laptops"
    """
    callback_start_time = time.time()
    agent_name = "unknown"
    session_id = "unknown"

    try:
        # Access session and memory service from invocation context (correct way)
        memory_service = callback_context._invocation_context.memory_service
        session = callback_context._invocation_context.session

        # Get agent metadata
        agent_name = getattr(callback_context, 'agent_name', 'unknown')
        user_id = getattr(session, 'user_id', 'unknown') if session else 'unknown'

        # Get app_name from invocation context
        app_name = getattr(callback_context._invocation_context, 'app_name', 'NOT_SET')

        # Extract session_id - try multiple attributes
        session_id = 'unknown'
        if session:
            # Try common session ID attributes
            session_id = (
                getattr(session, 'session_id', None) or
                getattr(session, 'id', None) or
                getattr(session, 'name', None) or
                str(session) if not str(session).startswith('<') else 'unknown'
            )

        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"[CALLBACK] [{timestamp}] Starting callback for agent: {agent_name} (session: {session_id}, user: {user_id}, app: {app_name})")

        # Critical warning if app_name is not set
        if app_name == 'NOT_SET' or app_name is None:
            print(f"[MEMORY] ⚠️  CRITICAL: app_name is NOT SET!")
            print(f"[MEMORY] ⚠️  Memory Bank requires app_name in scope")
            print(f"[MEMORY] ⚠️  Fix: Add app_name='customer_support' to AdkApp in deployment")

        # Debug: Print session object structure if session_id is still unknown
        if session_id == 'unknown' and session:
            print(f"[CALLBACK DEBUG] Session object type: {type(session)}")
            print(f"[CALLBACK DEBUG] Session attributes: {[attr for attr in dir(session) if not attr.startswith('_')]}")

        # Calculate total agent execution time
        execution_key = f"{agent_name}:{session_id}"
        if execution_key in _agent_execution_tracker:
            agent_start_time = _agent_execution_tracker[execution_key]
            total_execution_time = time.time() - agent_start_time
            print(f"[AGENT COMPLETE] {agent_name} total execution time: {total_execution_time:.2f}s")

            # Alert on slow agents
            if total_execution_time > 20:
                print(f"[AGENT COMPLETE] ⚠️ SLOW AGENT: {agent_name} took {total_execution_time:.2f}s")

            # Clean up tracker
            del _agent_execution_tracker[execution_key]
        else:
            print(f"[AGENT COMPLETE] ⚠️ No start time tracked for {agent_name}")

        # Check if memory service is available
        if not memory_service:
            print(f"[MEMORY] ⚠️ Memory service not available")
            return

        # Log memory service info and check if it's Memory Bank
        memory_service_name = type(memory_service).__name__
        print(f"[MEMORY] 🔍 Memory service type: {memory_service_name}")

        # Check if using proper Memory Bank service
        if memory_service_name == "VertexAiMemoryBankService":
            print(f"[MEMORY] ✅ Using Vertex AI Memory Bank (persistent cross-session memory)")
        elif memory_service_name == "InMemoryMemoryService":
            print(f"[MEMORY] ⚠️ WARNING: Using InMemoryMemoryService instead of Memory Bank!")
            print(f"[MEMORY] ⚠️ Memories will be lost when the agent restarts")
            print(f"[MEMORY] ℹ️  Deploy with Memory Bank config to enable persistent memory")
        else:
            print(f"[MEMORY] ℹ️  Using custom memory service: {memory_service_name}")

        if not session:
            print(f"[MEMORY] ⚠️ Session not available")
            return

        # Skip evaluation sessions - they use special IDs not compatible with Memory Bank
        if isinstance(session_id, str) and session_id.startswith('___eval___session___'):
            print(f"[MEMORY] ⏭️ Skipping Memory Bank save for evaluation session")
            return


        # Save session to Memory Bank
        try:
            events = getattr(session, 'events', [])

            print(f"[MEMORY] 📝 Attempting to save session to Memory Bank")
            print(f"[MEMORY]    App Name: {app_name}")
            print(f"[MEMORY]    User ID: {user_id}")
            print(f"[MEMORY]    Session ID: {session_id}")
            print(f"[MEMORY]    Agent: {agent_name}")
            print(f"[MEMORY]    Events count: {len(events)}")
            print(f"[MEMORY]    Scope: {{app_name: '{app_name}', user_id: '{user_id}'}}")

            # Check if memory_service has the method we expect
            if hasattr(memory_service, 'add_session_to_memory'):
                print(f"[MEMORY] 🔧 Calling add_session_to_memory...")
                result = await memory_service.add_session_to_memory(session)
                print(f"[MEMORY] ✅ Session sent to Memory Bank")
                print(f"[MEMORY] 📊 Result: {result}")
                print(f"[MEMORY] ℹ️  Consolidation happens async (may take a few minutes)")
            else:
                print(f"[MEMORY] ⚠️ Memory service does not have 'add_session_to_memory' method")
                print(f"[MEMORY] 📋 Available methods: {dir(memory_service)}")

                # Try alternative method if available
                if hasattr(memory_service, 'add_memory'):
                    print(f"[MEMORY] 🔧 Trying add_memory method instead...")
                    # Extract relevant info from events
                    for event in events[-5:]:  # Last 5 events
                        await memory_service.add_memory(
                            user_id=user_id,
                            content=str(event),
                            session_id=session_id
                        )
                    print(f"[MEMORY] ✅ Events saved using add_memory")
        except Exception as save_error:
            print(f"[MEMORY] ❌ Save failed: {save_error}")
            print(f"[MEMORY] 🔍 Error type: {type(save_error).__name__}")
            import traceback
            print(f"[MEMORY] 📋 Traceback:")
            traceback.print_exc()
    except Exception as e:
        print(f"[MEMORY] ❌ Callback error: {e}")
    finally:
        # Log callback performance
        duration = time.time() - callback_start_time
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[CALLBACK] [{timestamp}] ✅ Callback completed for {agent_name} in {duration:.2f}s")

        # Alert on slow callbacks
        if duration > 5:
            print(f"[CALLBACK] ⚠️ SLOW CALLBACK: {agent_name} callback took {duration:.2f}s")


async def check_hanging_agents():
    """
    Utility function to check for agents that started but haven't completed.

    Call this periodically or on-demand to detect hung agents.
    """
    current_time = time.time()
    hanging_agents = []

    for execution_key, start_time in _agent_execution_tracker.items():
        elapsed = current_time - start_time
        if elapsed > 30:  # Consider an agent hanging if it's been running for more than 30 seconds
            agent_name = execution_key.split(':')[0]
            hanging_agents.append({
                'agent': agent_name,
                'execution_key': execution_key,
                'elapsed_seconds': elapsed
            })
            print(f"[MONITORING] ⚠️ HANGING AGENT DETECTED: {agent_name} has been running for {elapsed:.2f}s")

    return hanging_agents
