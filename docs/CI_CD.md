# CI/CD with Google Cloud Build

The project uses **Google Cloud Build** for continuous integration and deployment. Three pipeline configs are active across four triggers, with eval profile selection per trigger type.

## Pipeline Overview

```
cloudbuild/pr-checks.yaml          PR checks (pull requests against deploy branches)
cloudbuild/cloudbuild-deploy.yaml  CI + CD (deploy on push) — auto-detects agent changes
cloudbuild/cloudbuild-nightly.yaml Full eval + optional post-deploy eval (scheduled/manual)
```

> **Note:** `cloudbuild/cloudbuild.yaml` is a CI-only config that is no longer used by any
> active trigger. It is retained for reference but is not wired to any Cloud Build trigger.

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
                        └── deploy-agent-engine  ← skipped if no agent changes
                            └── deploy-cloud-run
                                └── get-service-url
                                    └── smoke-test
                                        └── load-test  ← staging only (_RUN_LOAD_TESTS=true)
```

`lint` and `tool-tests` run in parallel after `install-deps`. CD steps only start after **all**
CI steps pass. `deploy-agent-engine` must complete before `deploy-cloud-run` so Cloud Run always
talks to the already-updated agent.

---

## Trigger Strategy

| Trigger | Environment | Branch | Config | Deploy | Load tests |
|---------|-------------|--------|--------|--------|------------|
| `ci-pull-request` | all | PR → deploy branch | `pr-checks.yaml` | No | No |
| `ci-cd-push-develop` | dev | develop | `cloudbuild-deploy.yaml` | Yes (dev) | No |
| `ci-cd-push-staging` | staging | staging | `cloudbuild-deploy.yaml` | Yes (staging) | Yes |
| `ci-cd-push-main` | prod | main | `cloudbuild-deploy.yaml` | Yes (prod) | No |
| `ci-manual` | prod | main (manual) | `cloudbuild-nightly.yaml` | No | No |

`ci-pull-request` targets the deploy branch of each environment (develop, staging, or main) as
the base — it fires when a PR is opened or updated against any of those branches.

---

## Smoke Tests

Smoke tests run at the end of every deployment, in all environments.

**What they test (6 checks in `tests/smoke/test_smoke.py`):**

1. Health endpoint returns 200
2. Agent responds to a basic message
3. Product search tool is reachable
4. Order tracking tool is reachable
5. Model Armor filters unsafe prompts
6. Session continuity (follow-up messages use the same session)

**When they run:** After `deploy-cloud-run` in `cloudbuild-deploy.yaml`. The preceding
`get-service-url` step writes the Cloud Run URL to `/workspace/service_url.txt` so the smoke
test step can pick it up automatically.

**Running locally:**
```bash
uv sync --group dev
CLOUD_RUN_URL=https://your-cloud-run-url pytest tests/smoke/ -v
```

---

## Load Tests

Load tests run in the **staging** environment only, controlled by the `_RUN_LOAD_TESTS`
substitution variable (set to `true` on the staging trigger, `false` everywhere else).

**Tool:** [Locust](https://locust.io/) — `tests/load/locustfile.py`

**Configuration:** 5 concurrent users, 2-minute run

**SLO thresholds** (checked by `tests/load/check_slos.py`):

| SLO | Threshold |
|-----|-----------|
| p95 response time | < 10 s |
| p99 response time | < 20 s |
| Error rate | < 5 % |
| Requests per second | > 0.5 |

The `load-test` step fails the build if any SLO is breached.

---

## Auto-detection of Agent Changes

`cloudbuild-deploy.yaml` runs a `detect-agent-changes` step first on every push:

```bash
git diff --name-only HEAD~1 HEAD -- customer_support_agent/
```

- If `customer_support_agent/` files changed → writes `true` → Agent Engine is redeployed
- Otherwise → writes `false` → only Cloud Run is deployed

`_DEPLOY_AGENT_ENGINE=true` can still be set explicitly on the trigger (or via
`make submit-build DEPLOY_AGENT_ENGINE=true`) to force an Agent Engine deploy regardless of which
files changed.

---

## Skipping Builds with `[skip ci]`

For commits that change nothing deployable — docs, Terraform, CI config — add `[skip ci]` or
`[ci skip]` anywhere in the commit message to prevent all triggers from running:

```bash
git commit -m "docs: update CI_CD.md [skip ci]"
git commit -m "[skip ci] fix typo in README"
```

**When to use each mechanism:**

| Scenario | Mechanism |
|----------|-----------|
| Working on a feature branch | Push normally → `ci-pull-request` fires on PR |
| Merging to `develop` | Push normally → `ci-cd-push-develop` deploys to dev |
| Merging to `staging` | Push normally → `ci-cd-push-staging` deploys to staging + runs load tests |
| Agent logic changed, merging to `main` | Push normally → auto-detects agent change → deploys Agent Engine + Cloud Run |
| Non-agent code, merging to `main` | Push normally → no agent change detected → deploys Cloud Run only |
| Docs / Terraform / CI config only | Add `[skip ci]` to commit message → no build runs |

---

## Eval Profiles

| Profile | Unit Metrics | Integration Metrics | Cost |
|---------|-------------|-------------------|------|
| `fast` | Rouge-1 response match | Rouge-1 response match | Free |
| `standard` | + tool name F1 (custom metric) | + rubric-based LLM judge | Low |
| `full` | + LLM-as-judge response quality | + LLM-as-judge response quality | Higher |

Profile configs: `tests/eval_configs/{unit,integration}/{fast,standard,full}.json`

---

## CI Steps

### 1. install-deps
Installs Python dependencies via `uv sync --frozen` into `/workspace/.venv` (shared across all
steps via Cloud Build's `/workspace` volume). Each subsequent step activates the venv with
`export PATH="/workspace/.venv/bin:$PATH"`.

### 2. lint
Runs `ruff check customer_support_agent/ --ignore=E501`.

`pr-checks.yaml` also runs `ruff format customer_support_agent/ --check` to catch formatting
issues (mirrors `.pre-commit-config.yaml`).

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

---

## CD Steps (cloudbuild-deploy.yaml only)

### 6. docker-build
Multi-stage Docker build (`backend/Dockerfile`): React frontend (Node 20) + FastAPI backend
(Python 3.11). Tagged with `$COMMIT_SHA` and `latest`.

### 7. docker-push
Pushes to Artifact Registry at
`$_REGION-docker.pkg.dev/$PROJECT_ID/customer-support/customer-support-app`.

### 8. deploy-agent-engine (conditional)
Runs `deployment/deploy.py --action deploy` when `_DEPLOY_AGENT_ENGINE=true`. Uses
update-or-create logic: if an Agent Engine with `AGENT_ENGINE_DISPLAY_NAME` already exists it is
updated in place; otherwise a new engine is created and its resource name is written to
`/workspace/agent_engine_resource_name.txt` for the next step.

### 9. deploy-cloud-run
Deploys the image to Cloud Run. Reads `AGENT_ENGINE_RESOURCE_NAME` from
`/workspace/agent_engine_resource_name.txt` (written by step 8 on first create) or falls back to
the `_AGENT_ENGINE_RESOURCE_NAME` substitution variable (used on updates where the resource name
is unchanged). Sets `ENVIRONMENT=production` to enable structured JSON logging.

### 10. get-service-url
Fetches the Cloud Run service URL and writes it to `/workspace/service_url.txt` for use by the
smoke test step.

### 11. smoke-test
Runs `pytest tests/smoke/test_smoke.py` against the deployed service URL. Runs in all
environments after every deployment.

### 12. load-test (staging only)
Runs Locust for 2 minutes with 5 concurrent users, then runs `tests/load/check_slos.py` to
assert SLO thresholds. Skipped when `_RUN_LOAD_TESTS=false` (default for dev and prod triggers).

---

## Nightly Pipeline (cloudbuild-nightly.yaml)

Runs all CI steps with `_EVAL_PROFILE=full` (all metrics including LLM-as-judge). Optionally
runs post-deploy evaluation against a deployed Agent Engine.

```bash
# Full eval only (default — post-deploy eval skipped)
gcloud builds triggers run ci-manual \
  --project=YOUR_PROJECT_ID --region=us-central1 --branch=main

# Full eval + post-deploy eval against a live Agent Engine
gcloud builds triggers run ci-manual \
  --project=YOUR_PROJECT_ID --region=us-central1 --branch=main \
  --substitutions="_RUN_POST_DEPLOY_EVAL=true,_AGENT_ENGINE_ID=YOUR_ENGINE_ID,_STAGING_BUCKET=gs://YOUR_BUCKET"
```

`_RUN_POST_DEPLOY_EVAL`, `_AGENT_ENGINE_ID`, and `_STAGING_BUCKET` default to `false`, `""`, and
`""` in the trigger definition — override them at run time only when needed.

---

## Setup

### Quick Start (Terraform — recommended)

All infrastructure (APIs, IAM, Firestore, GCS, Artifact Registry, Cloud Build triggers, Cloud
Scheduler) is managed by Terraform. Each environment has its own directory.

```bash
# 1. Copy and fill in your values (shown for prod — repeat for dev/staging as needed)
cd terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

# 2. Bootstrap infrastructure
cd ../../..
make infra-up    # terraform init + apply (prod by default)

# 3. Connect GitHub repo (one-time, browser OAuth — cannot be automated)
#    Cloud Console → Cloud Build → Repositories (2nd gen) → Create host connection → GitHub
#    Then: Link Repository → select your repo
#    Then set github_connected=true, cloudbuild_connection_name, cloudbuild_repo_name
#    in terraform/environments/prod/terraform.tfvars, then: make infra-up

# 4. Seed Firestore and deploy
make seed-db
make deploy-agent-engine
make deploy-cloud-run
```

See `terraform/modules/core/` for the shared Terraform module used by all environments.

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
> 1. Create a 2nd gen host connection: Cloud Console → Cloud Build → **Repositories (2nd gen)** → **Create host connection** → GitHub → name it `github-connection`
> 2. Link the repository: **Link Repository** → select `Saoussen-CH/customer-support-mas-ai`
> 3. Get the slugified repo name: `gcloud builds repositories list --connection=github-connection --region=us-central1`
> 4. Set `github_connected=true`, `cloudbuild_connection_name`, and `cloudbuild_repo_name` in the relevant `terraform/environments/*/terraform.tfvars`, then run `make infra-up`
>
> **Important:** Cloud Build 2nd gen triggers require `service_account` in the API request — omitting it causes a silent `400 INVALID_ARGUMENT`. Terraform handles this automatically.

#### Cloud Console — quick reference

For each trigger: Cloud Build → Triggers → **Create Trigger** → fill in the fields below → **Save**.

| Field | ci-pull-request | ci-cd-push-develop | ci-cd-push-staging | ci-cd-push-main | ci-manual |
|---|---|---|---|---|---|
| **Name** | `ci-pull-request` | `ci-cd-push-develop` | `ci-cd-push-staging` | `ci-cd-push-main` | `ci-manual` |
| **Region** | `us-central1` | `us-central1` | `us-central1` | `us-central1` | `us-central1` |
| **Event** | Pull request | Push to branch | Push to branch | Push to branch | Manual invocation |
| **Branch** | deploy branches | `^develop$` | `^staging$` | `^main$` | `main` |
| **Build config** | `cloudbuild/pr-checks.yaml` | `cloudbuild/cloudbuild-deploy.yaml` | `cloudbuild/cloudbuild-deploy.yaml` | `cloudbuild/cloudbuild-deploy.yaml` | `cloudbuild/cloudbuild-nightly.yaml` |
| **_EVAL_PROFILE** | — | `standard` | `standard` | `standard` | `full` |
| **_RUN_LOAD_TESTS** | — | `false` | `true` | `false` | — |
| **_STAGING_BUCKET** | — | `gs://YOUR_DEV_BUCKET` | `gs://YOUR_STAGING_BUCKET` | `gs://YOUR_PROD_BUCKET` | `gs://YOUR_PROD_BUCKET` |
| **_AGENT_ENGINE_RESOURCE_NAME** | — | `projects/.../reasoningEngines/ID` | `projects/.../reasoningEngines/ID` | `projects/.../reasoningEngines/ID` | — |

#### Trigger — Push to `develop` (dev environment, CI + CD)

```bash
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-cd-push-develop
filename: cloudbuild/cloudbuild-deploy.yaml
repositoryEventConfig:
  push:
    branch: "^develop$"
  repository: projects/YOUR_PROJECT_ID/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
  repositoryType: GITHUB
serviceAccount: projects/YOUR_PROJECT_ID/serviceAccounts/YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com
substitutions:
  _EVAL_PROFILE: standard
  _GOOGLE_CLOUD_LOCATION: us-central1
  _DEPLOY_AGENT_ENGINE: "false"
  _STAGING_BUCKET: gs://YOUR_DEV_STAGING_BUCKET
  _AGENT_ENGINE_RESOURCE_NAME: ""
  _RUN_LOAD_TESTS: "false"
EOF
```

#### Trigger — Push to `staging` (staging environment, CI + CD + load tests)

```bash
gcloud builds triggers import --region=us-central1 --project=YOUR_PROJECT_ID --source=- <<'EOF'
name: ci-cd-push-staging
filename: cloudbuild/cloudbuild-deploy.yaml
repositoryEventConfig:
  push:
    branch: "^staging$"
  repository: projects/YOUR_PROJECT_ID/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
  repositoryType: GITHUB
serviceAccount: projects/YOUR_PROJECT_ID/serviceAccounts/YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com
substitutions:
  _EVAL_PROFILE: standard
  _GOOGLE_CLOUD_LOCATION: us-central1
  _DEPLOY_AGENT_ENGINE: "false"
  _STAGING_BUCKET: gs://YOUR_STAGING_BUCKET
  _AGENT_ENGINE_RESOURCE_NAME: ""
  _RUN_LOAD_TESTS: "true"
EOF
```

#### Trigger — Push to `main` (prod environment, CI + CD)

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
  _STAGING_BUCKET: gs://YOUR_PROD_STAGING_BUCKET
  _AGENT_ENGINE_DISPLAY_NAME: customer-support-multiagent
  _AGENT_ENGINE_RESOURCE_NAME: ""
  _RUN_LOAD_TESTS: "false"
EOF
```

#### Trigger — Manual / nightly (full eval, prod only)

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

Or use the `nightly` make target:
```bash
# Push your changes first — Cloud Build clones from GitHub, not local files
git push origin main

# Then trigger (all CI steps, post-deploy off by default)
make nightly

# Run specific steps only
make nightly RUN_LINT=false RUN_TOOL_TESTS=false   # unit + integration only
make nightly RUN_LINT=false RUN_TOOL_TESTS=false RUN_UNIT_TESTS=false RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true  # post-deploy only
```

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

Cloud Build doesn't have native cron triggers. Use Cloud Scheduler (created automatically by
Terraform for the prod environment):

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

---

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
| `_DEPLOY_AGENT_ENGINE` | `false` | Override to force Agent Engine redeploy. Auto-detected at runtime by `detect-agent-changes` via `git diff`; set to `true` to force a redeploy regardless of changed files. |
| `_STAGING_BUCKET` | `` | GCS staging bucket for Agent Engine deployment (e.g. `gs://my-bucket`) |
| `_AGENT_ENGINE_RESOURCE_NAME` | `` | Full resource name of the Agent Engine for Cloud Run |
| `_MODEL_ARMOR_ENABLED` | `false` | Enable Model Armor prompt filtering |
| `_MODEL_ARMOR_TEMPLATE_ID` | `` | Model Armor template ID (if enabled) |
| `_RUN_LOAD_TESTS` | `false` | Run Locust load tests and SLO check after deployment (`true` for staging only) |
| `_RUN_LINT` | `true` | Run lint step (nightly only) |
| `_RUN_TOOL_TESTS` | `true` | Run tool-tests step (nightly only) |
| `_RUN_UNIT_TESTS` | `true` | Run unit-tests step (nightly only) |
| `_RUN_INTEGRATION_TESTS` | `true` | Run integration-tests step (nightly only) |
| `_RUN_POST_DEPLOY_EVAL` | `false` | Enable post-deploy eval (nightly only) |
| `_AGENT_ENGINE_ID` | `` | Agent Engine ID for post-deploy eval |

`$PROJECT_ID` and `$COMMIT_SHA` are built-in Cloud Build substitutions.

---

## Timeouts

| Pipeline | Timeout | Rationale |
|----------|---------|-----------|
| `pr-checks.yaml` | 20 min | Fast profile only, quick feedback |
| `cloudbuild-deploy.yaml` | 60 min | CI + Docker build + Agent Engine + Cloud Run + smoke/load tests |
| `cloudbuild-nightly.yaml` | 60 min | Full eval with LLM judges is slow |

---

## Make Targets for CI

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

# Submit the full CI+CD pipeline to Cloud Build
make submit-build                          # Cloud Run only (_DEPLOY_AGENT_ENGINE=false)
make submit-build DEPLOY_AGENT_ENGINE=true # + Agent Engine redeploy
make submit-build EVAL_PROFILE=fast        # faster feedback

# Trigger the nightly pipeline (ci-manual) against already-pushed code on main
git push origin main   # Cloud Build reads from GitHub — push first
make nightly
make nightly RUN_LINT=false RUN_TOOL_TESTS=false
make nightly RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true
make nightly RUN_LINT=false RUN_TOOL_TESTS=false RUN_UNIT_TESTS=false RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true

# Show all targets
make help
```
