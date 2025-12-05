# Multi-Agent Customer Support System

  A production-ready, full-stack AI customer support system powered by Google's Agent Development Kit (ADK). Features hierarchical multi-agent orchestration, RAG-powered semantic search with vector embeddings,   cross-session Memory Bank for personalized  experiences, and Sequential workflow patterns for validated refund processing. Built with React/TypeScript frontend, FastAPI backend, Vertex AI middleware and Firestore. Includes comprehensive LLM-based evaluation suite with 10+ test datasets, cloud-native deployment automation.

## Architecture

![System Architecture](./images/architecture.drawio.png)

The system is built on Google Cloud Platform with:
- **Frontend:** React/TypeScript on Cloud Run
- **Backend:** FastAPI + Cloud Proxy on Cloud Run
- **AI Layer:** Vertex AI Agent Engine with multi-agent orchestration
- **Data Layer:** Firestore with vector search, Memory Bank for cross-session memory

For detailed architecture documentation, see [ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Implementation Based on Kaggle 5-Day AI Agents Course

This project implements and extends concepts from Kaggle 5-Day AI Agents Intensive materials:

| Course Topic | Implementation | Production Enhancement |
|-------------|----------------|----------------------|
| **Multi-Agent Orchestration** | ✅ Root + 3 Specialists + Workflow agents | Cost-optimized with Gemini 2.5 Pro + Flash |
| **Sequential Workflows** | ✅ 3-step refund validation pipeline | Validation gates prevent invalid operations |
| **Session Management** | ✅ Vertex AI Agent Engine sessions | Backend proxy with JWT auth + multi-user support |
| **Memory Bank** | ✅ Vertex AI Memory Bank with callbacks | Cross-session preference recall |
| **Observability** | ✅ LoggingPlugin + Cloud Logging | Production-ready monitoring |
| **Evaluation & Testing** | ✅ Vertex AI Gen AI Evaluation + AgentEvaluator | 10+ evalset files with LLM-as-judge metrics |
| **Deployment** | ✅ Vertex AI Agent Engine + Cloud Run | Full-stack with automation scripts |

## Key Features

- 🤖 **Multi-Agent System** - Root agent coordinates specialized agents (Product, Order, Billing)
- 🧠 **Memory Bank** - Remembers user preferences across sessions
- 🔍 **RAG Semantic Search** - Vector embeddings for intelligent product search
- ⚡ **Sequential Workflow** - SequentialAgent for validated refund processing with step-by-step validation gates
- 👥 **User Management** - Email/password auth or guest access
- 💬 **Multi-Session Conversations** - Multiple chat threads per user
- 🔄 **Retry Logic** - Automatic exponential backoff for transient errors
- 🧪 **Comprehensive Testing** - Pytest automation with ADK AgentEvaluator
- 🎤 **Voice Features** - Speech-to-text input and text-to-speech output
- ☁️ **Cloud Deployment** - Deploy to Cloud Run + Vertex AI Agent Engine

## Quick Start

> 📖 **New to the project?** See **[GETTING_STARTED.md](./GETTING_STARTED.md)** for a complete step-by-step setup checklist.

### Prerequisites

Before deploying, you need:
- **Python 3.11** (managed with pyenv)
- **GCP project** with billing enabled
- **Required APIs** enabled (Vertex AI, Firestore, Cloud Run, etc.)
- **IAM permissions** configured
- **GCS bucket** for staging

**Install Python 3.11 with pyenv:**
```bash
# Install pyenv (macOS)
brew install pyenv

# Install pyenv (Linux)
curl https://pyenv.run | bash

# Install Python 3.11.13
pyenv install 3.11.13

# The project uses .python-version file
cd customer-support-mas
python --version  # Should show 3.11.13
```

**Run automated GCP setup:**
```bash
# 1. Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# 2. Set your project
gcloud config set project YOUR_PROJECT_ID

# 3. Run setup scripts
./scripts/setup_gcp.sh        # Enable APIs, create service account, grant IAM roles
./scripts/setup_firestore.sh  # Create Firestore database, seed data
```

See **[PREREQUISITES.md](./docs/PREREQUISITES.md)** for detailed setup instructions.

### Deploy the System

```bash
# 1. Configure environment variables
cp .env.example .env
nano .env  # Edit with your GCP project details

# 2. Deploy agent to Vertex AI Agent Engine
# Option A: Standard deployment (no Memory Bank)
python deployment/deploy.py

# Option B: Two-stage deployment (with Memory Bank)
python deployment/deploy_two_stage.py

# 3. Deploy frontend + backend to Cloud Run
./deployment/deploy-cloudrun.sh

# 4. Access the web application
open https://customer-support-ai-xxxxx-uc.a.run.app
```

## Project Structure

```
customer-support-mas/
├── customer_support_agent/       # Core agent system
│   ├── main.py                   # Entry point
│   ├── config.py                 # Agent configurations
│   ├── agents/                   # Agent definitions
│   │   ├── root_agent.py         # Root coordinator (Gemini 2.5 Pro)
│   │   ├── product_agent.py      # Product specialist (Gemini 2.5 Flash)
│   │   ├── order_agent.py        # Order specialist
│   │   ├── billing_agent.py      # Billing specialist
│   │   ├── workflow_agents.py    # Parallel/Sequential/Loop agents
│   │   ├── callbacks.py          # Memory Bank callbacks (traditional - doesn't work)
│   │   └── callbacks_sdk.py      # Memory Bank callbacks (SDK-based - working)
│   ├── tools/                    # Tool implementations
│   │   ├── product_tools.py      # 8 product tools (including get_product_info smart wrapper)
│   │   ├── order_tools.py        # 2 order tools
│   │   ├── billing_tools.py      # 6 billing tools
│   │   └── workflow_tools.py     # Loop control tools
│   ├── database/                 # Database layer
│   │   ├── client.py             # Firestore client
│   │   └── seed.py               # Database seeding
│   └── services/                 # Business logic
│       └── rag_search.py         # RAG semantic search
├── backend/                      # FastAPI backend
│   └── app/
│       ├── main.py               # API server
│       ├── auth.py               # User authentication
│       ├── agent_client.py       # Agent Engine client
│       └── database.py           # Firestore operations
├── frontend/                     # React frontend
│   └── src/
│       ├── App.tsx               # Main component
│       ├── components/           # UI components
│       └── services/             # API clients
├── deployment/                   # Deployment scripts
│   ├── deploy.py                 # Deploy to Agent Engine (standard)
│   ├── deploy_two_stage.py       # Deploy with Memory Bank (two-stage)
│   └── deploy-cloudrun.sh        # Deploy to Cloud Run
├── scripts/                      # Utility scripts
│   └── add_embeddings.py         # Add vector embeddings for RAG
├── tests/                        # Test suite
│   ├── test_customer_support.py  # Main test suite
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
├── online_evaluation/            # Online evaluation scripts
│   ├── run_agent_evaluation.py   # Batch evaluation
│   └── run_single_eval.py        # Single test case
└── docs/                         # Documentation
    ├── ARCHITECTURE.md           # System architecture
    └── DEPLOYMENT.md             # Deployment guide
```

## Technology Stack

**Frontend:** React 18 - TypeScript - Vite - Axios

**Backend:** FastAPI - Python 3.11 - Pydantic - Token-based auth

**AI/ML:** Google ADK - Gemini 2.5 Pro/Flash - Vertex AI Agent Engine - Vertex AI Memory Bank - Vertex AI Agent Engine Sessions - text-embedding-004 - gemini-embedding-001

**Data:** Firestore (NoSQL + vector search)

**Infrastructure:** Cloud Run - Artifact Registry - Docker - Cloud Logging

**Testing:** pytest - AgentEvaluator - Vertex AI Gen AI Evaluation

## Agent Architecture

### 1. Root Agent (Coordinator)
- **Model**: Gemini 2.5 Pro
- **Role**: Routes requests to specialist agents
- **Tools**: 4 AgentTools (product_agent, order_agent, billing_agent, refund_workflow)

### 2. Product Agent
- **Model**: Gemini 2.5 Flash
- **Tools**:
  - `search_products` - RAG semantic search
  - **`get_product_info`** - **Smart unified tool (default)** - Fetches details + inventory + reviews comprehensively
  - `get_last_mentioned_product` - Context-aware retrieval
  - `get_all_saved_products_info` - Efficient multi-product fetch from last search
  - `get_product_details` - Fetch only details (for "ONLY details" requests)
  - `check_inventory` - Stock levels only (for "ONLY inventory" requests)
  - `get_product_reviews` - Customer reviews only (for "ONLY reviews" requests)

**Design Philosophy**: The product agent defaults to providing comprehensive information (`get_product_info`) for better UX. Individual tools are only used when users explicitly request specific data with "ONLY" or "JUST" keywords.

### 3. Order Agent
- **Model**: Gemini 2.5 Flash
- **Tools**: `track_order`, `get_my_order_history`

### 4. Billing Agent
- **Model**: Gemini 2.5 Flash
- **Tools**: `get_invoice`, `get_invoice_by_order_id`, `check_payment_status`
- **Note**: Refunds are processed through the dedicated `refund_workflow` for proper validation

## Workflow Patterns

### Smart Tool Wrapper
```python
# The product agent uses get_product_info() by default
# Fetches details + inventory + reviews comprehensively
# Deterministic behavior - no keyword-based routing
```

### SequentialAgent - Stepwise Validation
```python
# Use case: "I want a refund for order ORD-12345"
# Steps: Validate Order → Check Eligibility → Process Refund
# Each step must pass before proceeding
# Only way to process refunds - ensures proper validation
```

### Efficient Multi-Product Fetch
```python
# Use case: "Show me details on all of them" (after search)
# Uses get_all_saved_products_info - single call for all products
# Replaces iterative LoopAgent approach to avoid timeouts
```

## Testing

```bash
# Run full test suite
pytest tests/ -v

# Run specific test category
pytest tests/test_customer_support.py::TestUnitEvaluation -v

# Run integration tests
pytest tests/test_customer_support.py::TestIntegrationEvaluation -v

# Verify refactoring
python test_refactoring.py
```

## RAG Search

RAG (Retrieval Augmented Generation) enables semantic search:

```python
# User: "gaming computer"
# 1. Embed query with text-embedding-004 (768-dim vector)
# 2. Search Firestore vector index
# 3. Return top 5 semantic matches (finds "ROG Gaming Laptop")
# 4. Apply price/category filters
```

**Setup RAG:**
```bash
# 1. Create vector index (via REST API or script)
python scripts/create_vector_index.py

# 2. Wait for index status = READY (5-10 min)
gcloud firestore indexes composite list --database=customer-support-db

# 3. Add embeddings to products
python scripts/add_embeddings.py \
  --project YOUR_PROJECT \
  --database customer-support-db \
  --location us-central1

# 4. Redeploy agent
python deployment/deploy.py --action deploy
```

**Fallback**: If RAG unavailable, uses keyword search automatically.

## Memory Bank

Remembers user preferences across sessions using Vertex AI Memory Bank with automatic extraction and recall.

### Memory Extraction Examples

```python
# Automatically extracted from conversations:
# - "Customer prefers products under $500"
# - "User had delivery issues with order ORD-12345"
# - "Customer is interested in gaming laptops"
```

### Implementation Approach

**Current Implementation:** SDK-based callbacks (`callbacks_sdk.py`)

The project uses the Vertex AI Client SDK approach for Memory Bank integration:

```python
# callbacks_sdk.py - Working approach
client = Client(project=PROJECT_ID, location=LOCATION)
client.agent_engines.memories.generate(
    agent_engine_id=agent_engine_id,
    session_id=session_id
)
```

**Why not the traditional approach?**

The traditional approach (`callbacks.py`) assumes Agent Engine automatically provides Memory Bank service via invocation context:

```python
# callbacks.py - Doesn't work when deployed
memory_service = callback_context._invocation_context.memory_service
memory_service.save()
```

However, this **doesn't work** when deployed to Vertex AI Agent Engine because the Memory Bank service is not automatically injected into the invocation context. The SDK-based approach explicitly calls the Memory Bank API using the Agent Engine SDK.

### Deployment Requirements

**Two-Stage Deployment:** Memory Bank requires using `deploy_two_stage.py` instead of the standard `deploy.py`:

1. **Stage 1:** Create Agent Engine resource with Memory Bank config → Get agent_engine_id
2. **Stage 2:** Deploy agent code with `AGENT_ENGINE_ID` environment variable

This solves the chicken-and-egg problem where callbacks need the agent_engine_id, but it's only available after initial deployment.

**Standard deployment vs Two-stage:**
- `deploy.py` - Single-stage deployment (no Memory Bank)
- `deploy_two_stage.py` - Two-stage deployment (with Memory Bank)

### Memory Recall

Agents use `PreloadMemoryTool` to automatically load relevant memories at conversation start:

```python
tools=[
    preload_memory_tool.PreloadMemoryTool(),  # Loads memories from previous sessions
    # ... other tools
]
```

## Configuration

### Using .env Files (Recommended)

```bash
# 1. Copy example files
cp .env.example .env
cp backend/.env.example backend/.env

# 2. Edit .env with your values
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
AGENT_ENGINE_RESOURCE_NAME=projects/.../reasoningEngines/...
```

The system automatically loads .env files:
- **Root `.env`** - Used by deployment scripts and agent code
- **`backend/.env`** - Used by FastAPI backend (pydantic-settings)
- **`frontend/.env`** - Used by React frontend (Vite)

### Environment Variables

**Required:**
- `GOOGLE_CLOUD_PROJECT` - Your GCP project ID
- `GOOGLE_CLOUD_STORAGE_BUCKET` - GCS bucket for staging (with `gs://` prefix)
- `AGENT_ENGINE_RESOURCE_NAME` - Deployed agent resource name

**Optional:**
- `GOOGLE_CLOUD_LOCATION` - GCP region (default: `us-central1`)
- `FIRESTORE_DATABASE` - Firestore database name (default: `(default)`)
- `GOOGLE_GENAI_USE_VERTEXAI` - Use Vertex AI (default: `1`)
- `FRONTEND_URL` - Frontend URL for CORS (default: `http://localhost:3000`)
- `PORT` - Backend port (default: `8000`)

## Database Schema

Firestore collections:

- **users/** - User accounts
- **sessions/** - Conversation sessions
- **messages/** - Chat messages
- **products/** - Products with embeddings (768-dim vectors)
- **orders/** - Customer orders
- **invoices/** - Billing invoices

## Example Interactions

**Product Search:**
```
User: Show me laptops under $600
Agent: [Uses search_products with RAG]
      Returns: UltraBook Pro ($899), ThinkStation ($799), OfficeMax ($599)
```

**Comprehensive Lookup:**
```
User: Tell me everything about PROD-001
Agent: [Uses get_product_info - smart unified tool]
      Returns: Details + Inventory (50 units) + Reviews (4.5/5)
```

**Refund Request (SequentialAgent):**
```
User: I want a refund for order ORD-12345
Agent: [Uses refund_workflow]
      Step 1: Validate order ✓
      Step 2: Check eligibility ✓
      Step 3: Process refund ✓
      Returns: Refund processed successfully
```

## Deployment

### Deploy to Agent Engine

**Option A: Standard deployment (no Memory Bank)**
```bash
python deployment/deploy.py
# Returns: projects/.../reasoningEngines/...
```

**Option B: Two-stage deployment (with Memory Bank)**
```bash
python deployment/deploy_two_stage.py
# Stage 1: Creates Agent Engine resource with Memory Bank config
# Stage 2: Deploys agent code with AGENT_ENGINE_ID env variable
# Returns: projects/.../reasoningEngines/...
```

See [Memory Bank](#memory-bank) section for details on why two-stage deployment is needed.

### Deploy to Cloud Run

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=your-project-id
export AGENT_ENGINE_RESOURCE_NAME=projects/.../reasoningEngines/...

# Deploy
./deployment/deploy-cloudrun.sh

# Access
open https://customer-support-ai-xxxxx-uc.a.run.app
```

## Observability

**Python Logging:**
```python
logging.info(f"[PRODUCT SEARCH] Query: {query}, Found: {len(results)} products")
```

**LoggingPlugin:**
- Automatic request/response logging
- Performance metrics
- Error tracking

**Cloud Logging:**
All logs sent to Google Cloud Logging for monitoring.

## Documentation

- **[GETTING_STARTED.md](./GETTING_STARTED.md)** - 📋 Complete setup checklist (START HERE)
- **[PYTHON_SETUP.md](./docs/PYTHON_SETUP.md)** - 🐍 Python 3.11 + pyenv installation guide
- **[PREREQUISITES.md](./docs/PREREQUISITES.md)** - ⚙️ Required APIs, IAM roles, GCP setup
- **[ENV_SETUP.md](./docs/ENV_SETUP.md)** - 🔧 Environment configuration with .env files
- **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** - 🚀 Deploy to Cloud Run & Vertex AI Agent Engine
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - 🏗️ System design, multi-agent workflows, RAG search

## Resources

- [Google ADK Documentation](https://cloud.google.com/vertex-ai/docs/agent-builder)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/reasoning-engine)
- [Firestore Vector Search](https://cloud.google.com/firestore/docs/vector-search)

## License

MIT License - See LICENSE file for details
