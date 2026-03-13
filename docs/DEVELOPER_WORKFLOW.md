# Developer Workflow

This guide covers the multi-environment developer workflow — from infrastructure bootstrap through local testing, CI/CD, and releases across dev, staging, and prod.

---

## Prerequisites

- Terraform installed (`terraform -v`)
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- 3 GCP projects created: `css-mas-dev`, `css-mas-staging`, `css-mas-prod`
- Python + `uv` installed (`pip install uv`)
- Repo cloned and dependencies installed (`make install`)

---

## Step 1 — Clone and install

```bash
git clone https://github.com/Saoussen-CH/customer-support-mas-ai.git
cd customer-support-mas-ai
make install
```

---

## Step 2 — Validate Terraform structure (no GCP calls, offline)

Run this for all three environments to confirm the module is wired correctly:

```bash
cd terraform/environments/dev
terraform init -backend=false
terraform validate
cd ../staging
terraform init -backend=false
terraform validate
cd ../prod
terraform init -backend=false
terraform validate
cd ../../..
```

**Expected:** `Success! The configuration is valid.` for each environment.

---

## Step 3 — Set up dev environment .env

See [ENV_SETUP.md](./ENV_SETUP.md) for full environment setup.

```bash
cp .env.dev.example .env.dev
```

Edit `.env.dev` and fill in:

| Variable | Value |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | `css-mas-dev` (your actual dev project ID) |
| `GOOGLE_CLOUD_STORAGE_BUCKET` | `gs://css-mas-dev-staging` (must be globally unique) |
| `AGENT_ENGINE_RESOURCE_NAME` | leave blank for now |
| `MODEL_ARMOR_TEMPLATE_ID` | leave blank for now |

Activate it:

```bash
make switch-env ENV=dev
# Verify:
grep GOOGLE_CLOUD_PROJECT .env
```

**Expected:** prints `GOOGLE_CLOUD_PROJECT=css-mas-dev`

---

## Step 4 — Set up Terraform tfvars for dev

```bash
cd terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and fill in:

```hcl
project_id          = "css-mas-dev"           # your actual dev project ID
staging_bucket_name = "css-mas-dev-staging"   # globally unique GCS bucket name
github_owner        = "Saoussen-CH"            # your GitHub username

# Leave these commented out for now:
# google_managed_sas_exist   = true
# agent_engine_resource_name = "..."
# github_connected           = true
# cloudbuild_connection_name = "github-connection"
# cloudbuild_repo_name       = "Saoussen-CH-customer-support-mas-ai"
```

---

## Step 5 — Bootstrap Cloud Resource Manager API

On a fresh GCP project, Terraform cannot read project metadata until this API
is enabled. Run this once before the first `terraform plan`:

```bash
cd ../../..   # back to repo root
make bootstrap-apis ENV=dev
```

Wait ~30 seconds for the API to propagate, then continue.

> This only needs to be done once per new GCP project.

---

## Step 6 — Terraform plan (preview, no changes applied)

```bash
cd terraform/environments/dev
terraform init
terraform plan -var-file=terraform.tfvars
```

**Expected:** Plan shows resources to create (APIs, Firestore, GCS bucket, IAM, Artifact Registry, Model Armor). No errors.

> Note: `github_connected = false` by default so Cloud Build triggers are skipped — this is correct.

---

## Step 7 — Apply dev infrastructure

```bash
terraform apply -var-file=terraform.tfvars
# Type 'yes' to confirm
```

Or via Makefile from the repo root:

```bash
make infra-up ENV=dev
```

**Expected:** All resources created. Note the outputs:

```bash
terraform -chdir=terraform/environments/dev output
```

Copy `model_armor_template_name` into `.env.dev` → `MODEL_ARMOR_TEMPLATE_ID=...`

---

## Step 8 — Authenticate and test GCP access

```bash
make switch-env ENV=dev
gcloud config set project css-mas-dev
gcloud auth application-default login
gcloud auth application-default set-quota-project css-mas-dev
```

Test Firestore and APIs are working:

```bash
make setup-firestore
make seed-db
make add-embeddings
```

---

## Step 9 — Test local agent (no deployment needed)

```bash
make test-local
```

**Expected:** Agent responds to a test query locally without errors.

---

## Step 10 — Run unit and integration tests

```bash
make test-tools
make test-unit
make test-integration
```

**Expected:** All pass. Use `EVAL_PROFILE=fast` (default) for speed.

---

## Step 11 — Deploy to dev (optional — requires GCP project set up)

```bash
make switch-env ENV=dev
make deploy-agent-engine
```

After deploy completes, copy the resource name printed at the end into:
- `.env.dev` → `AGENT_ENGINE_RESOURCE_NAME=projects/.../reasoningEngines/...`
- `terraform/environments/dev/terraform.tfvars`:
  ```hcl
  google_managed_sas_exist   = true   # ← uncomment this
  agent_engine_resource_name = "projects/.../reasoningEngines/..."  # ← and this
  ```

**Re-apply Terraform** — this is required to grant Firestore permissions to the two
Agent Engine service accounts that Google creates on first deploy:

```bash
make infra-up ENV=dev
```

> Without this re-apply, tool calls (`search_products`, `track_order`, etc.) will
> fail with `403 Missing or insufficient permissions` because the Agent Engine SA
> (`service-PROJ_NUM@gcp-sa-aiplatform-re.iam.gserviceaccount.com`) won't yet have
> `roles/datastore.user`.

Deploy Cloud Run:

```bash
make deploy-cloud-run ENV=dev
```

---

## Step 12 — Run smoke tests against dev

After Cloud Run is deployed:

```bash
export CLOUD_RUN_URL=$(gcloud run services describe customer-support-app --region us-central1 --project css-mas-dev --format="value(status.url)")
CLOUD_RUN_URL=$CLOUD_RUN_URL uv run pytest tests/smoke/ -v
```

**Expected:** All 6 smoke tests pass.

---

## Step 13 — Run load tests against staging (staging only)

After deploying to staging (`make switch-env ENV=staging` + repeat steps 4-10):

```bash
export CLOUD_RUN_URL=$(gcloud run services describe customer-support-app --region us-central1 --project css-mas-staging --format="value(status.url)")

uv run locust -f tests/load/locustfile.py \
  --headless --users 5 --spawn-rate 1 --run-time 2m \
  --host $CLOUD_RUN_URL \
  --csv /tmp/load-results \
  --exit-code-on-error 1

uv run python tests/load/check_slos.py /tmp/load-results_stats.csv
```

**Expected:** Locust finishes, SLO checker exits 0 (all SLOs met).

> Note: Latency is dominated by LLM inference and is not a useful SLO for AI systems.
> The checker validates: error_rate < 5%, at least 1 request completed per endpoint,
> and p99 < 270s (well within Cloud Run's 300s hard timeout).
> Response correctness is validated separately via `make eval-post-deploy`.

---

## Step 14 — Connect GitHub to Cloud Build and enable CI/CD triggers

Cloud Build triggers require a 2nd-gen GitHub connection. This is a one-time OAuth
step per GCP project — it cannot be automated by Terraform.

### 14a — Create the connection in the GCP Console

1. Open **Cloud Build → Repositories (2nd gen)** for the project
   (`css-mas-dev`, `css-mas-staging`, or `css-mas-prod`)
2. Click **Create host connection** → select **GitHub**
3. Authenticate with GitHub and install the Google Cloud Build app on the repo
4. Click **Link repository**, select `Saoussen-CH/customer-support-mas-ai`
5. Note the connection name (default: `github-connection`) and the repository
   resource name Cloud Build shows — it will look like:
   ```
   projects/css-mas-dev/locations/us-central1/connections/github-connection/repositories/Saoussen-CH-customer-support-mas-ai
   ```

### 14b — Or use gcloud (2nd-gen connection)

```bash
# Install the Cloud Build GitHub app first (browser OAuth), then:
gcloud builds connections create github github-connection \
  --region=us-central1 \
  --project=css-mas-dev

gcloud builds repositories create Saoussen-CH-customer-support-mas-ai \
  --connection=github-connection \
  --remote-uri=https://github.com/Saoussen-CH/customer-support-mas-ai.git \
  --region=us-central1 \
  --project=css-mas-dev
```

Repeat for `css-mas-staging` and `css-mas-prod`.

### 14c — Enable triggers via Terraform

Uncomment the GitHub variables in each `terraform/environments/<env>/terraform.tfvars`:

```hcl
github_connected           = true
cloudbuild_connection_name = "github-connection"
cloudbuild_repo_name       = "Saoussen-CH-customer-support-mas-ai"
```

Then re-apply Terraform to create the triggers:

```bash
make infra-up ENV=dev
make infra-up ENV=staging
make infra-up ENV=prod
```

**Expected triggers created per environment:**

| Environment | Trigger name | Fires on |
|---|---|---|
| dev | `ci-pull-request` | PR targeting `develop` |
| dev | `ci-cd-push-develop` | Push to `develop` |
| staging | `ci-pull-request` | PR targeting `staging` |
| staging | `ci-cd-push-staging` | Push to `staging` |
| prod | `ci-pull-request` | PR targeting `main` |
| prod | `ci-push-main` | Push to `main` |
| prod | `ci-manual` | Manual / nightly (Cloud Scheduler) |

Verify in GCP Console: **Cloud Build → Triggers** — you should see 2 triggers for dev,
2 for staging, and 3 for prod.

> **Branch strategy:** `develop` → deploys to dev, `staging` → deploys to staging,
> `main` → deploys to prod. Merge `feat/*` → `develop` → `staging` → `main` to
> promote across environments.

---

## Step 15 — Validate make switch-env works

```bash
make switch-env ENV=dev
grep GOOGLE_CLOUD_PROJECT .env   # → css-mas-dev

make switch-env ENV=staging
grep GOOGLE_CLOUD_PROJECT .env   # → css-mas-staging

make switch-env ENV=prod
grep GOOGLE_CLOUD_PROJECT .env   # → css-mas-prod

# Test error handling:
make switch-env ENV=qa           # → Error: .env.qa not found
```

---

## Step 16 — Validate Terraform targets in Makefile

```bash
make terraform-plan ENV=dev      # runs plan in terraform/environments/dev
make terraform-plan ENV=staging  # runs plan in terraform/environments/staging
make terraform-plan ENV=prod     # runs plan in terraform/environments/prod
```

---

## Checklist

- [ ] `terraform validate` passes for dev, staging, prod
- [ ] `make bootstrap-apis ENV=dev` runs without error (fresh project only)
- [ ] `make switch-env ENV=dev` correctly switches `.env`
- [ ] `make terraform-plan ENV=dev` shows expected plan (no errors)
- [ ] `make infra-up ENV=dev` creates all resources without errors
- [ ] GitHub connection created in Cloud Build console for each GCP project
- [ ] `github_connected = true` uncommented in each `terraform.tfvars`
- [ ] `make infra-up ENV=dev/staging/prod` creates Cloud Build triggers
- [ ] Triggers visible in Cloud Build → Triggers (2 for dev, 2 for staging, 3 for prod)
- [ ] `make test-tools` passes
- [ ] `make test-unit` passes
- [ ] `make test-integration` passes
- [ ] `make test-local` passes (agent responds)
- [ ] Smoke tests pass against deployed dev
- [ ] Load tests pass against deployed staging
- [ ] `GOOGLE_CLOUD_PROJECT` in `.env` switches correctly per environment

---

## If something breaks

| Symptom | Fix |
|---|---|
| `Error 403: Cloud Resource Manager API not enabled` | Run `make bootstrap-apis ENV=dev`, wait 30s, retry |
| `403 aiplatform.googleapis.com requires a quota project` | Run `gcloud auth application-default set-quota-project css-mas-dev` |
| `terraform validate` fails | Check module path in `environments/dev/main.tf` → `source = "../../modules/core"` |
| `google_managed_sas_exist = false` errors | Leave it `false` until after first Agent Engine deploy |
| No triggers in Cloud Build after `make infra-up` | `github_connected` is still `false` (default) — follow Step 14 to create the GitHub connection, then uncomment `github_connected = true` in tfvars and re-apply |
| `github_connected = false` — triggers not created | Expected until you complete Step 14 — Cloud Build GitHub connection must be created manually (requires OAuth) before Terraform can create triggers |
| Agent Engine deploy fails | Check `.env` has correct `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_STORAGE_BUCKET` |
| `403 Missing or insufficient permissions` on tool calls | Set `google_managed_sas_exist = true` in `terraform.tfvars` and re-run `make infra-up ENV=dev` — the Agent Engine SA needs `roles/datastore.user` |
| "violates our safety policy" on normal queries | Model Armor pi_and_jailbreak filter confidence was too low — re-run `make infra-up ENV=dev` to apply updated `MEDIUM_AND_ABOVE` thresholds |
| `No response text extracted` in Cloud Run logs | Check Agent Engine logs: `gcloud logging read 'resource.type="aiplatform.googleapis.com/ReasoningEngine"' --project=PROJECT_ID --limit=20` |
| Smoke tests fail with 503 | Wait 2-3 min after deploy for cold start, then retry |
| Model Armor template not found | Run `terraform output model_armor_template_name` and copy into `.env.dev` |
