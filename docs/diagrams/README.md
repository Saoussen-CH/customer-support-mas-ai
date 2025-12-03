# Architecture Diagrams

Mermaid diagrams for the Multi-Agent Customer Support System.

## Diagrams

### System Overview
**File:** `system-overview.mmd`
- Complete system architecture
- Shows all agents, services, and data flows
- Includes Vertex AI Agent Engine, Memory Bank, and Firestore

### Agent Hierarchy
**File:** `agent-hierarchy.mmd`
- Multi-agent structure
- Root coordinator and specialist agents
- Workflow patterns

### Individual Agents

**Root Agent** - `root-agent.mmd`
- Coordinator and router
- Routes to specialist agents

**Product Agent** - `product-agent.mmd`
- 8 tools including RAG search (PreloadMemoryTool + 7 product tools)
- Smart default: `get_product_info` (comprehensive)
- Efficient multi-product: `get_all_saved_products_info`
- Firestore integration with vector search

**Order Agent** - `order-agent.mmd`
- 3 tools (PreloadMemoryTool + 2 order tools)
- Authenticated user context via `get_my_order_history`
- Firestore integration

**Billing Agent** - `billing-agent.mmd`
- 4 tools (PreloadMemoryTool + 3 billing tools)
- Note: Refunds processed via `refund_workflow` only
- Firestore integration

## Color Legend (Google Cloud Style)

- 🟢 Green (#34A853) - Root/Coordinator
- 🟡 Yellow (#FBBC04) - Specialist Agents
- 🔴 Red (#EA4335) - Workflows
- 🔵 Blue (#4285F4) - Tools
- 🟣 Purple (#9334E6) - Memory Bank
- 🟠 Orange (#FF6F00) - Firestore

## Technical Notes

**Callbacks:**
All agents use `auto_save_to_memory_explicit` callback which:
- Creates `VertexAiMemoryBankService` instance
- Automatically saves session data to Memory Bank
- Follows the explicit pattern (not invocation context)
- Note: `track_agent_start` callback is commented out in code

**Agent Hierarchy:**
- Root Agent: Gemini 2.5 Pro (complex reasoning, coordination)
- Specialist Agents: Gemini 2.5 Flash (cost-optimized, simple tool calls)
- Sequential Workflow: Gemini 2.5 Pro (refund validation logic)

## Rendering

View these diagrams using:
- Mermaid Live Editor: https://mermaid.live
- GitHub (native Mermaid support)
- VS Code with Mermaid extension
