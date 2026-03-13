# ==============================================================================
# CI/CD — Cloud Build triggers (2nd gen) + Cloud Scheduler nightly job
# ==============================================================================
# Trigger strategy by environment:
#   dev     — PR checks + terraform plan on PRs to develop
#             push to develop → terraform apply + app deploy
#   staging — same, targeting staging branch and css-mas-staging project
#   prod    — same, targeting main branch and css-mas-prod project
#             Also: nightly eval + Cloud Scheduler + release trigger (tag push)

locals {
  repo_resource = "projects/${var.project_id}/locations/${var.region}/connections/${var.cloudbuild_connection_name}/repositories/${var.cloudbuild_repo_name}"
  is_dev        = var.environment == "dev"
  is_staging    = var.environment == "staging"
  is_prod       = var.environment == "prod"

  # Which branch each environment watches
  deploy_branch = local.is_prod ? "^main$" : (local.is_staging ? "^staging$" : "^develop$")

  # Terraform state bucket — use explicit var or fall back to convention
  tfstate_bucket = var.tfstate_bucket_name != "" ? var.tfstate_bucket_name : "${var.project_id}-tf-state"

  # Environment directory used by terraform-plan and terraform-apply triggers
  env_directory = "terraform/environments/${var.environment}"

  # Shared deploy substitutions for app deploy triggers
  deploy_substitutions = {
    _EVAL_PROFILE               = "standard"
    _GOOGLE_CLOUD_LOCATION      = var.region
    _REGION                     = var.region
    _FIRESTORE_DATABASE         = var.firestore_database_id
    _SERVICE_NAME               = var.cloud_run_service_name
    _AR_REPO                    = var.ar_repo_name
    _STAGING_BUCKET             = "gs://${var.staging_bucket_name}"
    _MODEL_ARMOR_ENABLED        = tostring(var.model_armor_enabled)
    _MODEL_ARMOR_TEMPLATE_ID    = var.model_armor_enabled ? google_model_armor_template.customer_support_policy[0].name : ""
    _AGENT_ENGINE_RESOURCE_NAME = var.agent_engine_resource_name
    _RUN_LOAD_TESTS             = tostring(local.is_staging)
  }

  # Shared terraform substitutions for plan and apply triggers
  terraform_substitutions = {
    _ENV_DIRECTORY   = local.env_directory
    _ENVIRONMENT     = var.environment
    _TF_STATE_BUCKET = local.tfstate_bucket
  }
}

# ==============================================================================
# APP CI/CD TRIGGERS
# ==============================================================================

# PR checks — fast eval + lint on every PR targeting the environment's deploy branch
resource "google_cloudbuild_trigger" "pr_checks" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-pull-request"
  description     = "PR checks: fast eval + lint (EVAL_PROFILE=fast) [${var.environment}]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    pull_request {
      branch          = local.deploy_branch
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
    }
  }

  filename = "cloudbuild/pr-checks.yaml"

  substitutions = {
    _GOOGLE_CLOUD_LOCATION = var.region
    _FIRESTORE_DATABASE    = var.firestore_database_id
  }

  depends_on = [google_project_service.apis]
}

# Dev: push to develop → full CI+CD deploy to dev project
resource "google_cloudbuild_trigger" "push_develop" {
  count           = var.github_connected && local.is_dev ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-cd-push-develop"
  description     = "CI + CD: standard eval + deploy on push to develop [dev]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push { branch = "^develop$" }
  }

  filename    = "cloudbuild/cloudbuild-deploy.yaml"
  substitutions = local.deploy_substitutions
  depends_on  = [google_project_service.apis]
}

# Staging: push to staging branch → full CI+CD deploy to staging project
resource "google_cloudbuild_trigger" "push_staging" {
  count           = var.github_connected && local.is_staging ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-cd-push-staging"
  description     = "CI + CD: standard eval + deploy on push to staging [staging]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push { branch = "^staging$" }
  }

  filename    = "cloudbuild/cloudbuild-deploy.yaml"
  substitutions = local.deploy_substitutions
  depends_on  = [google_project_service.apis]
}

# Prod: push to main → full CI+CD deploy to prod project
resource "google_cloudbuild_trigger" "push_main" {
  count           = var.github_connected && local.is_prod ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-push-main"
  description     = "CI only: standard eval on push to main — prod deploy via git tag (release trigger) [prod]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push { branch = "^main$" }
  }

  filename = "cloudbuild/cloudbuild.yaml"
  substitutions = {
    _EVAL_PROFILE          = "standard"
    _GOOGLE_CLOUD_LOCATION = var.region
    _FIRESTORE_DATABASE    = var.firestore_database_id
  }
  depends_on    = [google_project_service.apis]
}

# ==============================================================================
# TERRAFORM CI/CD TRIGGERS
# ==============================================================================

# Terraform Plan — PR to env branch shows infra diff before merge
resource "google_cloudbuild_trigger" "terraform_plan" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "terraform-plan"
  description     = "Terraform plan: show infra diff on PR to ${var.environment} [${var.environment}]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    pull_request {
      branch          = local.deploy_branch
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
    }
  }

  filename      = "cloudbuild/terraform-plan.yaml"
  substitutions = local.terraform_substitutions
  depends_on    = [google_project_service.apis]
}

# Terraform Apply — push to env branch auto-applies infra changes after merge
resource "google_cloudbuild_trigger" "terraform_apply" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "terraform-apply"
  description     = "Terraform apply: auto-apply infra on push to ${var.environment} branch [${var.environment}]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push { branch = local.deploy_branch }
  }

  filename      = "cloudbuild/terraform-apply.yaml"
  substitutions = local.terraform_substitutions
  depends_on    = [google_project_service.apis]
}

# ==============================================================================
# RELEASE TRIGGER — prod only
# ==============================================================================

# Release: git tag push (v*) → versioned deploy to prod
resource "google_cloudbuild_trigger" "release" {
  count           = var.github_connected && local.is_prod ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "release"
  description     = "Release: build + tag Docker image + deploy Agent Engine + Cloud Run on git tag push (v*) [prod]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push {
      tag = "^v[0-9]+\\.[0-9]+\\.[0-9]+"
    }
  }

  filename = "cloudbuild/release.yaml"

  substitutions = {
    _GOOGLE_CLOUD_LOCATION      = var.region
    _REGION                     = var.region
    _FIRESTORE_DATABASE         = var.firestore_database_id
    _SERVICE_NAME               = var.cloud_run_service_name
    _AR_REPO                    = var.ar_repo_name
    _STAGING_BUCKET             = "gs://${var.staging_bucket_name}"
    _MODEL_ARMOR_ENABLED        = tostring(var.model_armor_enabled)
    _MODEL_ARMOR_TEMPLATE_ID    = var.model_armor_enabled ? google_model_armor_template.customer_support_policy[0].name : ""
    _AGENT_ENGINE_RESOURCE_NAME = var.agent_engine_resource_name
  }

  depends_on = [google_project_service.apis]
}

# ==============================================================================
# NIGHTLY EVAL — prod only
# ==============================================================================

resource "google_cloudbuild_trigger" "nightly" {
  count           = var.github_connected && local.is_prod ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-manual"
  description     = "Full eval + optional post-deploy eval (nightly / manual dispatch) [prod]"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  source_to_build {
    repository = local.repo_resource
    ref        = "refs/heads/main"
    repo_type  = "GITHUB"
  }

  filename = "cloudbuild/cloudbuild-nightly.yaml"

  substitutions = {
    _EVAL_PROFILE                = "full"
    _GOOGLE_CLOUD_LOCATION       = var.region
    _FIRESTORE_DATABASE          = var.firestore_database_id
    _AGENT_ENGINE_RESOURCE_NAME  = var.agent_engine_resource_name
  }

  depends_on = [google_project_service.apis]
}

# Cloud Scheduler — fires nightly trigger at midnight UTC — prod only
resource "google_cloud_scheduler_job" "nightly_eval" {
  count       = var.github_connected && local.is_prod ? 1 : 0
  project     = var.project_id
  region      = var.region
  name        = "nightly-full-eval"
  description = "Trigger full eval pipeline nightly at midnight UTC"
  schedule    = "0 0 * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://cloudbuild.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/triggers/${google_cloudbuild_trigger.nightly[0].trigger_id}:run"
    body        = base64encode(jsonencode({ branchName = "main" }))
    oauth_token { service_account_email = local.cloud_run_sa }
  }

  depends_on = [
    google_project_service.apis,
    google_cloudbuild_trigger.nightly,
    google_project_iam_member.cloud_run_sa,
  ]
}
