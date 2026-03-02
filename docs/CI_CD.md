# CI/CD with Google Cloud Build

The project uses **Google Cloud Build** for continuous integration and deployment. Three pipeline configs handle different scenarios, with eval profile selection per trigger type.

## Pipeline Overview

```
cloudbuild/pr-checks.yaml      PR checks (pull_request to main)
cloudbuild/cloudbuild.yaml     CI only (develop push)
cloudbuild/cloudbuild-deploy.yaml     CI + CD (main push)
cloudbuild/cloudbuild-nightly.yaml    Full eval + optional post-deploy eval (scheduled/manual)
```

### Job Dependency Graph

```
install-deps
├── lint ─────────────────────────┐
└── tool-tests                    │
    └── unit-tests                │
        └── integration-tests     │
            └── [CD steps] ◄─────┘  (cloudbuild-deploy.yaml only)
                ├── docker-build
                ├── docker-push
                ├── deploy-cloud-run
                └── deploy-agent-engine (optional)
```

`lint` and `tool-tests` run in parallel after `install-deps`. CD steps only start after **all** CI steps pass.

## Trigger Configuration

| Trigger | Event | Config | `_EVAL_PROFILE` |
|---------|-------|--------|-----------------|
| `ci-pull-request` | PR to `main` | `cloudbuild/pr-checks.yaml` | `fast` |
| `ci-push-develop` | Push to `develop` | `cloudbuild/cloudbuild.yaml` | `standard` |
| `ci-cd-push-main` | Push to `main` | `cloudbuild/cloudbuild-deploy.yaml` | `standard` |
| `ci-manual` | Manual dispatch | `cloudbuild/cloudbuild-nightly.yaml` | `full` |
| Cloud Scheduler | Nightly (midnight UTC) | `cloudbuild/cloudbuild-nightly.yaml` | `full` |

### Eval Profile Details

| Profile | Unit Metrics | Integration Metrics | Cost |
|---------|-------------|-------------------|------|
| `fast` | Rouge-1 response match | Rouge-1 response match | Free |
| `standard` | + tool trajectory exact match | + rubric-based LLM judge | Low |
| `full` | + LLM-as-judge response quality | + LLM-as-judge response quality | Higher |

Profile configs: `tests/eval_configs/{unit,integration}/{fast,standard,full}.json`

## CI Steps

### 1. install-deps
Installs Python dependencies into `/workspace/.local` (shared across all steps via Cloud Build's `/workspace` volume).

### 2. lint
Runs `ruff check customer_support_agent/ --ignore=E501`.

`pr-checks.yaml` also runs `ruff format customer_support_agent/ --check` to catch formatting issues (mirrors `.pre-commit-config.yaml`).

### 3. tool-tests
Pure Python tests with mocked Firestore — no LLM calls, no cost.
```
pytest tests/unit/test_tools.py tests/unit/test_mock_rag.py tests/unit/test_refund_standalone.py
```

### 4. unit-tests
Agent evaluation via ADK `AgentEvaluator` — calls Vertex AI Gemini.
```
pytest tests/unit/test_agent_eval_ci.py
```

### 5. integration-tests
Multi-agent orchestration evaluation through the root agent.
```
pytest tests/integration/test_integration_eval_ci.py
```

## CD Steps (cloudbuild-deploy.yaml only)

### 6. docker-build
Multi-stage Docker build (`backend/Dockerfile`): React frontend (Node 20) + FastAPI backend (Python 3.11). Tagged with `$COMMIT_SHA` and `latest`.

### 7. docker-push
Pushes to Artifact Registry at `$_REGION-docker.pkg.dev/$PROJECT_ID/customer-support/customer-support-app`.

### 8. deploy-cloud-run
Deploys the image to Cloud Run with env vars for project, Firestore database, and region.

### 9. deploy-agent-engine (optional)
Runs `deployment/deploy.py` when `_DEPLOY_AGENT_ENGINE=true`. Reads the staging bucket name from Secret Manager.

## Nightly Pipeline (cloudbuild-nightly.yaml)

Runs all CI steps with `_EVAL_PROFILE=full` (all metrics including LLM-as-judge). Optionally runs post-deploy evaluation against a deployed Agent Engine:

```bash
# Enable post-deploy eval by setting substitutions:
# _RUN_POST_DEPLOY_EVAL=true
# _AGENT_ENGINE_ID=<your-engine-id>
```

## Setup

### Quick Start (Terraform — recommended)

All infrastructure (APIs, IAM, Firestore, GCS, Artifact Registry, Secret Manager, Cloud Build triggers, Cloud Scheduler) is managed by Terraform in the `terraform/` directory.

```bash
# 1. Copy and fill in your values
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
$EDITOR terraform/terraform.tfvars

# 2. Bootstrap infrastructure
make infra-up    # terraform init + apply

# 3. Connect GitHub repo (one-time, browser OAuth — cannot be automated)
#    Cloud Console → Cloud Build → Triggers → Connect Repository → GitHub

# 4. Seed Firestore and deploy
make seed-db
make deploy-agent-engine
make deploy-cloud-run
```

See [../terraform/](../terraform/) for full Terraform configuration.

### Alternative: Shell Scripts

```bash
./scripts/setup-cloud-build.sh YOUR_PROJECT_ID us-central1 YOUR_STAGING_BUCKET
```

This script:
1. Grants IAM roles to the Cloud Build service account
2. Creates the Artifact Registry repository
3. Creates Secret Manager secrets
4. Enables required APIs
5. Prints trigger creation commands

### IAM Roles Required

The Cloud Build service account (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) needs:

| Role | Purpose |
|------|---------|
| `roles/datastore.user` | Firestore access |
| `roles/aiplatform.user` | Vertex AI Gemini API |
| `roles/aiplatform.admin` | Agent Engine deployment |
| `roles/artifactregistry.writer` | Push Docker images |
| `roles/run.admin` | Cloud Run deployment |
| `roles/iam.serviceAccountUser` | Act as Cloud Run service account |
| `roles/storage.objectAdmin` | Staging bucket access |
| `roles/secretmanager.secretAccessor` | Read secrets |

No service account key file is needed — Cloud Build runs natively on GCP with IAM.

### Creating Triggers

After connecting your GitHub repo in Cloud Console (Cloud Build > Triggers > Connect Repository):

```bash
# PR trigger (fast checks + ruff format)
gcloud builds triggers create github \
  --name="ci-pull-request" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --pull-request-pattern="^main$" \
  --build-config="cloudbuild/pr-checks.yaml" \
  --substitutions="_GOOGLE_CLOUD_LOCATION=us-central1"

# Push to main (CI + deploy)
gcloud builds triggers create github \
  --name="ci-cd-push-main" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild/cloudbuild-deploy.yaml" \
  --substitutions="_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=us-central1"

# Push to develop (CI only)
gcloud builds triggers create github \
  --name="ci-push-develop" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^develop$" \
  --build-config="cloudbuild/cloudbuild.yaml" \
  --substitutions="_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=us-central1"

# Manual trigger (full eval)
gcloud builds triggers create manual \
  --name="ci-manual" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch="main" \
  --build-config="cloudbuild/cloudbuild-nightly.yaml" \
  --substitutions="_EVAL_PROFILE=full,_GOOGLE_CLOUD_LOCATION=us-central1"
```

### Nightly Schedule

Cloud Build doesn't have native cron triggers. Use Cloud Scheduler:

```bash
TRIGGER_ID=$(gcloud builds triggers list \
  --filter="name=ci-manual" --format="value(id)")

gcloud scheduler jobs create http nightly-full-eval \
  --schedule="0 0 * * *" \
  --uri="https://cloudbuild.googleapis.com/v1/projects/$PROJECT_ID/locations/global/triggers/${TRIGGER_ID}:run" \
  --http-method=POST \
  --oauth-service-account-email="PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --message-body='{"branchName": "main"}' \
  --time-zone="UTC"
```

## Substitution Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `_EVAL_PROFILE` | `standard` | Eval metric profile (`fast`, `standard`, `full`) |
| `_PYTHON_VERSION` | `3.11` | Python version for test containers |
| `_FIRESTORE_DATABASE` | `customer-support-db` | Firestore database name |
| `_GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region |
| `_REGION` | `us-central1` | Cloud Run / Artifact Registry region |
| `_SERVICE_NAME` | `customer-support-app` | Cloud Run service name |
| `_AR_REPO` | `customer-support` | Artifact Registry repository |
| `_DEPLOY_AGENT_ENGINE` | `false` | Enable Agent Engine deployment |
| `_RUN_POST_DEPLOY_EVAL` | `false` | Enable post-deploy eval (nightly only) |
| `_AGENT_ENGINE_ID` | `` | Agent Engine ID for post-deploy eval |

`$PROJECT_ID` and `$COMMIT_SHA` are built-in Cloud Build substitutions.

## Timeouts

| Pipeline | Timeout | Rationale |
|----------|---------|-----------|
| `pr-checks.yaml` | 20 min | Fast profile only, quick feedback |
| `cloudbuild.yaml` | 30 min | CI tests only |
| `cloudbuild-deploy.yaml` | 40 min | CI + Docker build + Cloud Run deploy |
| `cloudbuild-nightly.yaml` | 60 min | Full eval with LLM judges is slow |

## Local Development with Make

The `Makefile` at the project root mirrors the CI steps so developers can run the same checks locally:

```bash
make install          # pip install + pre-commit install
make lint             # ruff check + ruff format --check (same as pr-checks.yaml)
make format           # auto-fix formatting
make test-tools       # pure Python tests, no LLM
make test-unit        # unit agent eval (EVAL_PROFILE=fast by default)
make test-integration # integration eval (EVAL_PROFILE=fast by default)
make test             # run all three in sequence

# Override eval profile
make test-unit EVAL_PROFILE=standard
make test-unit EVAL_PROFILE=full

# Post-deploy eval
make eval-post-deploy AGENT_ENGINE_ID=<id> EVAL_PROFILE=standard

# Show all targets
make help
```
