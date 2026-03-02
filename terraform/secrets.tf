# ==============================================================================
# Secret Manager
# ==============================================================================
# The staging-bucket secret is read by the Cloud Build deploy pipeline to pass
# the bucket name to Agent Engine deployment without hardcoding it in YAML.

resource "google_secret_manager_secret" "staging_bucket" {
  project   = var.project_id
  secret_id = "staging-bucket"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "staging_bucket" {
  secret      = google_secret_manager_secret.staging_bucket.id
  secret_data = var.staging_bucket_name

  # Prevent Terraform from showing the secret value in plan output
  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Grant Cloud Build SA access to read the secret
resource "google_secret_manager_secret_iam_member" "cloud_build_staging_bucket" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.staging_bucket.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.cloud_build_sa}"

  depends_on = [google_project_service.apis]
}
