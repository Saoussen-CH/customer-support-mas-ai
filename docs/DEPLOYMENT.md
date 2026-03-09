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

## Step 3 — Terraform (infrastructure bootstrap)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` — the three required fields:

```hcl
project_id          = "your-gcp-project-id"
staging_bucket_name = "your-project-id-staging"   # must be globally unique
github_owner        = "your-github-username-or-org"
```

Run:

```bash
cd ..          # back to project root
make infra-up  # terraform init + apply
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

## Step 4 — Update .env from Terraform outputs

```bash
cd terraform && terraform output && cd ..
```

Copy the values into `.env`:

| Terraform output | .env variable |
|-----------------|---------------|
| `staging_bucket` | `GOOGLE_CLOUD_STORAGE_BUCKET=gs://<value>` |
| `firestore_database_id` | `FIRESTORE_DATABASE=<value>` |
| `model_armor_template_name` | `MODEL_ARMOR_TEMPLATE_ID=<value>` |

---

## Step 5 — Install Python dependencies

```bash
make install
```

---

## Step 6 — Seed Firestore

```bash
make seed-db          # load demo products, orders, users, invoices
make add-embeddings   # add vector embeddings for RAG semantic search
```

> `add-embeddings` can take a few minutes. The Firestore vector index must be
> READY first — Terraform creates it automatically.

---

## Step 7 — Connect GitHub to Cloud Build

One-time manual step in the GCP Console (cannot be automated):

1. Go to **Cloud Build → Triggers**
2. Click **Connect Repository**
3. Select **GitHub** and authorize
4. Choose your repository (`Saoussen-CH/customer-support-mas-ai`)
5. Click **Done** (do not create a trigger from the wizard)

Then enable trigger creation in Terraform:

```bash
# In terraform/terraform.tfvars, set:
github_connected = true
```

```bash
make infra-up
```

This creates all 4 CI/CD triggers linked to your repository.

---

## Step 8 — Deploy Agent Engine (first time)

```bash
make deploy-agent-engine
```

This creates the Agent Engine on Vertex AI. At the end it prints the resource
name — copy it into `.env`:

```bash
AGENT_ENGINE_RESOURCE_NAME=projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID
```

---

## Step 9 — Re-run GCP setup to grant Agent Engine SA permissions

The Agent Engine service account (`gcp-sa-aiplatform-re`) is created by
Google on first Agent Engine deployment — it does not exist before that.
Re-run setup now that it exists:

```bash
make setup-gcp
```

---

## Step 10 — Push to main (deploys Cloud Run via CI/CD)

```bash
git push
```

The Cloud Build trigger fires and runs the full pipeline:

```
install → lint + tool-tests → unit-tests → integration-tests
  → docker-build → docker-push
    → deploy-agent-engine (skipped — no agent code changed)
      → deploy-cloud-run
        → smoke-test
```

Get the Cloud Run URL:

```bash
gcloud run services describe customer-support-app \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## Step 11 — Test

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

## Subsequent deployments

| Scenario | Command |
|----------|---------|
| Agent code changed | `git push` — CI auto-detects, redeploys Agent Engine |
| Backend/frontend only | `git push` — Agent Engine deploy skipped |
| Force Agent Engine redeploy | `make submit-build DEPLOY_AGENT_ENGINE=true` |
| Manual build without push | `make submit-build` |

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
make infra-up              # terraform init + apply
make terraform-plan        # preview infrastructure changes
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
service account only exists after the first deployment.

**Cloud Run returns 403**
`gcloud run deploy --allow-unauthenticated` in the pipeline sets
`allUsers roles/run.invoker` automatically. For manual deploys:
```bash
gcloud run services add-iam-policy-binding customer-support-app \
  --region=us-central1 --member=allUsers --role=roles/run.invoker
```

---

## See also

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system design and components
- [CI_CD.md](./CI_CD.md) — CI/CD pipeline details and trigger setup
- [ENV_SETUP.md](./ENV_SETUP.md) — full .env variable reference
