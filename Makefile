# ==============================================================================
# Customer Support MAS — Makefile
# ==============================================================================
# Usage:
#   make <target>
#   make help          List all available targets
#
# Override defaults with environment variables or inline:
#   make test-unit EVAL_PROFILE=standard
#   make eval-post-deploy AGENT_ENGINE_ID=1234567890
# ==============================================================================

# ------------------------------------------------------------------------------
# Defaults (override from environment or command line)
# ------------------------------------------------------------------------------
PYTHON        ?= uv run python
PYTEST        ?= uv run pytest
EVAL_PROFILE  ?= fast
AGENT         ?= product
AGENT_ENGINE_ID ?=
DELAY         ?= 5
SUITE         ?=

PYTHON_VERSION := 3.11
PYTEST_FLAGS   := -v --tb=short

# Common env vars required by all Vertex AI / Firestore steps
COMMON_ENV := GOOGLE_GENAI_USE_VERTEXAI=True

# ------------------------------------------------------------------------------
# Phony targets
# ------------------------------------------------------------------------------
.PHONY: help \
        install setup-gcp setup-firestore setup-cloud-build \
        setup-model-armor create-model-armor-template test-model-armor \
        seed-db add-embeddings vector-index \
        lint format \
        test-tools test-unit test-integration test \
        gen-evalset gen-integration-evalset \
        eval-post-deploy \
        frontend-install frontend-build frontend-dev \
        deploy-agent-engine test-local \
        deploy-cloud-run submit-build nightly

# ==============================================================================
# HELP
# ==============================================================================

help: ## Show this help message
	@echo ""
	@echo "Customer Support MAS — available targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make test                              # run all tests (EVAL_PROFILE=fast)"
	@echo "  make test-unit EVAL_PROFILE=standard   # unit eval with standard profile"
	@echo "  make gen-evalset AGENT=order           # generate order agent eval dataset"
	@echo "  make eval-post-deploy AGENT_ENGINE_ID=1234567890"
	@echo "  make nightly                                    # run all steps (post-deploy off)"
	@echo "  make nightly RUN_INTEGRATION_TESTS=false RUN_POST_DEPLOY_EVAL=true"
	@echo ""

# ==============================================================================
# SETUP
# ==============================================================================

install: ## Install Python deps + pre-commit hooks (uses uv)
	pip install uv --quiet
	uv sync --frozen --group dev
	uv run pre-commit install
	@echo "Done. Run 'make setup-gcp' next if setting up GCP for the first time."

setup-gcp: ## Enable GCP APIs and configure IAM (reads .env)
	bash scripts/setup_gcp.sh

setup-firestore: ## Create Firestore database and seed sample data
	bash scripts/setup_firestore.sh

setup-cloud-build: ## Configure Cloud Build IAM, Artifact Registry, and Secret Manager
	@PROJECT_ID="$(PROJECT_ID)"; \
	REGION="$(REGION)"; \
	STAGING_BUCKET="$(STAGING_BUCKET)"; \
	if [ -f .env ]; then \
		if [ -z "$$PROJECT_ID" ];     then PROJECT_ID=$$(grep '^GOOGLE_CLOUD_PROJECT='           .env | cut -d= -f2-); fi; \
		if [ -z "$$REGION" ];         then REGION=$$(grep '^GOOGLE_CLOUD_LOCATION='              .env | cut -d= -f2-); fi; \
		if [ -z "$$STAGING_BUCKET" ]; then STAGING_BUCKET=$$(grep '^GOOGLE_CLOUD_STORAGE_BUCKET=' .env | cut -d= -f2- | sed 's|gs://||'); fi; \
	fi; \
	if [ -z "$$PROJECT_ID" ] || [ -z "$$REGION" ] || [ -z "$$STAGING_BUCKET" ]; then \
		echo "Error: PROJECT_ID, REGION, and STAGING_BUCKET are required."; \
		echo "Add them to .env or pass inline: make setup-cloud-build PROJECT_ID=<id> REGION=<region> STAGING_BUCKET=<bucket>"; \
		exit 1; \
	fi; \
	GITHUB_OWNER_ARG="$(GITHUB_OWNER)"; \
	if [ -z "$$GITHUB_OWNER_ARG" ] && [ -f .env ]; then \
		GITHUB_OWNER_ARG=$$(grep '^GITHUB_OWNER=' .env | cut -d= -f2- || echo ""); \
	fi; \
	bash scripts/setup-cloud-build.sh "$$PROJECT_ID" "$$REGION" "$$STAGING_BUCKET" "$$GITHUB_OWNER_ARG"

setup-model-armor: ## Enable Model Armor and configure floor settings
	@ARGS=""; \
	if [ -n "$(MODE)" ]; then ARGS="$$ARGS --mode $(MODE)"; fi; \
	if [ -n "$(CREATE_TEMPLATE)" ]; then ARGS="$$ARGS --create-template"; fi; \
	bash scripts/setup_model_armor.sh $$ARGS

create-model-armor-template: ## Create Model Armor template via Python SDK (use when gcloud model-armor is unavailable)
	PYTHONPATH=. $(PYTHON) scripts/create_model_armor_template.py

test-model-armor: ## Smoke test Model Armor API (safe + unsafe prompts)
	PYTHONPATH=. $(PYTHON) scripts/test_model_armor.py

seed-db: ## Seed Firestore with sample products, orders, invoices, users
	set -a && . ./.env && set +a && PYTHONPATH=. $(PYTHON) -m customer_support_agent.database.seed \
		--project $(shell grep GOOGLE_CLOUD_PROJECT .env | cut -d= -f2) \
		--database $(shell grep FIRESTORE_DATABASE .env | cut -d= -f2 || echo customer-support-db)

add-embeddings: ## Add vector embeddings to Firestore products (for RAG)
	set -a && . ./.env && set +a && PYTHONPATH=. $(PYTHON) scripts/add_embeddings.py \
		--project $(shell grep GOOGLE_CLOUD_PROJECT .env | cut -d= -f2) \
		--database $(shell grep FIRESTORE_DATABASE .env | cut -d= -f2 || echo customer-support-db) \
		--location $(shell grep GOOGLE_CLOUD_LOCATION .env | cut -d= -f2 || echo us-central1)

vector-index: ## Create Firestore vector index for semantic search
	set -a && . ./.env && set +a && PYTHONPATH=. $(PYTHON) scripts/create_vector_index.py

# ==============================================================================
# LINT & FORMAT
# ==============================================================================

lint: ## Check code style (ruff check + ruff format --check)
	ruff check customer_support_agent/ --ignore=E501
	ruff format customer_support_agent/ --check

format: ## Auto-fix formatting with ruff
	ruff format customer_support_agent/
	ruff check customer_support_agent/ --fix --ignore=E501

# ==============================================================================
# TESTS
# ==============================================================================

test-tools: ## Run pure tool tests (no LLM, mocked Firestore) — fast
	$(COMMON_ENV) $(PYTEST) \
		tests/unit/test_tools.py \
		tests/unit/test_mock_rag.py \
		tests/unit/test_refund_standalone.py \
		$(PYTEST_FLAGS)

test-unit: ## Run unit agent eval (EVAL_PROFILE=fast|standard|full)
	$(COMMON_ENV) EVAL_PROFILE=$(EVAL_PROFILE) $(PYTEST) \
		tests/unit/test_agent_eval_ci.py \
		$(PYTEST_FLAGS)

test-integration: ## Run integration eval (EVAL_PROFILE=fast|standard|full, TEST=test_name to filter)
	$(COMMON_ENV) EVAL_PROFILE=$(EVAL_PROFILE) $(PYTEST) \
		tests/integration/test_integration_eval_ci.py \
		$(if $(TEST),-k $(TEST),) \
		$(PYTEST_FLAGS)

test: test-tools test-unit test-integration ## Run all tests (EVAL_PROFILE=fast by default)

# ==============================================================================
# EVAL DATASET GENERATION
# ==============================================================================

gen-evalset: ## Generate unit eval dataset — AGENT=product|order|billing (default: product)
	@ARGS="--agent $(AGENT) --delay $(DELAY)"; \
	if [ -n "$(DRY_RUN)" ]; then ARGS="$$ARGS --dry-run"; fi; \
	PYTHONPATH=. $(PYTHON) scripts/generate_eval_dataset.py $$ARGS

gen-integration-evalset: ## Generate integration eval dataset
	@ARGS="--delay $(DELAY)"; \
	if [ -n "$(SUITE)" ]; then ARGS="$$ARGS --suite $(SUITE)"; fi; \
	if [ -n "$(DRY_RUN)" ]; then ARGS="$$ARGS --dry-run"; fi; \
	PYTHONPATH=. $(PYTHON) scripts/generate_integration_evalset.py $$ARGS

# ==============================================================================
# POST-DEPLOY EVALUATION
# ==============================================================================

eval-post-deploy: ## Evaluate deployed Agent Engine (AGENT_ENGINE_ID or AGENT_ENGINE_RESOURCE_NAME required)
	@# Prefer AGENT_ENGINE_RESOURCE_NAME (full path) over AGENT_ENGINE_ID (numeric short ID)
	@AGENT_ID="$(AGENT_ENGINE_RESOURCE_NAME)"; \
	if [ -z "$$AGENT_ID" ]; then AGENT_ID="$(AGENT_ENGINE_ID)"; fi; \
	if [ -z "$$AGENT_ID" ] && [ -f .env ]; then \
		AGENT_ID=$$(grep '^AGENT_ENGINE_RESOURCE_NAME=' .env | cut -d= -f2-); \
	fi; \
	if [ -z "$$AGENT_ID" ]; then \
		echo "Error: AGENT_ENGINE_ID or AGENT_ENGINE_RESOURCE_NAME is required."; \
		echo "Usage: make eval-post-deploy AGENT_ENGINE_ID=<id> [EVAL_PROFILE=standard]"; \
		echo "  or:  make eval-post-deploy AGENT_ENGINE_RESOURCE_NAME=projects/P/locations/L/reasoningEngines/ID"; \
		echo "  Tip: set AGENT_ENGINE_RESOURCE_NAME in your .env to use the full resource name automatically."; \
		exit 1; \
	fi; \
	PYTHONPATH=. $(PYTHON) scripts/eval_vertex.py \
		--agent-engine-id "$$AGENT_ID" \
		--profile $(if $(filter fast,$(EVAL_PROFILE)),standard,$(EVAL_PROFILE)) \
		--delay $(DELAY)

# ==============================================================================
# FRONTEND
# ==============================================================================

# ==============================================================================
# TERRAFORM — Infrastructure as Code
# ==============================================================================

terraform-init: ## Initialize Terraform (run once, or after adding providers)
	cd terraform && terraform init

terraform-plan: ## Preview infrastructure changes (requires terraform.tfvars)
	cd terraform && terraform plan -var-file=terraform.tfvars

terraform-apply: ## Apply infrastructure changes
	cd terraform && terraform apply -var-file=terraform.tfvars

terraform-destroy: ## Destroy all Terraform-managed infrastructure (DESTRUCTIVE)
	@echo "WARNING: This will destroy the Firestore database, GCS bucket, AR repo, and all IAM bindings."
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	cd terraform && terraform destroy -var-file=terraform.tfvars

infra-up: terraform-init terraform-apply ## Bootstrap: initialize and apply Terraform (first-time setup)

# ==============================================================================
# FRONTEND
# ==============================================================================

frontend-install: ## Install frontend npm dependencies
	cd frontend && npm ci

frontend-build: ## Build React frontend for production
	cd frontend && npm run build

frontend-dev: ## Start frontend dev server (hot reload)
	cd frontend && npm start

# ==============================================================================
# DEPLOYMENT
# ==============================================================================

test-local: ## Run agent locally to verify before deploying
	PYTHONPATH=. $(PYTHON) deployment/deploy.py --action test_local

deploy-agent-engine: ## Deploy agent to Vertex AI Agent Engine
	PYTHONPATH=. $(PYTHON) deployment/deploy.py --action deploy

deploy-cloud-run: ## Build and deploy backend to Cloud Run
	bash deployment/deploy-cloudrun.sh

nightly: ## Trigger ci-manual Cloud Build with selective step flags
	@# Defaults: all steps on, post-deploy off. Override with RUN_LINT=false, RUN_UNIT_TESTS=false, etc.
	@# RUN_POST_DEPLOY_EVAL=true requires AGENT_ENGINE_ID (or AGENT_ENGINE_RESOURCE_NAME in .env)
	@PROJECT_ID=$$(grep '^GOOGLE_CLOUD_PROJECT=' .env | cut -d= -f2-); \
	STAGING_BUCKET=$$(grep '^GOOGLE_CLOUD_STORAGE_BUCKET=' .env | cut -d= -f2-); \
	RUN_LINT_VAL="$(if $(RUN_LINT),$(RUN_LINT),true)"; \
	RUN_TOOL_VAL="$(if $(RUN_TOOL_TESTS),$(RUN_TOOL_TESTS),true)"; \
	RUN_UNIT_VAL="$(if $(RUN_UNIT_TESTS),$(RUN_UNIT_TESTS),true)"; \
	RUN_INT_VAL="$(if $(RUN_INTEGRATION_TESTS),$(RUN_INTEGRATION_TESTS),true)"; \
	RUN_PD_VAL="$(if $(RUN_POST_DEPLOY_EVAL),$(RUN_POST_DEPLOY_EVAL),false)"; \
	AGENT_ID="$(AGENT_ENGINE_ID)"; \
	if [ -z "$$AGENT_ID" ] && [ -f .env ]; then \
		AGENT_ID=$$(grep '^AGENT_ENGINE_RESOURCE_NAME=' .env | cut -d= -f2-); \
	fi; \
	gcloud builds triggers run ci-manual \
		--project="$$PROJECT_ID" \
		--region=us-central1 \
		--branch=main \
		--substitutions="_RUN_LINT=$$RUN_LINT_VAL,_RUN_TOOL_TESTS=$$RUN_TOOL_VAL,_RUN_UNIT_TESTS=$$RUN_UNIT_VAL,_RUN_INTEGRATION_TESTS=$$RUN_INT_VAL,_RUN_POST_DEPLOY_EVAL=$$RUN_PD_VAL,_AGENT_ENGINE_ID=$$AGENT_ID,_STAGING_BUCKET=$$STAGING_BUCKET"

submit-build: ## Submit full CI+CD pipeline to Cloud Build (DEPLOY_AGENT_ENGINE=true to also redeploy agent)
	@PROJECT_ID=$$(grep '^GOOGLE_CLOUD_PROJECT=' .env | cut -d= -f2-); \
	STAGING_BUCKET=$$(grep '^GOOGLE_CLOUD_STORAGE_BUCKET=' .env | cut -d= -f2-); \
	AGENT_ENGINE_RESOURCE_NAME=$$(grep '^AGENT_ENGINE_RESOURCE_NAME=' .env | cut -d= -f2-); \
	AGENT_ENGINE_DISPLAY_NAME=$$(grep '^AGENT_ENGINE_DISPLAY_NAME=' .env | cut -d= -f2-); \
	COMMIT_SHA=$$(git rev-parse HEAD); \
	gcloud builds submit . \
		--config cloudbuild/cloudbuild-deploy.yaml \
		--project "$$PROJECT_ID" \
		--substitutions "COMMIT_SHA=$$COMMIT_SHA,_STAGING_BUCKET=$$STAGING_BUCKET,_AGENT_ENGINE_RESOURCE_NAME=$$AGENT_ENGINE_RESOURCE_NAME,_AGENT_ENGINE_DISPLAY_NAME=$$AGENT_ENGINE_DISPLAY_NAME,_DEPLOY_AGENT_ENGINE=$(if $(DEPLOY_AGENT_ENGINE),$(DEPLOY_AGENT_ENGINE),false),_EVAL_PROFILE=$(EVAL_PROFILE)"
