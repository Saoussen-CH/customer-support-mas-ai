# Local Testing Guide — Multi-Environment Terraform

This guide covers how to test the `feat/multi-env-terraform` branch locally
before pushing or merging anything.

---

## Prerequisites

- Terraform installed (`terraform -v`)
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- 3 GCP projects created: `css-mas-dev`, `css-mas-staging`, `css-mas-prod`
- Python + `uv` installed (`pip install uv`)
- Repo cloned and dependencies installed (`make install`)

---

## Step 1 — Switch to the feature branch

```bash
git checkout feat/multi-env-terraform
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

Copy `model_armor_template_id` into `.env.dev` → `MODEL_ARMOR_TEMPLATE_ID=...`

---

## Step 8 — Authenticate and test GCP access

```bash
make switch-env ENV=dev
gcloud config set project css-mas-dev
gcloud auth application-default login
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
make deploy-agent-engine
```

After deploy completes, copy the resource name printed at the end into:
- `.env.dev` → `AGENT_ENGINE_RESOURCE_NAME=projects/.../reasoningEngines/...`
- `terraform/environments/dev/terraform.tfvars` → uncomment `agent_engine_resource_name = "..."`

Then re-apply Terraform to wire the resource name into Cloud Run:

```bash
make infra-up ENV=dev
```

Deploy Cloud Run:

```bash
make deploy-cloud-run
```

---

## Step 12 — Run smoke tests against dev

After Cloud Run is deployed:

```bash
export CLOUD_RUN_URL=$(gcloud run services describe customer-support-app \
  --region us-central1 --project css-mas-dev \
  --format="value(status.url)")

CLOUD_RUN_URL=$CLOUD_RUN_URL uv run pytest tests/smoke/ -v
```

**Expected:** All 6 smoke tests pass.

---

## Step 13 — Run load tests against staging (staging only)

After deploying to staging (`make switch-env ENV=staging` + repeat steps 4-10):

```bash
export CLOUD_RUN_URL=$(gcloud run services describe customer-support-app \
  --region us-central1 --project css-mas-staging \
  --format="value(status.url)")

uv run locust -f tests/load/locustfile.py \
  --headless --users 5 --spawn-rate 1 --run-time 2m \
  --host $CLOUD_RUN_URL \
  --csv /tmp/load-results \
  --exit-code-on-error 1

uv run python tests/load/check_slos.py /tmp/load-results_stats.csv
```

**Expected:** Locust finishes, SLO checker exits 0 (all SLOs met).

---

## Step 14 — Validate make switch-env works

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

## Step 15 — Validate Terraform targets in Makefile

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
| `terraform validate` fails | Check module path in `environments/dev/main.tf` → `source = "../../modules/core"` |
| `google_managed_sas_exist = false` errors | Leave it `false` until after first Agent Engine deploy |
| `github_connected = false` — triggers not created | Expected — connect GitHub in Cloud Build console first, then set `true` in tfvars |
| Agent Engine deploy fails | Check `.env` has correct `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_STORAGE_BUCKET` |
| Smoke tests fail with 503 | Wait 2-3 min after deploy for cold start, then retry |
| Model Armor template not found | Run `terraform output model_armor_template_id` and copy into `.env` |
