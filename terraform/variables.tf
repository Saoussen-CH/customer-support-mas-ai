# ==============================================================================
# Required
# ==============================================================================

variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "staging_bucket_name" {
  description = "GCS bucket name for Agent Engine staging artifacts. Must be globally unique."
  type        = string
}

variable "github_owner" {
  description = "GitHub repository owner (username or organisation)."
  type        = string
}

# ==============================================================================
# Optional — sensible defaults match the rest of the project
# ==============================================================================

variable "region" {
  description = "Primary GCP region for Cloud Run, Artifact Registry, and Cloud Scheduler."
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore multi-region location code. nam5=US, eur3=Europe."
  type        = string
  default     = "nam5"
}

variable "firestore_database_id" {
  description = "Firestore database ID."
  type        = string
  default     = "customer-support-db"
}

variable "ar_repo_name" {
  description = "Artifact Registry Docker repository name."
  type        = string
  default     = "customer-support"
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name for the FastAPI + React backend."
  type        = string
  default     = "customer-support-app"
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
  default     = "customer-support-mas-ai"
}

variable "google_managed_sas_exist" {
  description = "Set to true after first Agent Engine deployment to grant IAM to Google-managed Vertex AI SAs (gcp-sa-aiplatform-re and gcp-sa-aiplatform). These SAs are created by Google and do not exist until first use."
  type        = bool
  default     = false
}

variable "github_connected" {
  description = "Set to true after creating a 2nd gen host connection and linking the repository in Cloud Build console. Required for CI/CD trigger creation."
  type        = bool
  default     = false
}

variable "agent_engine_resource_name" {
  description = "Full resource name of the deployed Agent Engine (projects/P/locations/L/reasoningEngines/ID). Set after first deploy."
  type        = string
  default     = ""
}

variable "cloudbuild_connection_name" {
  description = "Name of the 2nd gen Cloud Build host connection (created manually in Cloud Build → Repositories → Create host connection)."
  type        = string
  default     = ""
}

variable "cloudbuild_repo_name" {
  description = "Repository name as shown in Cloud Build 2nd gen (usually Owner-repo-name, e.g. Saoussen-CH-customer-support-mas-ai). Run: gcloud builds repositories list --connection=<name> --region=<region>"
  type        = string
  default     = ""
}

variable "model_armor_enabled" {
  description = "Enable Model Armor: grants IAM, enables API, and configures floor settings."
  type        = bool
  default     = true
}

variable "model_armor_floor_mode" {
  description = "Model Armor floor enforcement mode. INSPECT_AND_BLOCK rejects flagged requests; INSPECT_ONLY logs only."
  type        = string
  default     = "INSPECT_AND_BLOCK"

  validation {
    condition     = contains(["INSPECT_AND_BLOCK", "INSPECT_ONLY"], var.model_armor_floor_mode)
    error_message = "model_armor_floor_mode must be INSPECT_AND_BLOCK or INSPECT_ONLY."
  }
}
