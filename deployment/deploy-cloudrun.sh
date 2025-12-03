#!/bin/bash

set -e

# Load configuration from .env file if it exists
if [ -f backend/.env ]; then
  echo "Loading configuration from backend/.env..."
  export $(cat backend/.env | grep -v '^#' | xargs)
fi

# Configuration - Use env vars or defaults
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-customer-support-ai}"
REPOSITORY="${REPOSITORY:-customer-support-repo}"
IMAGE_NAME="${IMAGE_NAME:-customer-support-app}"
AGENT_ENGINE_RESOURCE_NAME="${AGENT_ENGINE_RESOURCE_NAME}"

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
  echo "ERROR: GOOGLE_CLOUD_PROJECT not set. Please set it in backend/.env"
  exit 1
fi

if [ -z "$AGENT_ENGINE_RESOURCE_NAME" ]; then
  echo "ERROR: AGENT_ENGINE_RESOURCE_NAME not set. Please set it in backend/.env"
  exit 1
fi

echo "================================================"
echo "Deploying Customer Support AI to Cloud Run"
echo "================================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "Agent Engine: $AGENT_ENGINE_RESOURCE_NAME"
echo ""

# Step 1: Enable required APIs
echo "Step 1: Enabling required APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  --project=$PROJECT_ID

# Step 2: Create Artifact Registry repository (if it doesn't exist)
echo ""
echo "Step 2: Creating Artifact Registry repository..."
if ! gcloud artifacts repositories describe $REPOSITORY \
  --location=$REGION \
  --project=$PROJECT_ID &>/dev/null; then
  gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --description="Customer Support AI images" \
    --project=$PROJECT_ID
  echo "Repository created."
else
  echo "Repository already exists."
fi

# Step 3: Build and push the Docker image
echo ""
echo "Step 3: Building and pushing Docker image..."
IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME"

# Configure Docker to use gcloud credentials
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

# Build the image
docker build -t $IMAGE_URL:latest -f backend/Dockerfile .

# Push the image
docker push $IMAGE_URL:latest

# Step 4: Deploy to Cloud Run
echo ""
echo "Step 4: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE_URL:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,AGENT_ENGINE_RESOURCE_NAME=$AGENT_ENGINE_RESOURCE_NAME,FRONTEND_URL=https://$SERVICE_NAME-$REGION.run.app" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --max-instances=10 \
  --project=$PROJECT_ID

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format='value(status.url)')

echo ""
echo "================================================"
echo "Deployment Complete!"
echo "================================================"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test the deployment:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "Access the frontend:"
echo "  $SERVICE_URL"
echo "================================================"
