# CI/CD with Google Cloud Build

The project uses **Google Cloud Build** for continuous integration and deployment. Three pipeline configs handle different scenarios, with eval profile selection per trigger type.

## Pipeline Overview

```
cloudbuild/pr-checks.yaml          PR checks (pull_request to main)
cloudbuild/cloudbuild.yaml         CI only (develop push)
cloudbuild/cloudbuild-deploy.yaml  CI + CD (main push) — two triggers point here
cloudbuild/cloudbuild-nightly.yaml Full eval + optional post-deploy eval (scheduled/manual)
```

### Job Dependency Graph

```
install-deps
├── lint ─────────────────────────┐
└── tool-tests                    │
    └── unit-tests                │
        └── integration-tests     │
            └── docker-build ◄────┘  (waits for integration-tests + lint)
                └── docker-push
                    └── deploy-agent-engine  ← agent first (skipped if _DEPLOY_AGENT_ENGINE=false)
                        └── deploy-cloud-run ← cloud run second (always runs)
```

`lint` and `tool-tests` run in parallel after `install-deps`. CD steps only start after **all** CI steps pass. `deploy-agent-engine` must complete before `deploy-cloud-run` so Cloud Run always talks to the already-updated agent.

## Trigger Configuration

Three triggers, one per branch tier:

| Trigger | Event | Config | `_EVAL_PROFILE` | `_DEPLOY_AGENT_ENGINE` |
|---------|-------|--------|-----------------|------------------------|
| `ci-branch-push` | Push to any feature branch (not `develop`, not `main`) | `cloudbuild/pr-checks.yaml` | `fast` | — |
| `ci-push-develop` | Push to `develop` | `cloudbuild/cloudbuild.yaml` | `standard` | — |
| `ci-cd-push-main-agent` | Push to `main` touching `customer_support_agent/**` | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | `true` |
| `ci-cd-push-main` | Push to `main` not touching `customer_support_agent/**` | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | `false` |
| `ci-manual` | Manual dispatch | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |
| Cloud Scheduler | Nightly (midnight UTC) | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |

### Two triggers for `cloudbuild-deploy.yaml`

`cloudbuild-deploy.yaml` is pointed to by **two** triggers that both fire on push to `main`, but with different file filters:

- **`ci-cd-push-main-agent`** — `includedFiles: ["customer_support_agent/**"]`, sets `_DEPLOY_AGENT_ENGINE=true`: redeploys Agent Engine + Cloud Run
- **`ci-cd-push-main`** — `ignoredFiles: ["customer_support_agent/**"]`, sets `_DEPLOY_AGENT_ENGINE=false`: deploys Cloud Run only

This means pushing changes to tests, frontend, backend, or infra does not trigger a (slow, expensive) Agent Engine redeploy. Only changes to `customer_support_agent/` do.

### Skipping builds entirely with `[skip ci]`

For commits that change nothing deployable — docs, Terraform, CI config itself — you can prevent all triggers from running by including `[skip ci]` or `[ci skip]` anywhere in the commit message:

```bash
git commit -m "docs: update CI_CD.md [skip ci]"
git commit -m "[skip ci] fix typo in README"
```

Cloud Build checks the commit message of the HEAD commit on the pushed branch. If it contains `[skip ci]` or `[ci skip]`, **all** triggered builds for that push are skipped.

**When to use each mechanism:**

| Scenario | Mechanism |
|----------|-----------|
| Working on a feature branch | Push normally → `ci-branch-push` fires (fast checks) |
| Merging to `develop` | Push normally → `ci-push-develop` fires (full CI) |
| Agent logic changed, merging to `main` | Push normally → `ci-cd-push-main-agent` fires (`_DEPLOY_AGENT_ENGINE=true`) |
| Non-agent code, merging to `main` | Push normally → `ci-cd-push-main` fires (`_DEPLOY_AGENT_ENGINE=false`) |
| Docs / Terraform / CI config only | Add `[skip ci]` to commit message → no build runs |

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

### 8. deploy-agent-engine (conditional)
Runs `deployment/deploy.py --action deploy` when `_DEPLOY_AGENT_ENGINE=true`. Receives the GCS staging bucket via the `_STAGING_BUCKET` substitution variable. Uses update-or-create logic: if an Agent Engine with `AGENT_ENGINE_DISPLAY_NAME` already exists it is updated in place (same resource name, Cloud Run needs no change); otherwise a new engine is created and its resource name is written to `/workspace/agent_engine_resource_name.txt` so the next step can read it.

### 9. deploy-cloud-run
Deploys the image to Cloud Run. Reads `AGENT_ENGINE_RESOURCE_NAME` from `/workspace/agent_engine_resource_name.txt` (written by step 8 on first create) or falls back to the `_AGENT_ENGINE_RESOURCE_NAME` substitution variable (used on updates where the resource name is unchanged). Sets `ENVIRONMENT=production` to enable structured JSON logging.

## Nightly Pipeline (cloudbuild-nightly.yaml)

Runs all CI steps with `_EVAL_PROFILE=full` (all metrics including LLM-as-judge). Optionally runs post-deploy evaluation against a deployed Agent Engine:

```bash
# Enable post-deploy eval by setting substitutions:
# _RUN_POST_DEPLOY_EVAL=true
# _AGENT_ENGINE_ID=<your-engine-id>
```

## Setup

### Quick Start (Terraform — recommended)

All infrastructure (APIs, IAM, Firestore, GCS, Artifact Registry, Cloud Build triggers, Cloud Scheduler) is managed by Terraform in the `terraform/` directory.

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
3. Enables required APIs
4. Prints trigger creation commands

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

No service account key file is needed — Cloud Build runs natively on GCP with IAM.

### Creating Triggers

After connecting your GitHub repo in Cloud Console (Cloud Build > Triggers > Connect Repository):

```bash
# Feature branch push — fast checks (lint + tool tests + fast eval)
gcloud builds triggers create github \
  --name="ci-branch-push" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^(?!main$|develop$).*" \
  --build-config="cloudbuild/pr-checks.yaml" \
  --substitutions="_GOOGLE_CLOUD_LOCATION=us-central1"

# Push to develop — full CI (standard eval, no deploy)
gcloud builds triggers create github \
  --name="ci-push-develop" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^develop$" \
  --build-config="cloudbuild/cloudbuild.yaml" \
  --substitutions="_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=us-central1"

# Push to main — agent code changed: redeploy Agent Engine + Cloud Run
gcloud builds triggers create github \
  --name="ci-cd-push-main-agent" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^main$" \
  --included-files="customer_support_agent/**" \
  --build-config="cloudbuild/cloudbuild-deploy.yaml" \
  --substitutions="_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=us-central1,_DEPLOY_AGENT_ENGINE=true,_STAGING_BUCKET=gs://YOUR_STAGING_BUCKET"

# Push to main — everything else: Cloud Run only (no Agent Engine redeploy)
gcloud builds triggers create github \
  --name="ci-cd-push-main" \
  --repo-name="customer-support-mas-kaggle" \
  --repo-owner="YOUR_GITHUB_OWNER" \
  --branch-pattern="^main$" \
  --ignored-files="customer_support_agent/**" \
  --build-config="cloudbuild/cloudbuild-deploy.yaml" \
  --substitutions="_EVAL_PROFILE=standard,_GOOGLE_CLOUD_LOCATION=us-central1,_DEPLOY_AGENT_ENGINE=false,_STAGING_BUCKET=gs://YOUR_STAGING_BUCKET"

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
| `_DEPLOY_AGENT_ENGINE` | `false` | Redeploy Agent Engine (set `true` by agent-code trigger, `false` by everything-else trigger) |
| `_STAGING_BUCKET` | `` | GCS staging bucket for Agent Engine deployment (e.g. `gs://my-bucket`) |
| `_AGENT_ENGINE_RESOURCE_NAME` | `` | Full resource name of the Agent Engine for Cloud Run (e.g. `projects/P/locations/L/reasoningEngines/ID`) |
| `_MODEL_ARMOR_ENABLED` | `false` | Enable Model Armor prompt filtering |
| `_MODEL_ARMOR_TEMPLATE_ID` | `` | Model Armor template ID (if enabled) |
| `_RUN_POST_DEPLOY_EVAL` | `false` | Enable post-deploy eval (nightly only) |
| `_AGENT_ENGINE_ID` | `` | Agent Engine ID for post-deploy eval |

`$PROJECT_ID` and `$COMMIT_SHA` are built-in Cloud Build substitutions.

## Timeouts

| Pipeline | Timeout | Rationale |
|----------|---------|-----------|
| `pr-checks.yaml` | 20 min | Fast profile only, quick feedback |
| `cloudbuild.yaml` | 60 min | Standard eval (integration tests ~36 min) |
| `cloudbuild-deploy.yaml` | 60 min | CI + Docker build + Agent Engine + Cloud Run |
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

# Submit the full CI+CD pipeline to Cloud Build (mirrors what the main trigger does)
make submit-build                          # Cloud Run only (_DEPLOY_AGENT_ENGINE=false)
make submit-build DEPLOY_AGENT_ENGINE=true # + Agent Engine redeploy
make submit-build EVAL_PROFILE=fast        # faster feedback (skip LLM-heavy evals)

# Show all targets
make help
```
