# Getting Started - Setup Checklist

Complete this checklist to deploy the Customer Support Multi-Agent System.

## ✅ Setup Checklist

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

- [ ] **Install Python 3.11+ using pyenv**

  **Install pyenv:**
  ```bash
  # macOS
  brew install pyenv

  # Linux
  curl https://pyenv.run | bash
  ```

  **Install Python 3.11.13:**
  ```bash
  pyenv install 3.11.13
  pyenv local 3.11.13  # Uses .python-version file
  ```

  **Verify:**
  ```bash
  python --version  # Should show Python 3.11.13
  ```

### Step 2: Clone and Setup Repository (2 minutes)

- [ ] **Clone repository**
  ```bash
  git clone https://github.com/your-repo/customer-support-mas.git
  cd customer-support-mas
  ```

- [ ] **Create virtual environment and install dependencies**
  ```bash
  # Verify Python version
  python --version  # Should be 3.11.13 (from .python-version)

  # Create virtual environment
  python -m venv .venv

  # Activate virtual environment
  source .venv/bin/activate  # macOS/Linux
  # OR
  .venv\Scripts\activate     # Windows

  # Install dependencies
  pip install -r requirements.txt
  ```

### Step 3: GCP Resources Setup (5-10 minutes)

Run automated setup scripts:

- [ ] **Enable APIs and configure IAM**
  ```bash
  ./scripts/setup_gcp.sh
  ```

  This script will:
  - ✓ Enable 10+ required GCP APIs
  - ✓ Create service account `customer-support-agent`
  - ✓ Grant IAM roles to service account
  - ✓ Grant IAM roles to your user
  - ✓ Create GCS bucket for staging

- [ ] **Setup Firestore database**
  ```bash
  ./scripts/setup_firestore.sh
  ```

  This script will:
  - ✓ Create Firestore database
  - ✓ Seed with sample data (products, orders, invoices)
  - ✓ Optionally add vector embeddings for RAG

**Manual alternative:** See [docs/PREREQUISITES.md](./docs/PREREQUISITES.md) for manual setup steps.

### Step 4: Environment Configuration (2 minutes)

- [ ] **Copy .env template**
  ```bash
  cp .env.example .env
  cp backend/.env.example backend/.env
  ```

- [ ] **Edit .env files**

  Update `.env` with your values:
  ```bash
  GOOGLE_CLOUD_PROJECT=your-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name  # From setup_gcp.sh output
  FIRESTORE_DATABASE=customer-support-db
  ```

  Update `backend/.env`:
  ```bash
  GOOGLE_CLOUD_PROJECT=your-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  FRONTEND_URL=http://localhost:3000
  PORT=8000
  ```

**Help:** See [docs/ENV_SETUP.md](./docs/ENV_SETUP.md) for detailed configuration guide.

### Step 5: Deploy to Vertex AI Agent Engine (5 minutes)

- [ ] **Deploy agent**
  ```bash
  # From project root directory
  python deployment/deploy.py --action deploy
  ```

  Expected output:
  ```
  ✓ Agent deployed successfully!
  Resource name: projects/123/locations/us-central1/reasoningEngines/456
  ```

- [ ] **Copy resource name to .env**

  Add to `.env` and `backend/.env`:
  ```bash
  AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
  ```

**Help:** See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for deployment troubleshooting.

### Step 5.5: Enable RAG Semantic Search (10 minutes)

This step enables semantic search (e.g., "gaming computer" finds "ROG Gaming Laptop").

- [ ] **Create vector index**
  ```bash
  # Use REST API
  curl -X POST \
    "https://firestore.googleapis.com/v1/projects/$GOOGLE_CLOUD_PROJECT/databases/$FIRESTORE_DATABASE/collectionGroups/products/indexes" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{
      "fields": [{
        "fieldPath": "embedding",
        "vectorConfig": {"dimension": 768, "flat": {}}
      }],
      "queryScope": "COLLECTION"
    }'
  ```

  Expected output:
  ```json
  {
    "name": "projects/.../operations/...",
    "metadata": {
      "state": "INITIALIZING",
      "index": "projects/.../indexes/..."
    }
  }
  ```

- [ ] **Wait for index to be ready (5-10 minutes)**
  ```bash
  # Check status
  gcloud firestore indexes composite list \
    --database=customer-support-db \
    --project=$GOOGLE_CLOUD_PROJECT

  # Wait for: STATE = READY
  ```

- [ ] **Add vector embeddings**
  ```bash
  # Once index is READY
  python scripts/add_embeddings.py \
    --project $GOOGLE_CLOUD_PROJECT \
    --database customer-support-db \
    --location us-central1
  ```

- [ ] **Redeploy agent with RAG enabled**
  ```bash
  python deployment/deploy.py --action deploy
  ```

- [ ] **Test semantic search**
  ```bash
  python deployment/deploy.py --action test_remote
  # Try: "Find me a gaming computer"
  # Should find "ROG Gaming Laptop" even without exact keywords!
  ```

**Note:** If you want to skip RAG for now, the agent will use keyword search as fallback.

**Help:** See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md#rag-setup-required-for-semantic-search) for detailed RAG setup.

### Step 6: Deploy Frontend + Backend (Optional, 10 minutes)

Skip this step if you only want to test the agent locally.

- [ ] **Update deployment script**

  Edit `deployment/deploy-cloudrun.sh`:
  ```bash
  PROJECT_ID="your-project-id"
  AGENT_ENGINE_RESOURCE_NAME="projects/123/.../reasoningEngines/456"
  ```

- [ ] **Deploy to Cloud Run**
  ```bash
  ./deployment/deploy-cloudrun.sh
  ```

- [ ] **Access web application**

  Open the URL from deployment output:
  ```
  https://customer-support-ai-xxxxx-uc.a.run.app
  ```

### Step 7: Verify Everything Works (2 minutes)

- [ ] **Run tests**
  ```bash
  pytest tests/ -v
  ```

- [ ] **Test agent locally**
  ```bash
  python deployment/deploy.py --action test_local
  ```

- [ ] **Test a few queries**
  - "Show me laptops under $600"
  - "Track order ORD-12345"
  - "Tell me everything about PROD-001"

## 🎉 You're Done!

Your multi-agent customer support system is now deployed and ready to use!

## What You've Set Up

✅ **Vertex AI Agent Engine** - Serverless agent deployment
✅ **Firestore Database** - Products, orders, invoices, users
✅ **RAG Search** - Semantic product search with embeddings (optional)
✅ **Memory Bank** - Cross-session user preferences
✅ **Multi-Agent System** - Root + Product + Order + Billing agents
✅ **Workflow Patterns** - Smart Tool Wrapper, SequentialAgent for validated refunds
✅ **Cloud Run** - Frontend + Backend web application (optional)


## Next Steps

### Test Different Scenarios

1. **Product Search with RAG**
   ```
   User: "Find me gaming laptops"
   → Uses semantic search to find relevant products
   ```

2. **Comprehensive Product Info**
   ```
   User: "Give me full details on PROD-001 including inventory and reviews"
   → Returns details + inventory + reviews automatically
   ```

3. **Refund Request (SequentialAgent)**
   ```
   User: "I want a refund for order ORD-12345"
   → Step 1: Validate order
   → Step 2: Check eligibility
   → Step 3: Process refund
   ```

4. **Order Tracking**
   ```
   User: "Where is my order ORD-12345?"
   → Retrieves order status from Firestore
   ```

### Learn More

- **[PYTHON_SETUP.md](./docs/PYTHON_SETUP.md)** - Python environment setup guide
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Understand the system design
- **[Testing](./README.md#testing)** - Run comprehensive test suite
- **[Memory Bank](./README.md#memory-bank)** - How agents remember preferences
- **[RAG Search](./README.md#rag-search)** - Semantic search explained

### Customize

- **Add new products**: Edit `customer_support_agent/database/seed.py`
- **Modify agents**: Edit files in `customer_support_agent/agents/`
- **Add new tools**: Create tools in `customer_support_agent/tools/`
- **Change models**: Update `customer_support_agent/config.py`

## Troubleshooting

If something doesn't work, check:

1. **[PYTHON_SETUP.md](./docs/PYTHON_SETUP.md)** - Python/pyenv issues
2. **[PREREQUISITES.md](./docs/PREREQUISITES.md)** - API/IAM issues
3. **[ENV_SETUP.md](./docs/ENV_SETUP.md)** - Configuration issues
4. **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** - Deployment errors
5. **[Troubleshooting section](./README.md#troubleshooting)** - Common errors

## Get Help

- Check logs: `gcloud run services logs read customer-support-ai --limit=50`
- View agent engine status: `gcloud ai reasoning-engines list`
- Test locally first: `python deployment/deploy.py --action test_local`


## Production Deployment

For production use:

1. Use Cloud Secret Manager for credentials
2. Set up monitoring and alerts
3. Configure auto-scaling on Cloud Run
4. Enable HTTPS and custom domain
5. Set up CI/CD pipeline
6. Review security settings

See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for production deployment guide.

---

**Congratulations! You've successfully deployed a production-ready multi-agent customer support system!** 🎊
