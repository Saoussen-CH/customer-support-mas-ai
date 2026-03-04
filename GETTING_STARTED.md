# Getting Started — Setup Checklist

Complete this checklist to deploy the Customer Support Multi-Agent System.

## Setup Checklist

### Step 1: Prerequisites (5 minutes)

- [ ] **GCP Account**
  - Create GCP account at [console.cloud.google.com](https://console.cloud.google.com)
  - Enable billing on your account

- [ ] **Create GCP Project**
  ```bash
  gcloud projects create YOUR_PROJECT_ID --name="Customer Support Agent"
  gcloud config set project YOUR_PROJECT_ID
  ```

- [ ] **Install gcloud CLI**
  - Download from [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
  - Verify: `gcloud --version`

- [ ] **Authenticate**
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```

### Step 2: Clone and Install Dependencies (2 minutes)

- [ ] **Clone repository**
  ```bash
  git clone https://github.com/your-repo/customer-support-mas-kaggle.git
  cd customer-support-mas-kaggle
  ```

- [ ] **Install dependencies** (uses `uv` — installs Python 3.11 automatically)
  ```bash
  make install
  ```

  This installs all Python dependencies from `pyproject.toml` + sets up pre-commit hooks.

### Step 3: GCP Resources Setup (5-10 minutes)

- [ ] **Enable APIs and configure IAM**
  ```bash
  bash scripts/setup_gcp.sh
  ```

  This script will:
  - Enable 10+ required GCP APIs
  - Create service account `customer-support-agent`
  - Grant IAM roles to service account and your user
  - Create GCS bucket for staging

- [ ] **Setup Firestore database and seed data**
  ```bash
  make setup-firestore
  ```

  This creates the Firestore database and seeds it with sample products, orders, invoices, and users.

**Manual alternative:** See [docs/PREREQUISITES.md](./docs/PREREQUISITES.md) for manual setup steps.

### Step 4: Environment Configuration (2 minutes)

- [ ] **Copy .env template**
  ```bash
  cp .env.example .env
  ```

- [ ] **Edit `.env` with your values**
  ```bash
  GOOGLE_CLOUD_PROJECT=your-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  GOOGLE_CLOUD_STORAGE_BUCKET=gs://your-bucket-name
  FIRESTORE_DATABASE=customer-support-db
  ```

**Help:** See [docs/ENV_SETUP.md](./docs/ENV_SETUP.md) for full configuration details.

### Step 5: Deploy to Vertex AI Agent Engine (5 minutes)

- [ ] **Deploy agent** (two-stage: deploys AdkApp + configures Memory Bank)
  ```bash
  make deploy-agent-engine
  ```

  Expected output:
  ```
  ✓ Agent deployed successfully!
  Resource name: projects/123/locations/us-central1/reasoningEngines/456
  ```

- [ ] **Copy resource name to .env**
  ```bash
  AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
  ```

**Help:** See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for deployment troubleshooting.

### Step 5.5: Enable RAG Semantic Search (10 minutes)

This enables "gaming computer" to find "ROG Gaming Laptop" via semantic search.

- [ ] **Create vector index**
  ```bash
  make vector-index
  ```

- [ ] **Wait for index to be ready (5-10 minutes)**
  ```bash
  gcloud firestore indexes composite list \
    --database=customer-support-db \
    --project=$GOOGLE_CLOUD_PROJECT
  # Wait for: STATE = READY
  ```

- [ ] **Add vector embeddings to products**
  ```bash
  make add-embeddings
  ```

- [ ] **Redeploy agent with RAG enabled**
  ```bash
  make deploy-agent-engine
  ```

**Note:** If you skip RAG, the agent falls back to keyword search automatically.

### Step 6: Deploy Frontend + Backend to Cloud Run (10 minutes)

Skip this step if you only want to test the agent locally.

- [ ] **Deploy to Cloud Run**
  ```bash
  make deploy-cloud-run
  ```

- [ ] **Access web application**

  Open the URL from the deployment output:
  ```
  https://customer-support-ai-xxxxx-uc.a.run.app
  ```

### Step 7: Run Tests (2 minutes)

- [ ] **Run all tests**
  ```bash
  make test
  ```

  Or run individual layers:
  ```bash
  make test-tools        # Pure Python, no LLM (free, fast)
  make test-unit         # Unit agent eval (LLM calls)
  make test-integration  # Multi-agent handoff eval (LLM calls)
  ```

- [ ] **Test agent locally**
  ```bash
  make test-local
  ```

### Step 8: Post-Deploy Evaluation (optional)

Evaluate the live deployed agent against production test cases:

```bash
make eval-post-deploy AGENT_ENGINE_ID=your-engine-id
```

Scores appear in **Vertex AI → Experiments → post-deploy-eval**. Results must pass `TOOL_USE_QUALITY ≥ 0.5` and `FINAL_RESPONSE_QUALITY ≥ 0.5`.

### Step 9: Set Up CI/CD (optional)

- [ ] **One-time Cloud Build setup** (IAM, Artifact Registry, Secret Manager)
  ```bash
  make setup-cloud-build \
    PROJECT_ID=your-project-id \
    REGION=us-central1 \
    STAGING_BUCKET=your-bucket-name
  ```

- [ ] **Connect GitHub repo** in Cloud Console → Cloud Build → Triggers → Connect Repository

- [ ] **Create triggers** using the commands printed by the setup script

See **[docs/CI_CD.md](./docs/CI_CD.md)** for full setup instructions.

---

## You're Done!

Your multi-agent customer support system is now deployed and ready to use!

## What You've Set Up

- **Vertex AI Agent Engine** — Serverless agent deployment
- **Firestore Database** — Products, orders, invoices, users
- **RAG Search** — Semantic product search with embeddings
- **Memory Bank** — Cross-session user preferences
- **Multi-Agent System** — Root + Product + Order + Billing agents
- **Sequential Workflow** — Validated refund processing
- **Cloud Run** — Frontend + Backend web application

## Test These Scenarios

1. **Product Search with RAG**
   ```
   "Find me gaming laptops"
   → Semantic search finds ROG Gaming Laptop
   ```

2. **Comprehensive Product Info**
   ```
   "Tell me everything about PROD-001"
   → Returns details + inventory + reviews in one call
   ```

3. **Refund Request (SequentialAgent)**
   ```
   "I want a refund for order ORD-12345"
   → Step 1: Validate order ✓
   → Step 2: Check eligibility ✓
   → Step 3: Process refund ✓
   ```

4. **Order Tracking**
   ```
   "Where is my order ORD-67890?"
   → Retrieves order status and tracking info
   ```

## Customize

- **Add new products**: Edit `customer_support_agent/database/seed.py`
- **Modify agents**: Edit files in `customer_support_agent/agents/`
- **Add new tools**: Create tools in `customer_support_agent/tools/`
- **Change models**: Update `customer_support_agent/config.py`

## Troubleshooting

1. **[PREREQUISITES.md](./docs/PREREQUISITES.md)** — API/IAM issues
2. **[ENV_SETUP.md](./docs/ENV_SETUP.md)** — Configuration issues
3. **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** — Deployment errors

```bash
# Useful debug commands
gcloud run services logs read customer-support-ai --limit=50
gcloud ai reasoning-engines list
make test-local
```

## Documentation

- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** — System design and agent architecture
- **[EVAL_ARCHITECTURE.md](./docs/EVAL_ARCHITECTURE.md)** — Evaluation strategy (3 layers + post-deploy)
- **[CI_CD.md](./docs/CI_CD.md)** — Cloud Build pipeline setup
- **[MEMORY_BANK.md](./docs/MEMORY_BANK.md)** — Memory Bank implementation
