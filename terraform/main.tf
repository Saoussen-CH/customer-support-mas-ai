terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Uncomment to store Terraform state remotely in GCS (recommended for teams).
  # Create the bucket first, then run: terraform init -migrate-state
  #
  # backend "gcs" {
  #   bucket = "YOUR_PROJECT_ID-tf-state"
  #   prefix = "customer-support-mas"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# Project data — used to derive service account emails from project number
# ---------------------------------------------------------------------------
data "google_project" "project" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.project.number

  # Vertex AI Agent Engine service account (used by deployed agents)
  agent_engine_sa = "service-${local.project_number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

  # Core Vertex AI service account (for embeddings, generateContent)
  vertex_sa = "service-${local.project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"

  # Cloud Run default compute SA (used by the FastAPI backend)
  cloud_run_sa = "${local.project_number}-compute@developer.gserviceaccount.com"

  # Cloud Build SA (used by all CI/CD pipelines)
  cloud_build_sa = "${local.project_number}@cloudbuild.gserviceaccount.com"

  # Artifact Registry image path prefix
  ar_base_url = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo_name}"
}
