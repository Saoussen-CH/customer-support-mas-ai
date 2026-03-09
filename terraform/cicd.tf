# ==============================================================================
# CI/CD — Cloud Build triggers (2nd gen) + Cloud Scheduler nightly job
# ==============================================================================
#
# PREREQUISITE: Create a 2nd gen host connection and link the repository manually
# in the GCP Console before setting github_connected = true:
#
#   Cloud Build → Repositories (2nd gen) → Create host connection → GitHub
#   → Link repository → Saoussen-CH/customer-support-mas-ai
#
# Then set in terraform.tfvars:
#   github_connected        = true
#   cloudbuild_connection_name = "<name-you-gave-the-connection>"
#
# 2nd gen triggers require a regional location (not "global").

locals {
  repo_resource = "projects/${var.project_id}/locations/${var.region}/connections/${var.cloudbuild_connection_name}/repositories/${var.cloudbuild_repo_name}"
}

# ------------------------------------------------------------------------------
# PR trigger — pr-checks.yaml (EVAL_PROFILE=fast)
# Runs on every pull request targeting main.
# ------------------------------------------------------------------------------
resource "google_cloudbuild_trigger" "pr_checks" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-pull-request"
  description     = "PR checks: fast eval + lint + ruff format (EVAL_PROFILE=fast)"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    pull_request {
      branch          = "^main$"
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

# ------------------------------------------------------------------------------
# Push to develop — cloudbuild.yaml (EVAL_PROFILE=standard)
# CI only, no deployment.
# ------------------------------------------------------------------------------
resource "google_cloudbuild_trigger" "push_develop" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-push-develop"
  description     = "CI: standard eval on push to develop (EVAL_PROFILE=standard)"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push {
      branch = "^develop$"
    }
  }

  filename = "cloudbuild/cloudbuild.yaml"

  substitutions = {
    _EVAL_PROFILE          = "standard"
    _GOOGLE_CLOUD_LOCATION = var.region
    _FIRESTORE_DATABASE    = var.firestore_database_id
  }

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Push to main — cloudbuild-deploy.yaml (EVAL_PROFILE=standard + deploy)
# Full CI pipeline followed by Docker build and Cloud Run deploy.
# ------------------------------------------------------------------------------
resource "google_cloudbuild_trigger" "push_main" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-cd-push-main"
  description     = "CI + CD: standard eval + deploy to Cloud Run on push to main"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild/cloudbuild-deploy.yaml"

  substitutions = {
    _EVAL_PROFILE            = "standard"
    _GOOGLE_CLOUD_LOCATION   = var.region
    _REGION                  = var.region
    _FIRESTORE_DATABASE      = var.firestore_database_id
    _SERVICE_NAME            = var.cloud_run_service_name
    _AR_REPO                 = var.ar_repo_name
    _MODEL_ARMOR_ENABLED     = tostring(var.model_armor_enabled)
    _MODEL_ARMOR_TEMPLATE_ID = ""
  }

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Manual / nightly trigger — cloudbuild-nightly.yaml (EVAL_PROFILE=full)
# Triggered by Cloud Scheduler (see below) or manually from the console.
# ------------------------------------------------------------------------------
resource "google_cloudbuild_trigger" "nightly" {
  count           = var.github_connected ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "ci-manual"
  description     = "Full eval + optional post-deploy eval (nightly / manual dispatch)"
  service_account = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"

  repository_event_config {
    repository = local.repo_resource
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild/cloudbuild-nightly.yaml"

  substitutions = {
    _EVAL_PROFILE          = "full"
    _GOOGLE_CLOUD_LOCATION = var.region
    _FIRESTORE_DATABASE    = var.firestore_database_id
  }

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Cloud Scheduler — fires the nightly trigger at midnight UTC
# ------------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "nightly_eval" {
  count       = var.github_connected ? 1 : 0
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

    oauth_token {
      service_account_email = local.cloud_run_sa
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloudbuild_trigger.nightly,
    google_project_iam_member.cloud_run_sa,
  ]
}
