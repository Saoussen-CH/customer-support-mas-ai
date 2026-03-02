# ==============================================================================
# Model Armor
# ==============================================================================
# Configures project-level floor settings that automatically screen every
# Vertex AI generateContent call — including those made internally by
# Agent Engine — for harmful content, prompt injection, and jailbreaks.
#
# No changes to agents or tools are required. Protection is applied
# transparently at the Gemini API layer.
#
# Requires: google provider >= 6.14.0
#           var.model_armor_enabled = true (default)
#
# IAM grants (roles/modelarmor.user on Vertex AI SAs) are in iam.tf.
# API enablement (modelarmor.googleapis.com) is in apis.tf.

resource "google_model_armor_floor_setting" "default" {
  count    = var.model_armor_enabled ? 1 : 0
  project  = var.project_id
  location = "global"

  # Reject requests and responses that violate thresholds.
  # Set to false (or use INSPECT_ONLY in filter_config) to log-only.
  enable_floor_setting_enforcement = var.model_armor_floor_mode == "INSPECT_AND_BLOCK"

  filter_config {
    # Responsible AI content filters
    rai_settings {
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS_CONTENT"
        confidence_level = "LOW_AND_ABOVE"
      }
    }

    # Prompt injection and jailbreak detection
    # Protects refund validation and auth flows from bypass attempts
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "LOW_AND_ABOVE"
    }

    # Block responses containing links to malicious URIs
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
  }

  depends_on = [google_project_service.apis]
}
