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
  default     = "customer-support-mas-kaggle"
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
