# CI/CD with Google Cloud Build

The project uses **Google Cloud Build** for continuous integration and deployment. Seven pipeline configs handle different scenarios across three environments (dev/staging/prod).

## Pipeline Overview

```
cloudbuild/pr-checks.yaml          App CI: fast eval + lint on every PR
cloudbuild/cloudbuild-deploy.yaml  App CI + CD on branch push (develop/staging/main) — auto-detects agent changes
cloudbuild/cloudbuild-nightly.yaml Full eval + optional post-deploy eval (scheduled/manual)
cloudbuild/release.yaml            Versioned release on git tag push (v*) — prod only
cloudbuild/terraform-plan.yaml     Infra: show plan diff on every PR — runs per env in parallel with pr-checks
cloudbuild/terraform-apply.yaml    Infra: auto-apply on merge — runs per env in parallel with deploy
```

> **Diagram:** See [`docs/diagrams/cicd-pipeline.mmd`](diagrams/cicd-pipeline.mmd) for the full promotion flow visualized.

**Key design principle:** Terraform is fully decoupled from the app deploy. Infrastructure changes propagate automatically — add a resource to `terraform/modules/core/`, open a PR (plan shows the diff), merge (apply runs automatically), promote through `develop → staging → main`.

### Job Dependency Graph — cloudbuild-deploy.yaml

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

### Job Dependency Graph — release.yaml

```
install-deps
├── lint ───────────────────────────┐
└── unit-tests (standard profile)  │
    └── docker-build ◄─────────────┘  (tagged: $TAG_NAME + $COMMIT_SHA + latest)
        └── docker-push
            └── deploy-agent-engine  ← always deploys (display name: customer-support-multiagent-vX.Y.Z)
                └── deploy-cloud-run ← uses $TAG_NAME image (not $COMMIT_SHA)
                    └── smoke-test
```

`lint` and `unit-tests` run in parallel after `install-deps`. CD steps only start after **all** CI steps pass. `deploy-agent-engine` must complete before `deploy-cloud-run` so Cloud Run always talks to the already-updated agent.

`ci-pull-request` targets the deploy branch of each environment (develop, staging, or main) as
the base — it fires when a PR is opened or updated against any of those branches.

### App triggers (per environment)

| Trigger | Event | Envs | Config | `_EVAL_PROFILE` | Agent Engine deploy |
|---------|-------|------|--------|-----------------|---------------------|
| `ci-pull-request` | PR to env branch | dev/staging/prod | `cloudbuild/pr-checks.yaml` | `fast` | — |
| `ci-cd-push-develop` | Push to `develop` | dev | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | auto-detected |
| `ci-cd-push-staging` | Push to `staging` | staging | `cloudbuild/cloudbuild-deploy.yaml` | `standard` | auto-detected |
| `ci-push-main` | Push to `main` | prod | `cloudbuild/cloudbuild.yaml` | `standard` | — (CI only) |
| `ci-manual` | Manual / nightly | prod | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |
| Cloud Scheduler | Midnight UTC | prod | `cloudbuild/cloudbuild-nightly.yaml` | `full` | — |
| `release` | Git tag `v*.*.*` | prod | `cloudbuild/release.yaml` | `standard` | always |

### Terraform triggers (per environment, run in parallel with app triggers)

| Trigger | Event | Envs | Config |
|---------|-------|------|--------|
| `terraform-plan` | PR to env branch | dev/staging/prod | `cloudbuild/terraform-plan.yaml` |
| `terraform-apply` | Push to env branch | dev/staging/prod | `cloudbuild/terraform-apply.yaml` |

**Total triggers per project:** dev=4, staging=4, prod=6 (ci-push-main is CI-only; prod deploy is via git tag → release trigger)

### Full event → trigger mapping

| Event | Triggers that fire |
|---|---|
| PR → `develop` | `ci-pull-request` (fast eval) + `terraform-plan` (infra diff) |
| Merge → `develop` | `ci-cd-push-develop` (deploy to dev) + `terraform-apply` (infra apply to dev) |
| PR → `staging` | `ci-pull-request` + `terraform-plan` |
| Merge → `staging` | `ci-cd-push-staging` (deploy to staging) + `terraform-apply` (infra apply to staging) |
| PR → `main` | `ci-pull-request` + `terraform-plan` |
| Merge → `main` | `ci-push-main` (CI only — no deploy) + `terraform-apply` (infra apply to prod) |
| Git tag `v*` | `release` (versioned deploy to prod) |

## Terraform CI/CD

Infrastructure changes are managed separately from app code and propagate automatically through the environment promotion flow.

### How it works

1. Add or modify a resource in `terraform/modules/core/` (shared across all envs)
2. Open a PR → `terraform-plan` fires in the target env's project and posts the diff to build logs
3. Reviewer approves the plan, merges the PR
4. `terraform-apply` fires automatically and applies the changes to that environment
5. Promote `develop → staging → main` to apply the same change to staging and prod

**Result:** A new Cloud Run service, IAM binding, Firestore index, or any other GCP resource added once to the module lands in all three environments without any manual `terraform apply`.

### Remote state

Terraform state is stored in GCS (not local files) so Cloud Build can read and write it:

```
gs://{project_id}-tf-state/customer-support-mas/{env}/   ← state files
gs://{project_id}-tf-state/tfvars/terraform.tfvars       ← env config (gitignored locally)
```

Bootstrap the state bucket once per environment (one-time manual step):

```bash
make bootstrap-tfstate ENV=dev      # creates bucket + uploads tfvars
make bootstrap-tfstate ENV=staging
make bootstrap-tfstate ENV=prod
```

After any local tfvars change (e.g. adding `agent_engine_resource_name`), sync it back to GCS so CI picks it up:

```bash
make sync-tfvars ENV=dev
```

### Substitution variables

| Variable | Description | Example |
|---|---|---|
| `_ENV_DIRECTORY` | Path to environment dir | `terraform/environments/dev` |
| `_ENVIRONMENT` | Environment name | `dev` |
| `_TF_STATE_BUCKET` | GCS bucket for state + tfvars | `css-mas-dev-tf-state` |

`_TF_STATE_BUCKET` defaults to `{PROJECT_ID}-tf-state` if not set in the trigger.

---

## Release Pipeline

### Creating a release

Tag the commit you want to release and push the tag. Cloud Build fires automatically on the prod project (`css-mas-prod`):

```bash
git tag v1.0.0
git push origin v1.0.0
```

The `release` trigger (`cloudbuild/release.yaml`) runs:

1. Lint + unit tests at `standard` eval profile (stronger gate than regular CI)
2. Docker image built and pushed with **three tags**: `v1.0.0`, `$COMMIT_SHA`, `latest`
3. Agent Engine deployed — display name set to `customer-support-multiagent-v1.0.0`
4. Cloud Run deployed using the **versioned image tag** (`v1.0.0`, not `$COMMIT_SHA`)
5. Smoke tests run against the live Cloud Run URL

### Rollback

Because Cloud Run is pinned to the versioned image tag, rollback is a single `gcloud` command — no rebuild required:

```bash
gcloud run deploy customer-support-app \
  --image=us-central1-docker.pkg.dev/css-mas-prod/customer-support/customer-support-app:v0.0.9 \
  --region=us-central1 \
  --project=css-mas-prod
```

---

## Agent Engine Versioning Strategy

Vertex AI Agent Engine (Reasoning Engine) has no native concept of tags or versions — each deployment either creates a new resource or updates the existing one. Three strategies exist:

### Option 1 — Display name label (metadata only)

Set the display name to include the version: `customer-support-multiagent-v1.0.0`. Visible in the GCP Console and in Cloud Logging, but not enforceable. The resource name stays stable, so Cloud Run needs no change on updates.

### Option 2 — One resource per major version

Deploy a new reasoning engine per release tag, keep the old one running:

- `reasoningEngines/111` = `v1.0.0`
- `reasoningEngines/222` = `v2.0.0`

**Pros:** Instant rollback by pointing Cloud Run's `AGENT_ENGINE_RESOURCE_NAME` env var to the old resource name. No redeploy needed.

**Cons:** Each idle reasoning engine incurs ongoing compute and storage costs. Managing the lifecycle (which versions to keep, when to delete old ones) adds operational overhead. For a system deployed across dev/staging/prod, this multiplies the idle cost across all environments.

**Why we didn't choose this:** The cost-to-benefit ratio is poor for this project. Cloud Run rollback (Option 3) achieves the same outcome for the app layer at zero extra cost. Agent Engine changes are also relatively infrequent — most releases only change the Cloud Run image (backend/frontend). When the agent code does change, the display name captures the version for traceability.

### Option 3 — Git tag + versioned Docker image (chosen)

The real versioning lives in **git tags** and **Artifact Registry image tags**. This is what `release.yaml` implements:

- Git tag `v1.0.0` → Docker image tagged `v1.0.0` in Artifact Registry
- Agent Engine display name set to `customer-support-multiagent-v1.0.0` (traceability)
- Cloud Run deployed with `image:v1.0.0` (not `image:latest`)
- Rollback = redeploy the previous tagged Cloud Run image (see above)

**Full version traceability per deployment:**

| Artifact | Version identifier |
|---|---|
| Git source | Tag `v1.0.0` + commit SHA |
| Docker image | `customer-support-app:v1.0.0` in Artifact Registry |
| Agent Engine | Display name `customer-support-multiagent-v1.0.0` |
| Cloud Run | Image pinned to `v1.0.0` |

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
| Working on a feature branch | Push normally → `ci-pull-request` fires (fast checks + terraform plan) |
| Merging to `develop` | Push normally → `ci-cd-push-develop` + `terraform-apply` fire in parallel |
| Agent logic changed, merging to `main` | Push normally → auto-detects agent change → deploys Agent Engine + Cloud Run |
| Non-agent code, merging to `main` | Push normally → no agent change detected → deploys Cloud Run only |
| New Terraform resource added | Push normally → plan on PR, apply on merge — propagates to all envs via promotion |
| Docs / CI config only | Add `[skip ci]` to commit message → no build runs |

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

All infrastructure is managed by Terraform in `terraform/modules/core/` (shared module) with per-environment configs in `terraform/environments/{dev,staging,prod}/`. State is stored remotely in GCS.

```bash
# 1. Copy and fill in your values for each environment
cp terraform/environments/dev/terraform.tfvars.example \
   terraform/environments/dev/terraform.tfvars
$EDITOR terraform/environments/dev/terraform.tfvars

# 2. Create GCS state bucket (once per env — stores state + tfvars for CI)
make bootstrap-tfstate ENV=dev

# 3. Bootstrap infrastructure
make infra-up ENV=dev   # terraform init + apply

# 4. Connect GitHub repo (one-time, browser OAuth — cannot be automated)
#    Cloud Console → Cloud Build → Repositories (2nd gen) → Create host connection → GitHub
#    Then: Link Repository → select your repo
#    Then set github_connected=true, cloudbuild_connection_name, cloudbuild_repo_name in terraform.tfvars
#    Then: make sync-tfvars ENV=dev && make infra-up ENV=dev

# 5. Seed Firestore and deploy
make seed-db
make deploy-agent-engine
make deploy-cloud-run
```

See [../terraform/](../terraform/) for full Terraform configuration and [DEPLOYMENT.md](./DEPLOYMENT.md) for the complete multi-environment setup walkthrough.

### Branch Protection Rules

Protect each deploy branch so a failing check blocks the merge button:

**GitHub → repo → Settings → Branches → Add branch protection rule** — repeat for `develop`, `staging`, and `main`:

| Setting | Value |
|---|---|
| Branch name pattern | `develop` / `staging` / `main` |
| Require status checks to pass | ✓ |
| Required checks | `ci-pull-request`, `terraform-plan` |
| Require branches to be up to date | ✓ |
| Do not allow bypassing (main only) | ✓ |

> **Note:** GitHub only lists checks that have already run on a branch. If a check doesn't
> appear in the search dropdown (e.g. on `main` before the first PR), type the name exactly
> (`ci-pull-request`, `terraform-plan`) and press Enter — GitHub accepts manually typed names.

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
| `roles/storage.objectAdmin` | Staging bucket + tfstate bucket access |
| `roles/editor` (or targeted) | `terraform-apply` — create/update GCP resources |

All roles are granted by Terraform (`terraform/modules/core/iam.tf`). No service account key file is needed — Cloud Build runs natively on GCP with IAM.

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

| Field | ci-pull-request | ci-push-develop | ci-cd-push-main | ci-manual | release |
|---|---|---|---|---|---|
| **Name** | `ci-pull-request` | `ci-push-develop` | `ci-cd-push-main` | `ci-manual` | `release` |
| **Region** | `us-central1` | `us-central1` | `us-central1` | `us-central1` | `us-central1` |
| **Event** | Pull request | Push to branch | Push to branch | Manual invocation | Push tag |
| **Repository (2nd gen)** | `Saoussen-CH-customer-support-mas-ai` | same | same | same | same |
| **Branch / Tag** | `^main$` | `^develop$` | `^main$` | `main` | `^v[0-9]+\.[0-9]+\.[0-9]+` |
| **Build config** | `cloudbuild/pr-checks.yaml` | `cloudbuild/cloudbuild.yaml` | `cloudbuild/cloudbuild-deploy.yaml` | `cloudbuild/cloudbuild-nightly.yaml` | `cloudbuild/release.yaml` |
| **Service account** | `PROJECT_NUMBER@cloudbuild.gserviceaccount.com` | same | same | same | same |
| **_EVAL_PROFILE** | — | `standard` | `standard` | `full` | `standard` |
| **_GOOGLE_CLOUD_LOCATION** | `us-central1` | `us-central1` | `us-central1` | `us-central1` | `us-central1` |
| **_STAGING_BUCKET** | — | — | `gs://YOUR_STAGING_BUCKET` | `gs://YOUR_STAGING_BUCKET` | `gs://YOUR_STAGING_BUCKET` |
| **_AGENT_ENGINE_RESOURCE_NAME** | — | — | `projects/.../reasoningEngines/ID` | — | `projects/.../reasoningEngines/ID` |

Triggers use the **2nd gen Cloud Build API** (`repositoryEventConfig`). Use `gcloud builds triggers import` with inline YAML — the older `gcloud builds triggers create github` flags (`--repo-name`, `--repo-owner`) do not work with 2nd gen connections.

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
| `release.yaml` | 60 min | Standard eval + Docker build + Agent Engine + Cloud Run + smoke tests |
| `terraform-plan.yaml` | 20 min | Init + plan only, no apply |
| `terraform-apply.yaml` | 30 min | Init + apply (resource creation can be slow on first run) |

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
