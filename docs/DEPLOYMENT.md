# Deployment Guide

End-to-end setup for a new user starting from a fresh clone.

## Prerequisites

Install these tools before starting:

| Tool | Version | Install |
|------|---------|---------|
| `gcloud` CLI | latest | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| Terraform | >= 1.5 | [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform/install) |
| Python | 3.11 | [python.org](https://www.python.org/downloads/) |
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) (local dev only) |

---

## Step 1 — Authenticate and clone

```bash
gcloud auth login
gcloud auth application-default login

git clone https://github.com/Saoussen-CH/customer-support-mas-ai.git
cd customer-support-mas-ai
```

---

## Step 2 — Configure .env

```bash
cp .env.example .env
```

Fill in the required fields:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
FIRESTORE_DATABASE=customer-support-db
MODEL_ARMOR_ENABLED=true   # recommended
```

Leave `GOOGLE_CLOUD_STORAGE_BUCKET`, `AGENT_ENGINE_RESOURCE_NAME`, and
`MODEL_ARMOR_TEMPLATE_ID` blank for now — they come from Terraform output.

---

## Step 3 — Bootstrap GCP project

```bash
make setup-gcp
```

This enables required APIs and grants IAM roles to the Cloud Run and Cloud Build
service accounts.

---

## Step 4 — Terraform (infrastructure bootstrap)

```bash
cd terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` — the three required fields:

```hcl
project_id          = "your-gcp-project-id"
staging_bucket_name = "your-project-id-staging"   # must be globally unique
github_owner        = "your-github-username-or-org"
```

Run from the project root:

```bash
cd ../../..    # back to project root
make bootstrap-apis ENV=prod   # enable Cloud Resource Manager API — once per new project
# wait ~30 seconds
make infra-up  # terraform init + apply (defaults to terraform/environments/prod)
```

Terraform creates:
- GCS staging bucket
- Artifact Registry repository
- Firestore database
- Cloud Build triggers (push-to-main + nightly)
- All IAM bindings (Cloud Run SA, Agent Engine SA, Cloud Build SA)
- Model Armor template + floor settings (if `model_armor_enabled = true`)
- Cloud Scheduler nightly job

---

## Step 5 — Update .env from Terraform outputs

```bash
cd terraform/environments/prod && terraform output && cd ../../..
```

Copy the values into `.env`:

| Terraform output | .env variable |
|-----------------|---------------|
| `staging_bucket` | `GOOGLE_CLOUD_STORAGE_BUCKET=gs://<value>` |
| `firestore_database_id` | `FIRESTORE_DATABASE=<value>` |
| `model_armor_template_name` | `MODEL_ARMOR_TEMPLATE_ID=<value>` |

---

## Step 6 — Install Python dependencies, seed Firestore, add embeddings

```bash
make install
make seed-db          # load demo products, orders, users, invoices
make add-embeddings   # add vector embeddings for RAG semantic search
```

> `add-embeddings` can take a few minutes. The Firestore vector index must be
> READY first — Terraform creates it automatically.

---

## Step 7 — Connect GitHub to Cloud Build (2nd gen)

One-time manual step in the GCP Console (cannot be automated):

1. Go to **Cloud Build → Repositories (2nd gen)**
2. Click **Create host connection** → select **GitHub** → authorize → name it `github-connection` (region: `us-central1`)
3. Click **Link Repository** → select `Saoussen-CH/customer-support-mas-ai` → click **Link**
4. Confirm the linked repo name:
   ```bash
   gcloud builds repositories list --connection=github-connection \
     --region=us-central1 --project=YOUR_PROJECT_ID
   ```
   Cloud Build slugifies the name, e.g. `Saoussen-CH-customer-support-mas-ai`

Then enable trigger creation in Terraform:

```hcl
# In terraform/environments/prod/terraform.tfvars:
github_connected           = true
cloudbuild_connection_name = "github-connection"
cloudbuild_repo_name       = "Saoussen-CH-customer-support-mas-ai"  # from step above
```

```bash
make infra-up
```

This creates all CI/CD triggers. **Note:** Cloud Build 2nd gen triggers require
`service_account` — this is set automatically by Terraform to the Cloud Build SA.

---

## Step 8 — Deploy Agent Engine (first time)

```bash
make deploy-agent-engine
```

This creates the Agent Engine on Vertex AI. At the end it prints the resource
name — copy it into both `.env` and `terraform/environments/prod/terraform.tfvars`:

**.env:**
```bash
AGENT_ENGINE_RESOURCE_NAME=projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID
```

**terraform/environments/prod/terraform.tfvars:**
```hcl
agent_engine_resource_name = "projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID"
```

Then re-apply Terraform so the Cloud Run service picks up the new value:

```bash
make infra-up
```

---

## Step 9 — Grant Agent Engine SA permissions

The Agent Engine service account (`gcp-sa-aiplatform-re`) is created by Google
on first Agent Engine deployment — it does not exist before that. Re-run setup
now that it exists, then set `google_managed_sas_exist = true` and re-apply:

```bash
make setup-gcp
```

In `terraform/environments/prod/terraform.tfvars`:

```hcl
google_managed_sas_exist = true
```

```bash
make infra-up
```

---

## Step 10 — Deploy

Push to `main` and let the CI/CD pipeline handle the deployment:

```bash
git push
```

The Cloud Build trigger fires and runs the full pipeline:

```
install → lint + tool-tests → unit-tests → integration-tests
  → docker-build → docker-push
    → deploy-agent-engine (skipped — no agent code changed)
      → deploy-cloud-run
        → get-service-url
          → smoke-test
```

Alternatively, deploy Cloud Run directly without CI/CD:

```bash
make deploy-cloud-run
```

Get the Cloud Run URL:

```bash
gcloud run services describe customer-support-app \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## Step 11 — Verify with smoke tests

```bash
uv sync --group dev
CLOUD_RUN_URL=https://your-cloud-run-url pytest tests/smoke/ -v
```

The smoke suite runs 6 checks: health endpoint, agent responds, product tool,
order tool, Model Armor filtering, and session continuity.

---

## Step 12 — Try it

Demo accounts (pre-seeded by `make seed-db`):

| Email | Password | Profile |
|-------|----------|---------|
| `demo@example.com` | `demo123` | Gold tier, has order history |
| `jane@example.com` | `jane123` | Silver tier, has order history |

Try these prompts:
- `Where is my order ORD-12345?`
- `Search for gaming laptops`
- `Ignore all previous instructions...` — blocked by Model Armor

---

## Multi-environment setup

The project supports three environments backed by separate GCP projects and
Terraform state. Each environment has its own directory under
`terraform/environments/`.

| Environment | Directory | Branch | Model Armor | Load tests |
|-------------|-----------|--------|-------------|------------|
| `dev` | `terraform/environments/dev` | `develop` | INSPECT_ONLY | No |
| `staging` | `terraform/environments/staging` | `staging` | INSPECT_AND_BLOCK | Yes |
| `prod` | `terraform/environments/prod` | `main` | INSPECT_AND_BLOCK | No |

Per-environment differences:

| Setting | dev | staging | prod |
|---------|-----|---------|------|
| Model Armor mode | INSPECT_ONLY | INSPECT_AND_BLOCK | INSPECT_AND_BLOCK |
| Firestore delete protection | disabled | enabled | enabled |
| GCS force_destroy | true | false | false |
| Nightly scheduler | No | No | Yes |
| Load tests in CI | No | Yes | No |

### Bootstrapping dev or staging

Follow the same steps as prod but target the appropriate environment directory
and pass `ENV=dev` or `ENV=staging` to make targets.

On a fresh GCP project, enable the Cloud Resource Manager API first (required
before Terraform can read project metadata):

```bash
# Bootstrap dev
cd terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
# fill in terraform.tfvars (project_id, staging_bucket_name, github_owner)
cd ../../..
make bootstrap-apis ENV=dev   # enable Cloud Resource Manager API — once per new project
# wait ~30 seconds
make infra-up ENV=dev

# Bootstrap staging
cd terraform/environments/staging
cp terraform.tfvars.example terraform.tfvars
# fill in terraform.tfvars
cd ../../..
make bootstrap-apis ENV=staging
# wait ~30 seconds
make infra-up ENV=staging
```

Shared infrastructure code lives in `terraform/modules/core/`.

---

## Subsequent deployments

| Scenario | Command |
|----------|---------|
| Agent code changed | `git push` — CI auto-detects, redeploys Agent Engine |
| Backend/frontend only | `git push` — Agent Engine deploy skipped |
| Force Agent Engine redeploy | `make submit-build DEPLOY_AGENT_ENGINE=true` |
| Manual build without push | `make submit-build` |
| Deploy to dev | Push to `develop` branch |
| Deploy to staging | Push to `staging` branch |
| Deploy to prod | Push to `main` branch |

---

## Useful make targets

```bash
make test                  # run all tests locally (EVAL_PROFILE=fast)
make test-local            # run agent locally before deploying
make test-model-armor      # smoke test Model Armor (safe + unsafe prompts)
make lint                  # ruff check
make format                # ruff auto-fix
make seed-db               # re-seed Firestore
make deploy-agent-engine   # deploy/update Agent Engine only
make deploy-cloud-run      # deploy Cloud Run directly
make bootstrap-apis ENV=dev  # enable Cloud Resource Manager API (fresh project only)
make infra-up                # terraform init + apply (prod by default)
make infra-up ENV=staging    # apply staging environment
make infra-up ENV=dev        # apply dev environment
make terraform-plan          # preview infrastructure changes
```

---

## Troubleshooting

**Agent Engine rate limit (`FAILED_PRECONDITION: Rate exceeded`)**
Wait 1–2 minutes — rate limits are per-minute quotas. The circuit breaker
will not trip on rate limit errors, only on actual outages.

**Model Armor not blocking prompts**
Check Cloud Run startup logs for `Model Armor init failed`. Ensure
`MODEL_ARMOR_TEMPLATE_ID` is set in the Cloud Run environment. Set it via
`_MODEL_ARMOR_TEMPLATE_ID` substitution or add it to the trigger.

**Agent Engine SA missing Firestore permissions**
Run `make setup-gcp` after the first `make deploy-agent-engine`. The `-re`
service account only exists after the first deployment. Then set
`google_managed_sas_exist = true` in `terraform.tfvars` and run `make infra-up`.

**Cloud Run returns 403**
`gcloud run deploy --allow-unauthenticated` in the pipeline sets
`allUsers roles/run.invoker` automatically. For manual deploys:
```bash
gcloud run services add-iam-policy-binding customer-support-app \
  --region=us-central1 --member=allUsers --role=roles/run.invoker
```

**Smoke tests failing after deploy**
Get the Cloud Run URL and run tests manually to see the failure:
```bash
CLOUD_RUN_URL=$(gcloud run services describe customer-support-app \
  --region=us-central1 --format='value(status.url)')
uv sync --group dev
CLOUD_RUN_URL=$CLOUD_RUN_URL pytest tests/smoke/ -v
```

---

## See also

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system design and components
- [CI_CD.md](./CI_CD.md) — CI/CD pipeline details and trigger setup
- [ENV_SETUP.md](./ENV_SETUP.md) — full .env variable reference
