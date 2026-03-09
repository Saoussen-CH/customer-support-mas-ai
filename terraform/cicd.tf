# ==============================================================================
# CI/CD — Cloud Build triggers + Cloud Scheduler nightly job
# ==============================================================================
#
# PREREQUISITE: Connect your GitHub repository in Cloud Console before applying:
#   Cloud Build → Triggers → Connect Repository → GitHub
#   (OAuth browser flow — cannot be automated via Terraform)
#
# Once connected, set github_owner and github_repo in terraform.tfvars.

# ------------------------------------------------------------------------------
# PR trigger — pr-checks.yaml (EVAL_PROFILE=fast)
# Runs on every pull request targeting main.
# Includes ruff format check to mirror .pre-commit-config.yaml.
# ------------------------------------------------------------------------------
resource "google_cloudbuild_trigger" "pr_checks" {
  count       = var.github_connected ? 1 : 0
  project     = var.project_id
  location    = "global"
  name        = "ci-pull-request"
  description = "PR checks: fast eval + lint + ruff format (EVAL_PROFILE=fast)"

  github {
    owner = var.github_owner
    name  = var.github_repo
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
  count       = var.github_connected ? 1 : 0
  project     = var.project_id
  location    = "global"
  name        = "ci-push-develop"
  description = "CI: standard eval on push to develop (EVAL_PROFILE=standard)"

  github {
    owner = var.github_owner
    name  = var.github_repo
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
  count       = var.github_connected ? 1 : 0
  project     = var.project_id
  location    = "global"
  name        = "ci-cd-push-main"
  description = "CI + CD: standard eval + deploy to Cloud Run on push to main"

  github {
    owner = var.github_owner
    name  = var.github_repo
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
  count       = var.github_connected ? 1 : 0
  project     = var.project_id
  location    = "global"
  name        = "ci-manual"
  description = "Full eval + optional post-deploy eval (nightly / manual dispatch)"

  # source_to_build + git_file_source = manual trigger (no GitHub webhook event)
  source_to_build {
    uri       = "https://github.com/${var.github_owner}/${var.github_repo}"
    ref       = "refs/heads/main"
    repo_type = "GITHUB"
  }

  git_file_source {
    path      = "cloudbuild/cloudbuild-nightly.yaml"
    uri       = "https://github.com/${var.github_owner}/${var.github_repo}"
    revision  = "refs/heads/main"
    repo_type = "GITHUB"
  }

  substitutions = {
    _EVAL_PROFILE          = "full"
    _GOOGLE_CLOUD_LOCATION = var.region
    _FIRESTORE_DATABASE    = var.firestore_database_id
  }

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Cloud Scheduler — fires the nightly trigger at midnight UTC
# Uses the Cloud Run compute SA (which has roles/cloudbuild.builds.editor)
# to call the Cloud Build REST API.
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
    uri         = "https://cloudbuild.googleapis.com/v1/projects/${var.project_id}/locations/global/triggers/${google_cloudbuild_trigger.nightly[0].trigger_id}:run"
    body        = base64encode(jsonencode({ branchName = "main" }))

    oauth_token {
      service_account_email = local.cloud_run_sa
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloudbuild_trigger.nightly,
    google_project_iam_member.cloud_run_sa_cloudbuild,
  ]
}
