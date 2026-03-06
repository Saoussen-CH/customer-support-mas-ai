# CI/CD with Google Cloud Build

The project uses **Google Cloud Build** for continuous integration and deployment. Four pipeline configs handle different scenarios, with eval profile selection per trigger type.

## Pipeline Overview

```
cloudbuild/pr-checks.yaml          PR checks (push to feature branches)
cloudbuild/cloudbuild.yaml         CI only (develop push)
cloudbuild/cloudbuild-deploy.yaml  CI + CD (main push) — one trigger, auto-detects agent changes
cloudbuild/cloudbuild-nightly.yaml Full eval + optional post-deploy eval (scheduled/manual)
```

### Job Dependency Graph

```
detect-agent-changes
└── install-deps
    ├── lint ─────────────────────────┐
    └── tool-tests                    │
        └── unit-tests                │
            └── integration-tests     │
                └── docker-build ◄────┘  (waits for integration-tests + lint)
                    └── docker-push
                        └── deploy-agent-engine  ← agent first (skipped if no agent changes)
                            └── deploy-cloud-run ← cloud run second (always runs)
```

`lint` and `tool-tests` run in parallel after `install-deps`. CD steps only start after **all** CI steps pass. `deploy-agent-engine` must complete before `deploy-cloud-run` so Cloud Run always talks to the already-updated agent.

## Trigger Configuration

Four triggers across three branch tiers:

| Trigger | Event | Config | `_EVAL_PROFILE` | Agent Engine deploy |
|---------|-------|--------|-----------------|---------------------|
| `ci-branch-push` | Push to any branch except `main` | `cloudbuild/pr-checks.yaml` | `fast` | — |
| `ci-push-develop` | Push to `develop` | `cloudbuild/cloudbuild.yaml` | `standard` | — |
| `ci-cd-push-main` | Push to `main` (all files) | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | auto-detected |
| `ci-manual` | Manual dispatch | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |
| Cloud Scheduler | Nightly (midnight UTC) | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |

### Auto-detection of agent changes

`cloudbuild-deploy.yaml` has a `detect-agent-changes` step that runs first on every push to `main`:

```bash
git diff --name-only HEAD~1 HEAD -- customer_support_agent/
```

- If `customer_support_agent/` files changed → writes `true` → Agent Engine is redeployed
- Otherwise → writes `false` → only Cloud Run is deployed

`_DEPLOY_AGENT_ENGINE=true` can still be set explicitly on the trigger (or via `make submit-build DEPLOY_AGENT_ENGINE=true`) to force an Agent Engine deploy regardless of which files changed.

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
| Agent logic changed, merging to `main` | Push normally → `ci-cd-push-main` fires, auto-detects agent change → deploys Agent Engine + Cloud Run |
| Non-agent code, merging to `main` | Push normally → `ci-cd-push-main` fires, no agent change detected → deploys Cloud Run only |
| Mixed commit (agent + backend), merging to `main` | Push normally → `ci-cd-push-main` fires once, detects agent change → full deploy |
| Docs / Terraform / CI config only | Add `[skip ci]` to commit message → no build runs |

### Eval Profile Details

| Profile | Unit Metrics | Integration Metrics | Cost |
|---------|-------------|-------------------|------|
| `fast` | Rouge-1 response match | Rouge-1 response match | Free |
| `standard` | + tool name F1 (custom metric) | + rubric-based LLM judge | Low |
| `full` | + LLM-as-judge response quality | + LLM-as-judge response quality | Higher |

Profile configs: `tests/eval_configs/{unit,integration}/{fast,standard,full}.json`

## CI Steps

### 1. install-deps
Installs Python dependencies via `uv sync --frozen` into `/workspace/.venv` (shared across all steps via Cloud Build's `/workspace` volume). Each subsequent step activates the venv with `export PATH="/workspace/.venv/bin:$PATH"`.

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

Runs all CI steps with `_EVAL_PROFILE=full` (all metrics including LLM-as-judge). Optionally runs post-deploy evaluation against a deployed Agent Engine.

```bash
# Full eval only (default — post-deploy eval skipped)
gcloud builds triggers run ci-manual \
  --project=YOUR_PROJECT_ID --region=us-central1 --branch=main

# Full eval + post-deploy eval against a live Agent Engine
# _STAGING_BUCKET is required when _RUN_POST_DEPLOY_EVAL=true:
#   - eval HTML report is uploaded to gs://BUCKET/eval-reports/eval-TIMESTAMP.html
#   - the GCS URI is recorded as a param in the Vertex AI Experiments run
gcloud builds triggers run ci-manual \
  --project=YOUR_PROJECT_ID --region=us-central1 --branch=main \
  --substitutions="_RUN_POST_DEPLOY_EVAL=true,_AGENT_ENGINE_ID=YOUR_ENGINE_ID,_STAGING_BUCKET=gs://YOUR_BUCKET"
```

`_RUN_POST_DEPLOY_EVAL`, `_AGENT_ENGINE_ID`, and `_STAGING_BUCKET` default to `false`, `""`, and `""` in the trigger definition — override them at run time only when needed.

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

> **Prerequisites**
> 1. Connect your GitHub repo: Cloud Console → Cloud Build → Triggers → **Connect Repository** → GitHub → select `customer-support-mas-ai`
> 2. Note your project number (`gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"`)

#### Cloud Console — quick reference

For each trigger: Cloud Build → Triggers → **Create Trigger** → fill in the fields below → **Save**.

| Field | ci-branch-push | ci-push-develop | ci-cd-push-main | ci-manual |
|---|---|---|---|---|
| **Name** | `ci-branch-push` | `ci-push-develop` | `ci-cd-push-main` | `ci-manual` |
| **Region** | `us-central1` | `us-central1` | `us-central1` | `us-central1` |
| **Event** | Push to branch | Push to branch | Push to branch | Manual invocation |
| **Source (2nd gen)** | `customer-support-mas-ai` | `customer-support-mas-ai` | `customer-support-mas-ai` | `customer-support-mas-ai` |
| **Branch** | `^main$` | `^develop$` | `^main$` | `main` |
| **Invert regex** | Yes | No | No | — |
| **Included/Ignored files** | — | — | — | — |
| **Build config** | `cloudbuild/pr-checks.yaml` | `cloudbuild/cloudbuild.yaml` | `cloudbuild/cloudbuild-deploy.yaml` | `cloudbuild/cloudbuild-nightly.yaml` |
| **Service account** | `PROJECT_NUMBER-compute@developer.gserviceaccount.com` | same | same | same |
| **_EVAL_PROFILE** | — | `standard` | `standard` | `full` |
| **_GOOGLE_CLOUD_LOCATION** | `us-central1` | `us-central1` | `us-central1` | `us-central1` |
| **_DEPLOY_AGENT_ENGINE** | — | — | `false` (auto-detected at runtime) | — |
| **_STAGING_BUCKET** | — | — | `gs://YOUR_STAGING_BUCKET` | `gs://YOUR_STAGING_BUCKET` |
| **_AGENT_ENGINE_DISPLAY_NAME** | — | — | `customer-support-multiagent` | — |
| **_AGENT_ENGINE_RESOURCE_NAME** | — | — | `projects/.../reasoningEngines/ID` | — |

Triggers use the **2nd gen Cloud Build API** (`repositoryEventConfig`). Use `gcloud builds triggers import` with inline YAML — the older `gcloud builds triggers create github` flags (`--repo-name`, `--repo-owner`) do not work with 2nd gen connections.

Replace `YOUR_PROJECT_ID`, `YOUR_PROJECT_NUMBER`, and `YOUR_STAGING_BUCKET` throughout.

#### Trigger 1 — Feature branch push (fast checks)

```bash
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-branch-push
filename: cloudbuild/pr-checks.yaml
repositoryEventConfig:
  push:
    branch: "^main$"
    invertRegex: true
  repository: projects/YOUR_PROJECT_ID/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
  repositoryType: GITHUB
serviceAccount: projects/YOUR_PROJECT_ID/serviceAccounts/YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com
substitutions:
  _GOOGLE_CLOUD_LOCATION: us-central1
EOF
```

> `invertRegex: true` on `^main$` fires on every branch except `main`. This includes `develop`, which means develop pushes run pr-checks in addition to the standard CI trigger — harmless extra checks.

#### Trigger 2 — Push to `develop` (standard CI, no deploy)

```bash
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-push-develop
filename: cloudbuild/cloudbuild.yaml
repositoryEventConfig:
  push:
    branch: "^develop$"
  repository: projects/YOUR_PROJECT_ID/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
  repositoryType: GITHUB
serviceAccount: projects/YOUR_PROJECT_ID/serviceAccounts/YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com
substitutions:
  _EVAL_PROFILE: standard
  _GOOGLE_CLOUD_LOCATION: us-central1
EOF
```

#### Trigger 3 — Push to `main` (CI + CD, auto-detects whether to redeploy Agent Engine)

No file filters needed. The `detect-agent-changes` step inside the YAML uses `git diff` to decide whether Agent Engine needs a redeploy.

```bash
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-cd-push-main
filename: cloudbuild/cloudbuild-deploy.yaml
repositoryEventConfig:
  push:
    branch: "^main$"
  repository: projects/YOUR_PROJECT_ID/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
  repositoryType: GITHUB
serviceAccount: projects/YOUR_PROJECT_ID/serviceAccounts/YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com
substitutions:
  _EVAL_PROFILE: standard
  _GOOGLE_CLOUD_LOCATION: us-central1
  _DEPLOY_AGENT_ENGINE: "false"
  _STAGING_BUCKET: gs://YOUR_STAGING_BUCKET
  _AGENT_ENGINE_DISPLAY_NAME: customer-support-multiagent
  _AGENT_ENGINE_RESOURCE_NAME: ""
EOF
```

> `_DEPLOY_AGENT_ENGINE=false` is the default. The `detect-agent-changes` step overrides it at runtime when `customer_support_agent/` files are detected in the diff. Set it explicitly to `true` on a manual trigger run to force an Agent Engine redeploy regardless.

#### Trigger 4 — Manual / nightly (full eval)

The `manual` event type must be created from the **Cloud Console** (not supported by `triggers import`):


1. Cloud Build → Triggers → **Create Trigger**
2. Name: `ci-manual` | Region: `us-central1`
3. Event: **Manual invocation**
4. Source (2nd gen): repository `Saoussen-CH/customer-support-mas-ai` | branch: `main`
5. Configuration: Cloud Build configuration file → `cloudbuild/cloudbuild-nightly.yaml`
6. Substitution variables: `_EVAL_PROFILE=full`, `_GOOGLE_CLOUD_LOCATION=us-central1`, `_STAGING_BUCKET=gs://YOUR_BUCKET`
7. Service account: `YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com`

Run on demand via CLI:
```bash
gcloud builds triggers run ci-manual --region=us-central1 --project=YOUR_PROJECT_ID --branch=main
```

Or use the `nightly` make target (reads project and engine IDs from `.env` automatically):
```bash
# Push your changes first — Cloud Build clones from GitHub, not local files
git push origin main

# Then trigger (all CI steps, post-deploy off by default)
make nightly

# Run specific steps only
make nightly RUN_LINT=false RUN_TOOL_TESTS=false   # unit + integration only
make nightly RUN_LINT=false RUN_TOOL_TESTS=false RUN_UNIT_TESTS=false RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true  # post-deploy only
```

**Note:** `make nightly` runs against the code already pushed to `main` on GitHub. Always push before running it.

#### Fixing existing triggers with typos

If a trigger was created with trailing spaces in the filename or branch pattern, update it in place:

```bash
# List trigger IDs
gcloud builds triggers list --region=us-central1 --format="table(name,id)"

# Re-import with the id field to update in place (no delete needed)
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-cd-push-main
id: YOUR_TRIGGER_ID
filename: cloudbuild/cloudbuild-deploy.yaml
...
EOF
```

### Nightly Schedule

Cloud Build doesn't have native cron triggers. Use Cloud Scheduler:

```bash
TRIGGER_ID=$(gcloud builds triggers list \
  --filter="name=ci-manual" --format="value(id)")

gcloud scheduler jobs create http nightly-full-eval \
  --schedule="0 0 * * *" \
  --uri="https://cloudbuild.googleapis.com/v1/projects/$PROJECT_ID/locations/us-central1/triggers/${TRIGGER_ID}:run" \
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
| `_DEPLOY_AGENT_ENGINE` | `false` | Override to force Agent Engine redeploy. Auto-detected at runtime by `detect-agent-changes` step via `git diff`; set explicitly to `true` to force a redeploy regardless of changed files. |
| `_STAGING_BUCKET` | `` | GCS staging bucket for Agent Engine deployment (e.g. `gs://my-bucket`) |
| `_AGENT_ENGINE_RESOURCE_NAME` | `` | Full resource name of the Agent Engine for Cloud Run (e.g. `projects/P/locations/L/reasoningEngines/ID`) |
| `_MODEL_ARMOR_ENABLED` | `false` | Enable Model Armor prompt filtering |
| `_MODEL_ARMOR_TEMPLATE_ID` | `` | Model Armor template ID (if enabled) |
| `_RUN_LINT` | `true` | Run lint step (nightly only) |
| `_RUN_TOOL_TESTS` | `true` | Run tool-tests step (nightly only) |
| `_RUN_UNIT_TESTS` | `true` | Run unit-tests step (nightly only) |
| `_RUN_INTEGRATION_TESTS` | `true` | Run integration-tests step (nightly only) |
| `_RUN_POST_DEPLOY_EVAL` | `false` | Enable post-deploy eval (nightly only) |
| `_AGENT_ENGINE_ID` | `` | Agent Engine ID for post-deploy eval |
| `_STAGING_BUCKET` (nightly) | `` | GCS bucket for post-deploy eval HTML report upload (e.g. `gs://my-bucket`). Report saved to `gs://BUCKET/eval-reports/eval-TIMESTAMP.html`; URI logged as a param in Vertex AI Experiments run. |

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

# Trigger the nightly pipeline (ci-manual) against already-pushed code on main
# Cloud Build reads from GitHub — push your changes first
make nightly                                         # all CI steps, post-deploy off
make nightly RUN_LINT=false RUN_TOOL_TESTS=false     # unit + integration only
make nightly RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true  # skip integration, run post-deploy
make nightly RUN_LINT=false RUN_TOOL_TESTS=false RUN_UNIT_TESTS=false RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true  # post-deploy eval only
# _STAGING_BUCKET is read automatically from GOOGLE_CLOUD_STORAGE_BUCKET in .env
# HTML report → gs://BUCKET/eval-reports/eval-TIMESTAMP.html
# Vertex AI Experiments run → eval-TIMESTAMP (same name, GCS URI logged as param)

# Show all targets
make help
```
