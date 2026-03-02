#!/usr/bin/env bash
# ==============================================================================
# One-time Cloud Build setup script
# Grants IAM roles, creates Artifact Registry repo, and sets up Secret Manager.
#
# Usage:
#   ./scripts/setup-cloud-build.sh <PROJECT_ID> <REGION> <STAGING_BUCKET_NAME>
#
# Example:
#   ./scripts/setup-cloud-build.sh my-gcp-project us-central1 my-adk-staging
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Owner or Editor role on the GCP project
# ==============================================================================

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <PROJECT_ID> <REGION> <STAGING_BUCKET_NAME>"
  exit 1
fi

PROJECT_ID="$1"
REGION="$2"
STAGING_BUCKET="$3"
AR_REPO="customer-support"

echo "=== Cloud Build Setup for project: ${PROJECT_ID} ==="

# Get project number
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo ""
echo "Cloud Build SA: ${CB_SA}"
echo "Compute SA: ${COMPUTE_SA}"
echo ""

# ==============================================================================
# 1. Grant IAM roles to Cloud Build service account
# ==============================================================================
echo "--- Granting IAM roles to Cloud Build SA ---"

declare -a ROLES=(
  "roles/datastore.user"           # Firestore access (tests + deploy)
  "roles/aiplatform.user"          # Vertex AI Gemini API (agent evals)
  "roles/aiplatform.admin"         # Agent Engine deployment
  "roles/artifactregistry.writer"  # Push Docker images
  "roles/run.admin"                # Cloud Run deployment
  "roles/storage.objectAdmin"      # Staging bucket for Agent Engine
  "roles/secretmanager.secretAccessor"  # Read secrets
)

for ROLE in "${ROLES[@]}"; do
  echo "  Granting ${ROLE}..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CB_SA}" \
    --role="${ROLE}" \
    --quiet 2>/dev/null
done

# Cloud Build needs to act as the Cloud Run service account
echo "  Granting serviceAccountUser on compute SA..."
gcloud iam service-accounts add-iam-policy-binding "${COMPUTE_SA}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet 2>/dev/null

echo "  IAM roles granted."
echo ""

# ==============================================================================
# 2. Create Artifact Registry repository
# ==============================================================================
echo "--- Creating Artifact Registry repo: ${AR_REPO} ---"

if gcloud artifacts repositories describe "${AR_REPO}" \
    --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "  Repository already exists, skipping."
else
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --description="Customer support app Docker images"
  echo "  Repository created."
fi
echo ""

# ==============================================================================
# 3. Create Secret Manager secrets
# ==============================================================================
echo "--- Setting up Secret Manager ---"

if gcloud secrets describe staging-bucket --project="${PROJECT_ID}" &>/dev/null; then
  echo "  Secret 'staging-bucket' already exists, updating..."
  echo -n "${STAGING_BUCKET}" | gcloud secrets versions add staging-bucket \
    --data-file=- --project="${PROJECT_ID}"
else
  echo "  Creating secret 'staging-bucket'..."
  echo -n "${STAGING_BUCKET}" | gcloud secrets create staging-bucket \
    --data-file=- --project="${PROJECT_ID}" \
    --replication-policy="automatic"
fi
echo ""

# ==============================================================================
# 4. Enable required APIs
# ==============================================================================
echo "--- Enabling required APIs ---"

declare -a APIS=(
  "cloudbuild.googleapis.com"
  "artifactregistry.googleapis.com"
  "run.googleapis.com"
  "secretmanager.googleapis.com"
  "aiplatform.googleapis.com"
  "firestore.googleapis.com"
  "cloudscheduler.googleapis.com"
)

for API in "${APIS[@]}"; do
  echo "  Enabling ${API}..."
  gcloud services enable "${API}" --project="${PROJECT_ID}" --quiet 2>/dev/null
done
echo ""

# ==============================================================================
# 5. Print next steps
# ==============================================================================
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo ""
echo "1. Connect your GitHub repo to Cloud Build:"
echo "   Cloud Console → Cloud Build → Triggers → Connect Repository"
echo "   (Select GitHub, authorize, choose your repo)"
echo ""
echo "2. Create triggers (update GITHUB_OWNER and REPO_NAME):"
echo ""
echo "   # PR trigger (fast eval)"
echo "   gcloud builds triggers create github \\"
echo "     --name='ci-pull-request' \\"
echo "     --repo-name='customer-support-mas-kaggle' \\"
echo "     --repo-owner='YOUR_GITHUB_OWNER' \\"
echo "     --pull-request-pattern='^main$' \\"
echo "     --build-config='cloudbuild.yaml' \\"
echo "     --substitutions='_EVAL_PROFILE=fast,_GOOGLE_CLOUD_LOCATION=${REGION}' \\"
echo "     --project='${PROJECT_ID}'"
echo ""
echo "   # Push to main (standard eval + deploy)"
echo "   gcloud builds triggers create github \\"
echo "     --name='ci-cd-push-main' \\"
echo "     --repo-name='customer-support-mas-kaggle' \\"
echo "     --repo-owner='YOUR_GITHUB_OWNER' \\"
echo "     --branch-pattern='^main$' \\"
echo "     --build-config='cloudbuild-deploy.yaml' \\"
echo "     --substitutions='_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=${REGION}' \\"
echo "     --project='${PROJECT_ID}'"
echo ""
echo "   # Push to develop (standard eval, CI only)"
echo "   gcloud builds triggers create github \\"
echo "     --name='ci-push-develop' \\"
echo "     --repo-name='customer-support-mas-kaggle' \\"
echo "     --repo-owner='YOUR_GITHUB_OWNER' \\"
echo "     --branch-pattern='^develop$' \\"
echo "     --build-config='cloudbuild.yaml' \\"
echo "     --substitutions='_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=${REGION}' \\"
echo "     --project='${PROJECT_ID}'"
echo ""
echo "   # Manual trigger (full eval)"
echo "   gcloud builds triggers create manual \\"
echo "     --name='ci-manual' \\"
echo "     --repo-name='customer-support-mas-kaggle' \\"
echo "     --repo-owner='YOUR_GITHUB_OWNER' \\"
echo "     --branch='main' \\"
echo "     --build-config='cloudbuild-nightly.yaml' \\"
echo "     --substitutions='_EVAL_PROFILE=full,_GOOGLE_CLOUD_LOCATION=${REGION}' \\"
echo "     --project='${PROJECT_ID}'"
echo ""
echo "3. Set up nightly Cloud Scheduler job:"
echo ""
echo "   # First, get the trigger ID for ci-manual"
echo "   TRIGGER_ID=\$(gcloud builds triggers list --project='${PROJECT_ID}' \\"
echo "     --filter='name=ci-manual' --format='value(id)')"
echo ""
echo "   gcloud scheduler jobs create http nightly-full-eval \\"
echo "     --schedule='0 0 * * *' \\"
echo "     --uri='https://cloudbuild.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/triggers/'\$TRIGGER_ID':run' \\"
echo "     --http-method=POST \\"
echo "     --oauth-service-account-email='${COMPUTE_SA}' \\"
echo "     --message-body='{\"branchName\": \"main\"}' \\"
echo "     --time-zone='UTC' \\"
echo "     --project='${PROJECT_ID}'"
echo ""
echo "4. Once Cloud Build is verified, disable GitHub Actions:"
echo "   Rename .github/workflows/ci.yml → ci.yml.disabled"
