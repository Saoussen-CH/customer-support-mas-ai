# ==============================================================================
# GCP API Enablement
# ==============================================================================
# All APIs required by the customer support MAS.
# disable_on_destroy = false so that destroying Terraform resources does not
# break other workloads in the project that depend on the same APIs.

locals {
  base_apis = [
    "aiplatform.googleapis.com",           # Vertex AI (Agent Engine, Gemini, embeddings)
    "firestore.googleapis.com",            # Firestore database
    "run.googleapis.com",                  # Cloud Run (backend + frontend)
    "cloudbuild.googleapis.com",           # Cloud Build CI/CD
    "storage.googleapis.com",              # GCS staging bucket
    "artifactregistry.googleapis.com",     # Docker image registry
    "cloudresourcemanager.googleapis.com", # IAM / project metadata
    "iam.googleapis.com",                  # Service accounts
    "logging.googleapis.com",              # Cloud Logging
    "monitoring.googleapis.com",           # Cloud Monitoring
    "secretmanager.googleapis.com",        # Secret Manager (staging bucket secret)
    "cloudscheduler.googleapis.com",       # Cloud Scheduler (nightly eval trigger)
  ]

  model_armor_api = var.model_armor_enabled ? ["modelarmor.googleapis.com"] : []

  all_apis = concat(local.base_apis, local.model_armor_api)
}

resource "google_project_service" "apis" {
  for_each = toset(local.all_apis)

  project = var.project_id
  service = each.key

  disable_on_destroy         = false
  disable_dependent_services = false
}
