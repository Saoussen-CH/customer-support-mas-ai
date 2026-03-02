# Multi-Agent Customer Support System

A production-ready customer support system with React frontend and FastAPI backend, built with Google's Agent Development Kit (ADK). Features multi-agent orchestration, RAG semantic search, Memory Bank, and Sequential workflow pattern for validated refund processing.

## Business Context

This system is built for a **consumer electronics and office furniture e-commerce store** (similar to Best Buy or Newegg). The AI agents handle:

| Domain | Examples |
|--------|----------|
| **Products** | Laptops, headphones, keyboards, office chairs, standing desks |
| **Orders** | Tracking shipments, delivery status, order history |
| **Billing** | Invoices, payment status, receipts |
| **Refunds** | 30-day return window, validated refund processing |

The architecture can be adapted to other retail domains by modifying the product catalog and business rules.

## Architecture

![System Architecture](./images/architecture.drawio.png)

The system is built on Google Cloud Platform with:
- **Frontend:** React/TypeScript on Cloud Run
- **Backend:** FastAPI + Cloud Proxy on Cloud Run
- **AI Layer:** Vertex AI Agent Engine with multi-agent orchestration
- **Data Layer:** Firestore with vector search, Memory Bank for cross-session memory

For detailed architecture documentation, see [ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Key Features

| Course Topic | Implementation | Production Enhancement |
|-------------|----------------|----------------------|
| **Multi-Agent Orchestration** | ✅ Root + 3 Specialists + Workflow agents | Cost-optimized with Gemini 2.5 Pro + Flash |
| **Sequential Workflows** | ✅ 3-step refund validation pipeline | Validation gates prevent invalid operations |
| **Session Management** | ✅ Vertex AI Agent Engine sessions | Backend proxy with JWT auth + multi-user support |
| **Memory Bank** | ✅ Vertex AI Memory Bank with callbacks | Cross-session preference recall |
| **Observability** | ✅ LoggingPlugin + Cloud Logging | Production-ready monitoring |
| **Evaluation & Testing** | ✅ Vertex AI Gen AI Evaluation + AgentEvaluator | 3-layer test suite with switchable eval profiles (fast/standard/full) |
| **Deployment** | ✅ Vertex AI Agent Engine + Cloud Run | Full-stack with automation scripts |
| **RAG Semantic Search** | 🚀 text-embedding-004 (768-dim) | Beyond course: Vector search on products |
| **Smart Tool Design** | 🚀 Batch tools + smart wrappers | Beyond course: Replaced Loop/Parallel patterns |
| **CI/CD** | 🚀 Cloud Build + GitHub Actions | Beyond course: Full pipeline with eval gating |
| **Post-Deploy Eval** | 🚀 Vertex AI Gen AI Evaluation Service | Beyond course: Live agent scoring after deploy |


- 🤖 **Multi-Agent System** - Root agent coordinates specialized agents (Product, Order, Billing)
- 🧠 **Memory Bank** - Remembers user preferences across sessions
- 🔍 **RAG Semantic Search** - Vector embeddings for intelligent product search
- ⚡ **Sequential Workflow** - SequentialAgent for validated refund processing with step-by-step validation gates
- 🛡️ **Model Armor** - Screens all Gemini calls for prompt injection, jailbreaks, and harmful content
- 👥 **User Management** - Email/password auth or guest access
- 💬 **Multi-Session Conversations** - Multiple chat threads per user
- 🔄 **Retry Logic** - Automatic exponential backoff for transient errors
- 🧪 **Comprehensive Testing** - Pytest automation with ADK AgentEvaluator
- 🎤 **Voice Features** - Speech-to-text input and text-to-speech output
- ☁️ **Cloud Deployment** - Deploy to Cloud Run + Vertex AI Agent Engine

## Quick Start

> 📖 **New to the project?** See **[GETTING_STARTED.md](./GETTING_STARTED.md)** for a complete step-by-step setup checklist.

### Prerequisites

- **Python 3.11** (managed via `uv` — installed automatically)
- **GCP project** with billing enabled
- **gcloud CLI** installed and authenticated

```bash
gcloud auth login
gcloud auth application-default login
```

### Bootstrap infrastructure with Terraform

```bash
# 1. Install dependencies (uv + pre-commit hooks)
make install

# 2. Configure Terraform
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform.tfvars — set project_id, staging_bucket_name, github_owner

# 3. Apply all infrastructure (APIs, IAM, Firestore, GCS, AR, triggers)
make infra-up

# 4. Seed the database
make seed-db
```

See **[PREREQUISITES.md](./docs/PREREQUISITES.md)** for detailed GCP setup instructions.

### Deploy the System

```bash
# 1. Configure environment variables
cp .env.example .env
# Edit .env with your GCP project details

# 2. Deploy agent to Vertex AI Agent Engine (two-stage: deploys + configures Memory Bank)
make deploy-agent-engine

# 3. Deploy frontend + backend to Cloud Run
make deploy-cloud-run

# 4. Access the web application
open https://customer-support-ai-xxxxx-uc.a.run.app
```

## Project Structure

```
customer-support-mas/
├── Makefile                      # Developer shortcuts (make test, make lint, make deploy-*)
├── pyproject.toml                # Python project config and dependencies (uv)
├── terraform/                    # Infrastructure as Code (Terraform)
│   ├── main.tf                   # Provider config, locals (service account emails)
│   ├── variables.tf              # Input variables
│   ├── outputs.tf                # Key outputs (bucket, AR URL, trigger IDs)
│   ├── apis.tf                   # GCP API enablement
│   ├── iam.tf                    # IAM bindings for all service accounts
│   ├── infrastructure.tf         # Firestore, GCS bucket, Artifact Registry
│   ├── secrets.tf                # Secret Manager (staging-bucket secret)
│   ├── cicd.tf                   # Cloud Build triggers + Cloud Scheduler
│   ├── model_armor.tf            # Model Armor floor settings
│   └── terraform.tfvars.example  # Variable template (copy → terraform.tfvars)
├── cloudbuild/
│   ├── pr-checks.yaml            # PR checks (fast eval + ruff format)
│   ├── cloudbuild.yaml           # CI pipeline (develop push)
│   ├── cloudbuild-deploy.yaml    # CI + CD pipeline (main push)
│   └── cloudbuild-nightly.yaml   # Full eval + post-deploy eval (nightly/manual)
├── customer_support_agent/       # Core agent system
│   ├── main.py                   # Entry point
│   ├── config.py                 # Agent configurations
│   ├── agents/                   # Agent definitions
│   │   ├── root_agent.py         # Root coordinator (Gemini 2.5 Pro)
│   │   ├── product_agent.py      # Product specialist (Gemini 2.5 Flash)
│   │   ├── order_agent.py        # Order specialist
│   │   ├── billing_agent.py      # Billing specialist
│   │   ├── workflow_agents.py    # SequentialAgent for refund validation
│   │   └── callbacks.py          # Memory Bank callbacks (after_agent_callback)
│   ├── tools/                    # Tool implementations
│   │   ├── product_tools.py      # 8 product tools (incl. get_product_info smart wrapper)
│   │   ├── order_tools.py        # 2 order tools
│   │   ├── billing_tools.py      # 6 billing tools
│   │   └── workflow_tools.py     # Refund workflow tools
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
│   ├── deploy.py                 # Deploy to Agent Engine with Memory Bank (two-stage)
│   └── deploy-cloudrun.sh        # Deploy to Cloud Run
├── scripts/                      # Utility scripts
│   ├── eval_vertex.py            # Post-deploy eval against Agent Engine
│   ├── setup-cloud-build.sh      # One-time Cloud Build IAM/trigger setup
│   ├── add_embeddings.py         # Add vector embeddings for RAG
│   ├── create_vector_index.py    # Create Firestore vector index
│   ├── generate_eval_dataset.py  # Generate unit eval datasets (.test.json)
│   └── generate_integration_evalset.py  # Generate integration eval datasets
├── tests/                        # Test suite
│   ├── conftest.py               # Root fixtures (mock DB, mock RAG)
│   ├── mock_firestore.py         # In-memory Firestore client
│   ├── mock_rag_search.py        # Keyword-based RAG search mock
│   ├── eval_configs/             # Switchable eval profiles (EVAL_PROFILE env var)
│   │   ├── __init__.py           # load_eval_config(), load_eval_set()
│   │   ├── unit/                 # fast.json, standard.json, full.json
│   │   ├── integration/          # fast.json, standard.json, full.json
│   │   └── post_deploy/          # standard.json, full.json
│   ├── unit/                     # Unit tests (pure Python + agent eval)
│   │   ├── test_mock_rag.py      # MockRAGProductSearch tests
│   │   ├── test_tools.py         # Direct tool function tests
│   │   ├── test_refund_standalone.py  # Refund workflow standalone
│   │   └── test_agent_eval_ci.py # ADK AgentEvaluator tests
│   ├── integration/              # Integration tests (multi-agent handoffs)
│   │   └── test_integration_eval_ci.py
│   └── post_deploy/              # Post-deployment eval against live Agent Engine
│       └── datasets/             # post_deploy_cases.json (9 live eval cases)
└── docs/                         # Documentation
    ├── ARCHITECTURE.md           # System architecture
    ├── CI_CD.md                  # CI/CD setup guide
    ├── DEPLOYMENT.md             # Deployment guide
    ├── EVAL_ARCHITECTURE.md      # Evaluation architecture (3-layer strategy)
    ├── EVAL_STRATEGY.md          # Eval profiles and metrics
    ├── PREREQUISITES.md          # GCP setup, APIs, IAM roles
    └── VERTEX_CREATE_EVALUATION_RUN.md  # create_evaluation_run() reference (re-enable guide)
```

## Technology Stack

**Frontend:** React 18 · TypeScript · Vite · Axios

**Backend:** FastAPI · Python 3.11 · Pydantic · Token-based auth

**AI/ML:** Google ADK · Gemini 2.5 Pro/Flash · Vertex AI Agent Engine · Vertex AI Memory Bank · Vertex AI Agent Engine Sessions · text-embedding-004 · gemini-embedding-001

**Data:** Firestore (NoSQL + vector search)

**Infrastructure:** Cloud Run · Artifact Registry · Docker · Cloud Build · Cloud Logging · Terraform

**Testing:** pytest · AgentEvaluator · Vertex AI Gen AI Evaluation Service

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
# Only way to process refunds — ensures proper validation
```

### Efficient Multi-Product Fetch
```python
# Use case: "Show me details on all of them" (after search)
# Uses get_all_saved_products_info — single call for all products
# Replaces iterative LoopAgent approach to avoid timeouts
```

## Testing

Three test layers — pure Python (free), unit agent eval (LLM), and integration agent eval (LLM) — plus post-deployment evaluation against the live Agent Engine.

All pre-deploy tests run against **in-memory mocks** (MockFirestoreClient + MockRAGProductSearch) — no live Firestore or RAG calls.

### Running Tests

```bash
# Pure Python tests (no LLM calls, no cost)
make test-tools

# Unit agent eval (LLM calls)
make test-unit

# Integration eval (LLM calls)
make test-integration

# Everything
make test
```

### Eval Profiles

Agent eval tests use a **profile-based evaluation config system** switchable via `EVAL_PROFILE`:

```bash
# Fast — Rouge-1 only (free, ~30s)
EVAL_PROFILE=fast make test-unit

# Standard — default
make test-unit

# Full — all metrics including LLM-as-judge
EVAL_PROFILE=full make test-integration
```

| Profile | Unit Metrics | Integration Metrics | Cost | Use Case |
|---------|-------------|-------------------|------|----------|
| **fast** | `response_match_score` (Rouge-1) | `response_match_score` (Rouge-1) | Free | Dev iteration, quick feedback |
| **standard** | + `tool_trajectory_avg_score` | + `rubric_based_tool_use_quality_v1` (LLM judge) | Low | Default CI |
| **full** | + `final_response_match_v2` (LLM judge) | + `final_response_match_v2` (LLM judge) | Higher | Pre-release quality gate |

**Why different metrics for unit vs integration?**
- **Unit tests** call tools with structured args (`product_id: "PROD-001"`) — exact `tool_trajectory_avg_score` matching works
- **Integration tests** route through the root agent which paraphrases args differently each run — `rubric_based_tool_use_quality_v1` (LLM semantic judge) is required

Config files live in `tests/eval_configs/{unit,integration}/{fast,standard,full}.json`.

### Post-Deploy Evaluation

After deploying to Agent Engine, run live evaluation against the deployed agent:

```bash
# Evaluate with standard profile (9 cases: product, order, billing, refund)
make eval-post-deploy AGENT_ENGINE_ID=<your-engine-id>

# Full profile (more metrics)
make eval-post-deploy AGENT_ENGINE_ID=<your-engine-id> EVAL_PROFILE=full

# Save HTML report (per-item scores + explanations, open in browser)
python scripts/eval_vertex.py --agent-engine-id <id> --report eval_report.html
```

Results are logged to **Vertex AI → Experiments → post-deploy-eval** and uploaded to GCS.

See [EVAL_ARCHITECTURE.md](./docs/EVAL_ARCHITECTURE.md) for the full evaluation strategy.

### Generating Eval Datasets

**Unit tests** — single-turn, individual agents:
```bash
make gen-evalset AGENT=product   # product | order | billing
make gen-evalset AGENT=order DELAY=10
```

**Integration tests** — multi-turn, root orchestrator:
```bash
make gen-integration-evalset
make gen-integration-evalset SUITE=product_handoffs
# Suites: product_handoffs, order_handoffs, billing_handoffs, refund_handoffs,
#         multi_agent, e2e, error_handling, session_persistence
```

## CI/CD Pipeline

The project uses **Google Cloud Build** for CI/CD.


Four pipelines cover the full lifecycle:

| Trigger | Config | `EVAL_PROFILE` | What it does |
|---------|--------|----------------|--------------|
| PR to `main` | `cloudbuild/pr-checks.yaml` | `fast` | Lint + tool tests + fast eval |
| Push to `develop` | `cloudbuild/cloudbuild.yaml` | `standard` | Full CI |
| Push to `main` | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | CI + Docker build + Cloud Run deploy |
| Nightly / Manual | `cloudbuild/cloudbuild-nightly.yaml` | `full` | All metrics + optional post-deploy eval |

**One-time setup:**
```bash
make setup-cloud-build \
  PROJECT_ID=your-project-id \
  REGION=us-central1 \
  STAGING_BUCKET=your-bucket-name
```

Then connect your GitHub repo in **Cloud Console → Cloud Build → Triggers → Connect Repository** and create the triggers (commands printed by the setup script).

See **[CI_CD.md](./docs/CI_CD.md)** for full setup and trigger configuration.


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
# 1. Create vector index
make vector-index

# 2. Wait for index status = READY (5-10 min)
gcloud firestore indexes composite list --database=customer-support-db

# 3. Add embeddings to products
make add-embeddings

# 4. Redeploy agent
make deploy-agent-engine
```

**Fallback**: If RAG is unavailable, keyword search is used automatically.

## Memory Bank

Remembers user preferences across sessions using Vertex AI Memory Bank with automatic extraction and recall.

```python
# Automatically extracted from conversations:
# - "Customer prefers products under $500"
# - "User had delivery issues with order ORD-12345"
# - "Customer is interested in gaming laptops"
```

**Implementation:** `callbacks.py` registers an `after_agent_callback` (`auto_save_to_memory`) on the root agent. After each conversation turn, it triggers memory extraction and saves relevant facts to the Vertex AI Memory Bank.

**Two-Stage Deployment:** `deploy.py` solves the chicken-and-egg problem where Memory Bank configuration requires an `agent_engine_id` that only exists after initial deployment:

1. **Stage 1:** Deploy AdkApp → get `agent_engine_id`
2. **Stage 2:** Update Agent Engine with Memory Bank configuration

Agents use `PreloadMemoryTool` to automatically load relevant memories at conversation start.

See [MEMORY_BANK.md](./docs/MEMORY_BANK.md) for full implementation details.

## Configuration

```bash
cp .env.example .env
```

**Required:**
- `GOOGLE_CLOUD_PROJECT` — Your GCP project ID
- `GOOGLE_CLOUD_STORAGE_BUCKET` — GCS bucket for staging (with `gs://` prefix)
- `AGENT_ENGINE_RESOURCE_NAME` — Deployed agent resource name

**Optional:**
- `GOOGLE_CLOUD_LOCATION` — GCP region (default: `us-central1`)
- `FIRESTORE_DATABASE` — Firestore database name (default: `(default)`)
- `GOOGLE_GENAI_USE_VERTEXAI` — Use Vertex AI (default: `1`)
- `FRONTEND_URL` — Frontend URL for CORS (default: `http://localhost:3000`)
- `PORT` — Backend port (default: `8000`)

See **[ENV_SETUP.md](./docs/ENV_SETUP.md)** for full environment configuration.

## Database Schema

Firestore collections:

- **users/** — User accounts
- **sessions/** — Conversation sessions
- **messages/** — Chat messages
- **products/** — Products with embeddings (768-dim vectors)
- **orders/** — Customer orders
- **invoices/** — Billing invoices

## Example Interactions

**Product Search:**
```
User: Show me laptops under $600
Agent: [Uses search_products with RAG]
      Returns: ProBook Laptop 15 ($999.99), ROG Gaming Laptop ($1,299.99)
```

**Comprehensive Lookup:**
```
User: Tell me everything about PROD-001
Agent: [Uses get_product_info — smart unified tool]
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

```bash
# Deploy agent with Memory Bank (two-stage)
make deploy-agent-engine
# Returns: projects/.../reasoningEngines/...
```

### Deploy to Cloud Run

```bash
make deploy-cloud-run
# Access: https://customer-support-ai-xxxxx-uc.a.run.app
```

## Security

### Model Armor

[Model Armor](https://cloud.google.com/model-armor/docs) screens every Gemini `generateContent` call for prompt injection, jailbreaks, and harmful content — automatically, with no code changes to the agents.

```bash
# Enable with INSPECT_AND_BLOCK floor settings (recommended for production)
make setup-model-armor

# With a named template for fine-grained control
make setup-model-armor CREATE_TEMPLATE=1
```

**What it protects against:**
- Users attempting to jailbreak the root agent into bypassing refund validation
- Prompt injection via product search queries or order IDs
- Harmful or sensitive data in billing/invoice responses

See [ARCHITECTURE.md — Security](./docs/ARCHITECTURE.md#security) for full details.

## Observability

**LoggingPlugin** provides automatic request/response logging, performance metrics, and error tracking. All logs go to Google Cloud Logging.

```python
# Custom structured logging in tools
logging.info(f"[PRODUCT SEARCH] Query: {query}, Found: {len(results)} products")
```

## Documentation

- **[GETTING_STARTED.md](./GETTING_STARTED.md)** — 📋 Complete setup checklist (START HERE)
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** — 🏗️ System design, multi-agent workflows, RAG, Model Armor
- **[PREREQUISITES.md](./docs/PREREQUISITES.md)** — ⚙️ Required APIs, IAM roles, GCP setup
- **[ENV_SETUP.md](./docs/ENV_SETUP.md)** — 🔧 Environment configuration
- **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** — 🚀 Deploy to Cloud Run & Vertex AI Agent Engine
- **[CI_CD.md](./docs/CI_CD.md)** — 🔄 Cloud Build + GitHub Actions setup
- **[EVAL_ARCHITECTURE.md](./docs/EVAL_ARCHITECTURE.md)** — 🧪 3-layer evaluation strategy
- **[EVAL_STRATEGY.md](./docs/EVAL_STRATEGY.md)** — 📊 Eval profiles, metrics, and dataset management
- **[MEMORY_BANK.md](./docs/MEMORY_BANK.md)** — 🧠 Memory Bank implementation details
- **[PYTHON_SETUP.md](./docs/PYTHON_SETUP.md)** — 🐍 Python 3.11 + uv setup
- **[VERTEX_CREATE_EVALUATION_RUN.md](./docs/VERTEX_CREATE_EVALUATION_RUN.md)** — 📋 create_evaluation_run() re-enablement guide

## Resources

- [Google ADK Documentation](https://cloud.google.com/vertex-ai/docs/agent-builder)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/reasoning-engine)
- [Firestore Vector Search](https://cloud.google.com/firestore/docs/vector-search)
- [Vertex AI Gen AI Evaluation](https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview)

## License

MIT License - See LICENSE file for details
