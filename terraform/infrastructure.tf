# ==============================================================================
# Core Infrastructure
# GCS bucket, Firestore database, Artifact Registry repository
# ==============================================================================

# ------------------------------------------------------------------------------
# GCS staging bucket — used by Agent Engine for deployment artifacts
# ------------------------------------------------------------------------------
resource "google_storage_bucket" "staging" {
  name                        = var.staging_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  # Automatically delete staging artifacts older than 90 days
  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

# Grant Cloud Run SA object-level access to the staging bucket
resource "google_storage_bucket_iam_member" "cloud_run_staging" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.cloud_run_sa}"
}

# Grant Agent Engine SA read access to the staging bucket
# (skipped until first Agent Engine deployment creates the SA)
resource "google_storage_bucket_iam_member" "agent_engine_staging" {
  count  = var.google_managed_sas_exist ? 1 : 0
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.agent_engine_sa}"
}

# ------------------------------------------------------------------------------
# Firestore database
# Stores products, orders, invoices, sessions, messages, refunds
# ------------------------------------------------------------------------------
resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = var.firestore_database_id
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  # Keep delete protection disabled so the database can be recreated in dev;
  # enable it manually in production:
  #   gcloud firestore databases update --delete-protection --database=customer-support-db
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Artifact Registry — Docker image repository for the Cloud Run backend
# ------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "docker" {
  project       = var.project_id
  location      = var.region
  repository_id = var.ar_repo_name
  format        = "DOCKER"
  description   = "Customer Support MAS Docker images (FastAPI + React)"

  depends_on = [google_project_service.apis]
}
