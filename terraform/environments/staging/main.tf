# ==============================================================================
# STAGING environment — watches staging branch, deploys to staging GCP project
# Mirrors prod config (INSPECT_AND_BLOCK, delete protection) for accurate testing.
# No nightly scheduler — that runs in prod only.
# ==============================================================================
# Usage:
#   cd terraform/environments/staging
#   terraform init -backend-config=backend.hcl
#   terraform apply -var-file=terraform.tfvars

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Remote state — create the GCS bucket first, then uncomment and run terraform init
  # backend "gcs" {
  #   bucket = "YOUR_STAGING_PROJECT_ID-tf-state"
  #   prefix = "customer-support-mas/staging"
  # }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

module "core" {
  source = "../../modules/core"

  # Environment
  environment = "staging"

  # Required
  project_id          = var.project_id
  staging_bucket_name = var.staging_bucket_name
  github_owner        = var.github_owner

  # Optional — override defaults as needed
  region                     = var.region
  firestore_location         = var.firestore_location
  firestore_database_id      = var.firestore_database_id
  ar_repo_name               = var.ar_repo_name
  cloud_run_service_name     = var.cloud_run_service_name
  github_repo                = var.github_repo
  google_managed_sas_exist   = var.google_managed_sas_exist
  github_connected           = var.github_connected
  agent_engine_resource_name = var.agent_engine_resource_name
  cloudbuild_connection_name = var.cloudbuild_connection_name
  cloudbuild_repo_name       = var.cloudbuild_repo_name
  model_armor_enabled        = var.model_armor_enabled
  model_armor_floor_mode     = var.model_armor_floor_mode
}
