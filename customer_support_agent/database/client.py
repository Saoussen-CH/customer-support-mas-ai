"""
Database Client Configuration
===============================
Sets up Firestore database client for the customer support system.
"""

import os
from dotenv import load_dotenv
from google.cloud import firestore

# Load environment variables from .env file (local development only)
load_dotenv()

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DATABASE_ID = os.getenv("FIRESTORE_DATABASE", "customer-support-db")

# Firestore project - ALWAYS use the hardcoded project ID where the database exists
# CRITICAL: Do NOT use os.getenv("GOOGLE_CLOUD_PROJECT") because when deployed to
# Agent Engine, it returns the project NUMBER (773461168680) instead of project ID
# (project-ddc15d84-7238-4571-a39), and the database only exists in the project ID
FIRESTORE_PROJECT = "project-ddc15d84-7238-4571-a39"

# Initialize Firestore client
db_client = firestore.Client(project=FIRESTORE_PROJECT, database=DATABASE_ID)
