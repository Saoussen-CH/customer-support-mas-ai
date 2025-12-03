# Deployment Guide

This guide covers deploying the customer support multi-agent system to Google Cloud.

> 📝 **Note:** For current deployment status and known issues, see [DEPLOYMENT_NOTES.md](../DEPLOYMENT_NOTES.md)

## Prerequisites

- Google Cloud Project with billing enabled
- APIs enabled: Firestore, Vertex AI, Cloud Run
- `gcloud` CLI installed and authenticated
- Python 3.11+

## Quick Deploy

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Edit with your project details

# 2. Set up service account permissions (REQUIRED)
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Grant Firestore access to Cloud Run service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"

# Grant Firestore access to Agent Engine service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# 3. Deploy to Agent Engine
python deployment/deploy.py --action deploy

# 4. Create Vector Index for RAG (Required for semantic search)
# Via REST API:
curl -X POST \
  "https://firestore.googleapis.com/v1/projects/YOUR_PROJECT/databases/YOUR_DB/collectionGroups/products/indexes" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": [{
      "fieldPath": "embedding",
      "vectorConfig": {"dimension": 768, "flat": {}}
    }],
    "queryScope": "COLLECTION"
  }'

# Or use the helper script:
python scripts/create_vector_index.py

# 5. Add vector embeddings to products
python scripts/add_embeddings.py \
  --project YOUR_PROJECT \
  --database YOUR_DB \
  --location us-central1

# 6. Redeploy with RAG enabled
python deployment/deploy.py --action deploy

# 7. (Optional) Deploy frontend/backend to Cloud Run
./deployment/deploy-cloudrun.sh
```

## Deployment Options

### Option 1: Vertex AI Agent Engine (Recommended)

Deploy the agent as a serverless reasoning engine:

```bash
# Deploy agent
python deployment/deploy.py --action deploy
```

**Important:** Always run from project root directory.

**What it does:**
- Packages the agent code
- Uploads to GCS staging bucket
- Creates a reasoning engine on Vertex AI
- Returns a resource name for querying

**Environment variables:**
- `GOOGLE_CLOUD_PROJECT` - Your GCP project ID
- `GOOGLE_CLOUD_LOCATION` - Region (default: us-central1)
- `GOOGLE_CLOUD_STORAGE_BUCKET` - GCS bucket for staging

**Output:**
```
Agent Engine Resource Name: projects/.../locations/.../reasoningEngines/...
```

Save this resource name:
```bash
export AGENT_ENGINE_RESOURCE_NAME="projects/.../reasoningEngines/..."
```

### Option 2: Cloud Run (Full Stack)

Deploy frontend + backend to Cloud Run:

```bash
./deployment/deploy-cloudrun.sh
```

**What it deploys:**
- FastAPI backend (connects to Agent Engine)
- React frontend
- Firestore database

**Configuration:**
Edit `deployment/deploy-cloudrun.sh` and set:
- `PROJECT_ID` - Your GCP project
- `REGION` - Deployment region
- `AGENT_ENGINE_RESOURCE_NAME` - From Agent Engine deployment

**Access:**
```
https://customer-support-ai-xxxxx-uc.a.run.app
```

## Management

### List Deployed Agents

```bash
python deployment/manage_agent.py list
```

### Query a Deployed Agent

```bash
python deployment/manage_agent.py query \
  --resource-name="projects/.../reasoningEngines/..." \
  --message="Show me laptops under $600"
```

### Delete a Deployed Agent

```bash
python deployment/manage_agent.py delete \
  --resource-name="projects/.../reasoningEngines/..."
```

## RAG Setup (Required for Semantic Search)

### 1. Create Vector Index

Firestore requires a vector index for semantic search:

**Method 1: REST API (Recommended)**
```bash
curl -X POST \
  "https://firestore.googleapis.com/v1/projects/YOUR_PROJECT/databases/YOUR_DB/collectionGroups/products/indexes" \
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

**Method 2: Helper Script**
```bash
python scripts/create_vector_index.py
# Will show instructions and check if index exists
```

**Check Index Status:**
```bash
gcloud firestore indexes composite list \
  --database=YOUR_DB \
  --project=YOUR_PROJECT
# Look for: STATE = READY
```

### 2. Add Vector Embeddings

Once the index is READY (takes 5-10 minutes):

```bash
python scripts/add_embeddings.py \
  --project YOUR_PROJECT \
  --database YOUR_DB \
  --location us-central1
```

This adds 768-dimensional embeddings to all products using `text-embedding-004`.

### 3. Redeploy Agent

After embeddings are added:

```bash
python deployment/deploy.py --action deploy
```

Now semantic search will work! Try: "Find me a gaming computer" (even though no product has those exact words).

## Service Account Permissions

### Required Permissions for Deployment

When deploying to Cloud Run and using Agent Engine, ensure the following service accounts have the correct permissions:

#### 1. Cloud Run Service Account Permissions

The Cloud Run compute service account needs Firestore access:

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Grant Firestore access to Cloud Run service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"

# Grant logging permissions (if not already set)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

#### 2. Agent Engine (Reasoning Engine) Service Account Permissions

The Agent Engine service account needs Firestore access to execute tools:

```bash
# Grant Firestore access to Agent Engine service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

#### 3. Verify Permissions

Check that permissions were granted:

```bash
# List all IAM bindings for Firestore
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/datastore.user"
```

You should see both service accounts listed:
- `{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`
- `service-{PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com`

### Common Permission Errors

**Error: `403 Missing or insufficient permissions`**
- **Cause:** Service account lacks Firestore access
- **Solution:** Run the permission commands above

**Error: `429 RESOURCE_EXHAUSTED`**
- **Cause:** Gemini API quota limits exceeded
- **Solution:** Wait 1-2 minutes for quotas to reset, or request quota increase

## Database Setup

### 1. Create Firestore Database

```bash
gcloud firestore databases create \
  --location=us-central1 \
  --database=customer-support-db
```

### 2. Seed Data

```bash
python -m customer_support_agent.database.seed
```

This creates:
- Products (10 items)
- Orders (3 sample orders)
- Invoices, payments, refunds
- Review and inventory data

### 3. Add Vector Embeddings (See RAG Setup section above)

Vector embeddings are required for semantic search. See the **RAG Setup** section at the top of this document for complete instructions.

## Environment Variables

### Required

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_STORAGE_BUCKET="gs://your-bucket"
```

### Optional

```bash
export GOOGLE_CLOUD_LOCATION="us-central1"        # Default region
export FIRESTORE_DATABASE="customer-support-db"   # Database name
export AGENT_ENGINE_RESOURCE_NAME="projects/..."  # Deployed agent
```

## Troubleshooting

### API Not Enabled

```
Error: API [aiplatform.googleapis.com] not enabled
```

**Solution:**
```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable run.googleapis.com
```

### Permission Denied

```
Error: Permission denied on resource
Error: 403 Missing or insufficient permissions
```

**Solution:** Ensure service accounts have required roles.

**For Cloud Run:**
```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"
```

**For Agent Engine:**
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

See the **Service Account Permissions** section above for complete setup instructions.

### Deployment Fails

Check logs:
```bash
gcloud run services logs read customer-support-ai --limit=50
```

### Agent Engine Not Found

Verify deployment:
```bash
python deployment/manage_agent.py list
```

## Costs

**Vertex AI Agent Engine:**
- $0.002 per 1K characters input
- $0.006 per 1K characters output

**Cloud Run:**
- Pay per request
- Free tier: 2M requests/month

**Firestore:**
- Pay per read/write
- Free tier: 50K reads, 20K writes/day

**Estimate:** ~$5-20/month for development usage

## Next Steps

After deployment:

1. Test the deployment:
   ```bash
   python deployment/manage_agent.py query \
     --message="Show me laptops"
   ```

2. Access the web UI (if using Cloud Run)

3. Monitor usage in Google Cloud Console

## Common Issues

### Empty Responses from Deployed Agent

**Symptom:** Agent deploys but returns "I apologize, but I didn't receive a response"

**Causes & Solutions:**

1. **Vector index not created**
   - Solution: Follow RAG Setup section above
   - Create vector index via REST API or helper script
   - Wait for status = READY (5-10 minutes)

2. **Embeddings not added**
   - Solution: Run `python scripts/add_embeddings.py`
   - Redeploy after adding embeddings

3. **RAG search failing**
   - Temporary workaround: Disable RAG in `customer_support_agent/services/rag_search.py`
   - Set `USE_RAG = False`
   - Uses keyword search instead

### Vector Search Returns 0 Results

**Symptom:** Vector index is READY, products have embeddings, but `find_nearest` returns 0 results

**Current Status:**
- The system is configured to use **fallback cosine similarity search** automatically
- This provides the same semantic search functionality without requiring the vector index
- Performance is acceptable for small-to-medium product catalogs (<1000 products)

**What's Currently Working:**
- ✅ Semantic search with embeddings (via fallback method)
- ✅ Category filtering
- ✅ Price filtering
- ✅ Retry logic for embedding generation

**Diagnosis Steps (if you want to debug the vector index):**

1. **Check vector index exists and is READY:**
```bash
curl -X GET \
  "https://firestore.googleapis.com/v1/projects/YOUR_PROJECT/databases/YOUR_DB/collectionGroups/products/indexes" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

2. **Verify products have embeddings:**
```bash
PYTHONPATH=. python3 -c "
from google.cloud import firestore
db = firestore.Client(project='YOUR_PROJECT', database='YOUR_DB')
doc = db.collection('products').limit(1).stream()
for d in doc:
    data = d.to_dict()
    print(f'Has embedding: {\"embedding\" in data}')
    print(f'Embedding dim: {len(data.get(\"embedding\", []))}')
"
```

3. **Test vector search directly:**
```bash
PYTHONPATH=. python3 -c "
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from vertexai.language_models import TextEmbeddingModel
import vertexai

vertexai.init(project='YOUR_PROJECT', location='us-central1')
db = firestore.Client(project='YOUR_PROJECT', database='YOUR_DB')

# Generate test embedding
model = TextEmbeddingModel.from_pretrained('text-embedding-004')
embedding = model.get_embeddings(['laptop'])[0].values
query_vector = Vector(embedding)

# Try vector search
results = db.collection('products').find_nearest(
    vector_field='embedding',
    query_vector=query_vector,
    distance_measure=DistanceMeasure.COSINE,
    limit=5
).stream()

count = sum(1 for _ in results)
print(f'Found {count} results')
"
```

**Known Issue:**
The Firestore vector index may have been created with `__name__` field in addition to the `embedding` field, making it a composite index instead of a pure vector index. This can cause `find_nearest` to return 0 results.

**Workaround:**
The current implementation automatically uses fallback cosine similarity search, which works correctly. No action needed unless you have >1000 products.

**To Re-enable Vector Search Later:**
Once the vector index issue is resolved, modify `customer_support_agent/services/rag_search.py`:
```python
# Change this line:
print(f"[RAG] Using fallback cosine similarity search (vector index not working)")
return self._fallback_search(query_embedding, limit, query, max_price)

# Back to:
try:
    query_vector = Vector(query_embedding)
    results = self.db.collection("products").find_nearest(...)
    # ... rest of vector search code
except Exception as e:
    return self._fallback_search(query_embedding, limit, query, max_price)
```

### Quota Exceeded Errors

**Error:** `429 Quota exceeded for aiplatform.googleapis.com/online_prediction_requests_per_base_model`

**Solution:**
- Wait 1 minute and retry
- Request quota increase in GCP Console
- Add embeddings in smaller batches

For more issues, see [DEPLOYMENT_NOTES.md](../DEPLOYMENT_NOTES.md)

## See Also

- [DEPLOYMENT_NOTES.md](../DEPLOYMENT_NOTES.md) - Current deployment status & known issues
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [README.md](../README.md) - Main documentation
- `deployment/` directory - All deployment scripts
- `scripts/` directory - Helper scripts
