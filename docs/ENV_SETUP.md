# Environment Configuration Guide

This guide explains how to configure the customer support system using `.env` files.

## Quick Start

```bash
# 1. Copy example files
cp .env.example .env
cp backend/.env.example backend/.env

# 2. Edit .env files with your values
nano .env              # Edit root .env
nano backend/.env      # Edit backend .env
```

## .env File Locations

### Root `.env` (Required for deployment & agent code)

**Location:** `/customer-support-mas/.env`

**Used by:**
- `deployment/deploy.py` - Agent Engine deployment
- `customer_support_agent/` - Agent system
- `scripts/add_embeddings.py` - RAG setup
- `online_evaluation/` - Evaluation scripts

**Variables:**
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
GOOGLE_GENAI_USE_VERTEXAI=1
FIRESTORE_DATABASE=customer-support-db
```

### Backend `.env` (Required for FastAPI backend)

**Location:** `/customer-support-mas/backend/.env`

**Used by:**
- `backend/app/config.py` - Pydantic settings
- `backend/app/agent_client.py` - Agent Engine client

**Variables:**
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
FRONTEND_URL=http://localhost:3000
PORT=8000
```

### Frontend `.env` (Optional for React frontend)

**Location:** `/customer-support-mas/frontend/.env`

**Used by:**
- Vite build process
- React environment variables (must start with `VITE_`)

**Variables:**
```bash
VITE_API_URL=http://localhost:8000
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID | `my-project-123` |
| `GOOGLE_CLOUD_STORAGE_BUCKET` | GCS bucket for staging (with `gs://` prefix) | `gs://my-bucket-staging` |
| `AGENT_ENGINE_RESOURCE_NAME` | Deployed agent resource name | `projects/123/locations/us-central1/reasoningEngines/456` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` | `us-east1`, `europe-west1` |
| `FIRESTORE_DATABASE` | Firestore database name | `customer-support-db` | `(default)` |
| `GOOGLE_GENAI_USE_VERTEXAI` | Use Vertex AI instead of direct Gemini API | `1` | `0` or `1` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` | `https://app.example.com` |
| `PORT` | Backend port | `8000` | `8080`, `3000` |

## How It Works

### Root .env Loading

The root `.env` file is loaded by:

1. **deployment/deploy.py**
```python
from dotenv import load_dotenv
load_dotenv()
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
```

2. **customer_support_agent/database/client.py**
```python
from dotenv import load_dotenv
load_dotenv()
FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
```

### Backend .env Loading

The backend `.env` is loaded automatically by Pydantic:

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_cloud_project: str

    class Config:
        env_file = ".env"  # Automatically loads backend/.env
```

### Frontend .env Loading

Vite automatically loads `frontend/.env` and exposes variables prefixed with `VITE_`:

```typescript
// frontend/src/config.ts
const API_URL = import.meta.env.VITE_API_URL
```

## Setup Steps

### 1. Get Your GCP Project ID

```bash
# List your projects
gcloud projects list

# Set active project
gcloud config set project your-project-id
```

### 2. Create GCS Bucket

```bash
# Create bucket
gsutil mb -l us-central1 gs://your-bucket-staging

# Verify
gsutil ls
```

### 3. Deploy Agent Engine (to get resource name)

```bash
# Deploy first time
python deployment/deploy.py

# Copy the resource name from output
# Example: projects/123/locations/us-central1/reasoningEngines/456
```

### 4. Create .env Files

```bash
# Root .env
cat > .env << EOF
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-staging
AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
GOOGLE_GENAI_USE_VERTEXAI=1
FIRESTORE_DATABASE=customer-support-db
EOF

# Backend .env
cat > backend/.env << EOF
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_RESOURCE_NAME=projects/123/locations/us-central1/reasoningEngines/456
FRONTEND_URL=http://localhost:3000
PORT=8000
EOF
```

### 5. Verify Configuration

```bash
# Test deployment script reads .env
python deployment/deploy.py --action test_local

# Test backend reads .env
cd backend
python -c "from app.config import settings; print(settings.google_cloud_project)"
```

## Security Best Practices

### ✅ DO

- ✅ Use `.env` files for local development
- ✅ Keep `.env` in `.gitignore` (already configured)
- ✅ Use Cloud Secret Manager for production
- ✅ Share `.env.example` files (without sensitive values)
- ✅ Rotate credentials regularly

### ❌ DON'T

- ❌ Commit `.env` files to git
- ❌ Share `.env` files publicly
- ❌ Include credentials in `.env.example`
- ❌ Use production credentials in development

## Production Deployment

For production, use environment variables directly instead of `.env` files:

### Cloud Run

```bash
# Set environment variables in Cloud Run
gcloud run services update customer-support-backend \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=your-project-id" \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=projects/..." \
  --region=us-central1
```

### Vertex AI Agent Engine

Agent Engine automatically has access to:
- `GOOGLE_CLOUD_PROJECT` - Auto-detected from deployment
- `GOOGLE_CLOUD_LOCATION` - Auto-detected from deployment

## Troubleshooting

### Error: "GOOGLE_CLOUD_PROJECT not set"

**Solution:**
```bash
# Check if .env exists
ls -la .env

# Check if variable is set
cat .env | grep GOOGLE_CLOUD_PROJECT

# Manually export if needed
export GOOGLE_CLOUD_PROJECT=your-project-id
```

### Error: "Backend can't find .env"

**Solution:**
```bash
# Ensure backend/.env exists
ls -la backend/.env

# Verify it's in the correct location
cd backend
python -c "import os; print(os.path.exists('.env'))"
```

### Error: "Permission denied accessing GCS bucket"

**Solution:**
```bash
# Authenticate
gcloud auth application-default login

# Grant permissions
gsutil iam ch user:your-email@example.com:roles/storage.admin gs://your-bucket
```

## Example Workflows

### Development Workflow

```bash
# 1. Setup .env
cp .env.example .env
nano .env  # Edit with your values

# 2. Run locally
python deployment/deploy.py --action test_local

# 3. Deploy to Agent Engine
python deployment/deploy.py --action deploy

# 4. Run backend
cd backend
uvicorn app.main:app --reload
```

### CI/CD Workflow

```yaml
# .github/workflows/deploy.yml
- name: Deploy to Agent Engine
  env:
    GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT }}
    GOOGLE_CLOUD_STORAGE_BUCKET: ${{ secrets.GCS_BUCKET }}
  run: python deployment/deploy.py --action deploy
```

## See Also

- [DEPLOYMENT.md](./DEPLOYMENT.md) - Full deployment guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [README.md](../README.md) - Main documentation
