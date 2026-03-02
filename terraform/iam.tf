# ==============================================================================
# IAM — google_project_iam_member (additive, does not replace existing bindings)
# ==============================================================================

# ------------------------------------------------------------------------------
# Vertex AI Agent Engine service account
# Runs deployed agents; needs Firestore to call tools and Vertex AI for Gemini.
# ------------------------------------------------------------------------------
resource "google_project_iam_member" "agent_engine_sa" {
  for_each = toset([
    "roles/datastore.user",       # Read/write Firestore (tool calls)
    "roles/aiplatform.user",      # Call Gemini / Vertex AI APIs
    "roles/storage.objectViewer", # Read staging bucket artifacts
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.agent_engine_sa}"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Core Vertex AI service account
# Used for embeddings and direct generateContent calls.
# ------------------------------------------------------------------------------
resource "google_project_iam_member" "vertex_sa" {
  for_each = toset([
    "roles/datastore.user",  # Firestore vector search for RAG
    "roles/aiplatform.user",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.vertex_sa}"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Cloud Run default compute service account
# Runs the FastAPI backend; needs Agent Engine and Firestore.
# ------------------------------------------------------------------------------
resource "google_project_iam_member" "cloud_run_sa" {
  for_each = toset([
    "roles/aiplatform.user", # Call Agent Engine
    "roles/datastore.user",  # Read/write sessions and messages
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.cloud_run_sa}"

  depends_on = [google_project_service.apis]
}

# Cloud Run SA also needs access to the staging bucket at the bucket level
# (granted in infrastructure.tf on the bucket resource itself)

# Cloud Run SA needs to invoke Cloud Build triggers (used by Cloud Scheduler)
resource "google_project_iam_member" "cloud_run_sa_cloudbuild" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${local.cloud_run_sa}"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Cloud Build service account
# Runs CI/CD pipelines; needs to deploy to Cloud Run and Artifact Registry.
# ------------------------------------------------------------------------------
resource "google_project_iam_member" "cloud_build_sa" {
  for_each = toset([
    "roles/datastore.user",                 # Firestore access during agent eval tests
    "roles/aiplatform.user",                # Call Vertex AI Gemini during eval tests
    "roles/aiplatform.admin",               # Deploy to Agent Engine
    "roles/artifactregistry.writer",        # Push Docker images
    "roles/run.admin",                      # Deploy Cloud Run service
    "roles/storage.objectAdmin",            # Read/write staging bucket
    "roles/secretmanager.secretAccessor",   # Read staging-bucket secret
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.cloud_build_sa}"

  depends_on = [google_project_service.apis]
}

# Cloud Build SA needs to impersonate the Cloud Run compute SA when deploying
resource "google_service_account_iam_member" "cloud_build_impersonate_compute" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.cloud_run_sa}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.cloud_build_sa}"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Model Armor — grant modelarmor.user to both Vertex AI service accounts
# so that Agent Engine and embedding calls can pass through Model Armor screening
# ------------------------------------------------------------------------------
resource "google_project_iam_member" "model_armor_agent_engine" {
  count = var.model_armor_enabled ? 1 : 0

  project = var.project_id
  role    = "roles/modelarmor.user"
  member  = "serviceAccount:${local.agent_engine_sa}"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "model_armor_vertex" {
  count = var.model_armor_enabled ? 1 : 0

  project = var.project_id
  role    = "roles/modelarmor.user"
  member  = "serviceAccount:${local.vertex_sa}"

  depends_on = [google_project_service.apis]
}
