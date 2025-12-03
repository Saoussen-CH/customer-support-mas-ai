#!/bin/bash
# ============================================================================
# GCP Prerequisites Setup Script
# ============================================================================
# This script enables required APIs and configures IAM permissions
# for the Customer Support Multi-Agent System
#
# Usage:
#   ./scripts/setup_gcp.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project created
#   - Billing enabled on project
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Configuration
# ============================================================================

# Load from .env if exists
if [ -f .env ]; then
    echo -e "${BLUE}Loading configuration from .env...${NC}"
    export $(grep -v '^#' .env | xargs)
fi

# Get project ID
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project ID found${NC}"
    echo "Please set GOOGLE_CLOUD_PROJECT in .env or run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

LOCATION=${GOOGLE_CLOUD_LOCATION:-us-central1}
BUCKET_NAME=${GOOGLE_CLOUD_STORAGE_BUCKET}

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  GCP Prerequisites Setup for Multi-Agent System           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Project ID:${NC} $PROJECT_ID"
echo -e "${BLUE}Location:${NC} $LOCATION"
echo ""

# ============================================================================
# 1. Enable Required APIs
# ============================================================================

echo -e "${YELLOW}[1/5] Enabling Required APIs...${NC}"
echo ""

APIS=(
    "aiplatform.googleapis.com"           # Vertex AI (Agent Engine, Gemini)
    "firestore.googleapis.com"            # Firestore database
    "run.googleapis.com"                  # Cloud Run
    "cloudbuild.googleapis.com"           # Cloud Build (for deployment)
    "storage.googleapis.com"              # Cloud Storage
    "artifactregistry.googleapis.com"     # Artifact Registry (container images)
    "cloudresourcemanager.googleapis.com" # Resource Manager
    "iam.googleapis.com"                  # IAM
    "logging.googleapis.com"              # Cloud Logging
    "monitoring.googleapis.com"           # Cloud Monitoring
)

for api in "${APIS[@]}"; do
    echo -e "  Enabling ${BLUE}$api${NC}..."
    if gcloud services enable "$api" --project="$PROJECT_ID" 2>/dev/null; then
        echo -e "    ${GREEN}✓${NC} Enabled"
    else
        echo -e "    ${YELLOW}⚠${NC} Already enabled or error"
    fi
done

echo ""

# ============================================================================
# 2. Create Service Account
# ============================================================================

echo -e "${YELLOW}[2/5] Creating Service Account...${NC}"
echo ""

SERVICE_ACCOUNT_NAME="customer-support-agent"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} Service account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    echo -e "  Creating service account: ${BLUE}$SERVICE_ACCOUNT_EMAIL${NC}"
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="Customer Support Agent" \
        --description="Service account for multi-agent customer support system" \
        --project="$PROJECT_ID"
    echo -e "  ${GREEN}✓${NC} Service account created"
fi

echo ""

# ============================================================================
# 3. Grant IAM Roles
# ============================================================================

echo -e "${YELLOW}[3/5] Granting IAM Roles to Service Account...${NC}"
echo ""

ROLES=(
    "roles/aiplatform.user"              # Vertex AI access
    "roles/aiplatform.serviceAgent"      # Vertex AI service operations
    "roles/datastore.user"               # Firestore read/write
    "roles/storage.objectAdmin"          # GCS bucket access
    "roles/logging.logWriter"            # Write logs
    "roles/run.invoker"                  # Invoke Cloud Run services
)

for role in "${ROLES[@]}"; do
    echo -e "  Granting ${BLUE}$role${NC}..."
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet &>/dev/null; then
        echo -e "    ${GREEN}✓${NC} Granted"
    else
        echo -e "    ${YELLOW}⚠${NC} Already granted or error"
    fi
done

echo ""

# ============================================================================
# 4. Grant Permissions to Current User
# ============================================================================

echo -e "${YELLOW}[4/5] Granting Permissions to Current User...${NC}"
echo ""

CURRENT_USER=$(gcloud config get-value account 2>/dev/null)

if [ -z "$CURRENT_USER" ]; then
    echo -e "  ${RED}✗${NC} No authenticated user found. Run: gcloud auth login"
else
    echo -e "  Current user: ${BLUE}$CURRENT_USER${NC}"

    USER_ROLES=(
        "roles/aiplatform.admin"            # Deploy to Agent Engine
        "roles/datastore.owner"             # Firestore admin
        "roles/storage.admin"               # GCS admin
        "roles/run.admin"                   # Cloud Run admin
        "roles/iam.serviceAccountUser"      # Use service accounts
    )

    for role in "${USER_ROLES[@]}"; do
        echo -e "  Granting ${BLUE}$role${NC}..."
        if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="user:$CURRENT_USER" \
            --role="$role" \
            --condition=None \
            --quiet &>/dev/null; then
            echo -e "    ${GREEN}✓${NC} Granted"
        else
            echo -e "    ${YELLOW}⚠${NC} Already granted or error"
        fi
    done
fi

echo ""

# ============================================================================
# 5. Create GCS Bucket (if needed)
# ============================================================================

echo -e "${YELLOW}[5/5] Setting up GCS Bucket...${NC}"
echo ""

if [ -z "$BUCKET_NAME" ]; then
    echo -e "  ${YELLOW}⚠${NC} No GOOGLE_CLOUD_STORAGE_BUCKET set in .env"
    BUCKET_NAME="${PROJECT_ID}-staging"
    echo -e "  Using default: ${BLUE}$BUCKET_NAME${NC}"
fi

# Remove gs:// prefix if present
BUCKET_NAME=${BUCKET_NAME#gs://}

if gsutil ls -b "gs://$BUCKET_NAME" &>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} Bucket already exists: gs://$BUCKET_NAME"
else
    echo -e "  Creating bucket: ${BLUE}gs://$BUCKET_NAME${NC}"
    gsutil mb -p "$PROJECT_ID" -l "$LOCATION" "gs://$BUCKET_NAME"
    echo -e "  ${GREEN}✓${NC} Bucket created"
fi

# Grant service account access to bucket
echo -e "  Granting bucket access to service account..."
gsutil iam ch "serviceAccount:$SERVICE_ACCOUNT_EMAIL:roles/storage.objectAdmin" "gs://$BUCKET_NAME" 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Bucket permissions configured"

echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete!                                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  Project ID:      ${GREEN}$PROJECT_ID${NC}"
echo -e "  Location:        ${GREEN}$LOCATION${NC}"
echo -e "  Service Account: ${GREEN}$SERVICE_ACCOUNT_EMAIL${NC}"
echo -e "  Storage Bucket:  ${GREEN}gs://$BUCKET_NAME${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Update .env file with bucket name:"
echo -e "     ${YELLOW}GOOGLE_CLOUD_STORAGE_BUCKET=$BUCKET_NAME${NC}"
echo ""
echo -e "  2. Create Firestore database:"
echo -e "     ${YELLOW}./scripts/setup_firestore.sh${NC}"
echo ""
echo -e "  3. Deploy to Agent Engine:"
echo -e "     ${YELLOW}python deployment/deploy.py${NC}"
echo ""
echo -e "${GREEN}✓ All prerequisites configured successfully!${NC}"
echo ""
