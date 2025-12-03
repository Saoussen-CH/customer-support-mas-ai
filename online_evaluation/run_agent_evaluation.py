#!/usr/bin/env python3
"""
Agent Engine Online Evaluation Script

This script evaluates a customer support agent deployed to Vertex AI Agent Engine
using the Gen AI evaluation service. It follows the official Google Cloud pattern
from create_genai_agent_evaluation.ipynb.

Usage:
    Set environment variables in .env file or export:
    export GOOGLE_CLOUD_PROJECT="project-id"
    export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."

    python online_evaluation/run_agent_evaluation.py
"""

import os
import json
import time
import sys
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Vertex AI imports
from vertexai import Client
from google.genai import types as genai_types
from vertexai import types


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Agent configuration
AGENT_ENGINE_RESOURCE_NAME = os.getenv(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/773461168680/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"
)

# Storage configuration
GCS_EVAL_BUCKET = f"gs://{PROJECT_ID}-eval-results"

# Get script directory and construct absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(SCRIPT_DIR, "datasets", "billing_queries.evalset.json")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(text):
    """Print formatted header."""
    print("\n" + "="*80)
    print(text)
    print("="*80 + "\n")


def load_evaluation_dataset(dataset_file):
    """Load evaluation dataset from JSON file."""
    print(f"📂 Loading dataset: {dataset_file}")

    with open(dataset_file, 'r') as f:
        eval_data = json.load(f)

    print(f"   Evaluation Set: {eval_data['eval_set_id']}")
    print(f"   Total Cases: {len(eval_data['eval_cases'])}\n")

    return eval_data


def prepare_evaluation_dataset(eval_data):
    """Prepare dataset for Vertex AI evaluation."""
    print("🔧 Preparing evaluation dataset...")

    prompts = []
    session_inputs = []
    eval_ids = []

    for i, eval_case in enumerate(eval_data['eval_cases']):
        # Extract user prompt
        conversation = eval_case['conversation'][0]
        prompt = conversation['user_content']['parts'][0]['text']

        # Create session input with unique user_id
        session_input = types.evals.SessionInput(
            user_id=f"eval_user_{i}",
            state={},
        )

        prompts.append(prompt)
        session_inputs.append(session_input)
        eval_ids.append(eval_case['eval_id'])

    # Create DataFrame in format required by Vertex AI
    dataset = pd.DataFrame({
        'prompt': prompts,
        'session_inputs': session_inputs,
    })

    print(f"   Created {len(dataset)} test cases\n")

    return dataset


def run_inference(client, agent_resource_name, dataset):
    """Run inference on deployed agent.

    The SDK handles rate limiting internally.
    """
    print("🤖 Running inference on deployed agent...")
    print("   This may take several minutes...\n")

    # Run inference - SDK handles everything including rate limiting
    agent_dataset_with_inference = client.evals.run_inference(
        agent=agent_resource_name,
        src=dataset,
    )

    print(f"✅ Inference completed for {len(dataset)} test cases\n")

    return agent_dataset_with_inference


def define_agent_info(agent_resource_name):
    """Define agent info with tool declarations."""
    print("🔧 Defining agent info...")

    # Define tool declarations for domain agents
    product_agent_tool = genai_types.FunctionDeclaration(
        name="product_agent",
        description="Product search and details using semantic search",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User query about products"}},
            "required": ["request"],
        },
    )

    order_agent_tool = genai_types.FunctionDeclaration(
        name="order_agent",
        description="Order tracking and history specialist",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User query about orders"}},
            "required": ["request"],
        },
    )

    billing_agent_tool = genai_types.FunctionDeclaration(
        name="billing_agent",
        description="Billing, invoices, and payment specialist",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User query about billing"}},
            "required": ["request"],
        },
    )

    # Define tool declarations for workflow agents
    comprehensive_product_lookup_tool = genai_types.FunctionDeclaration(
        name="comprehensive_product_lookup",
        description="ParallelAgent: Get comprehensive info for ONE product (details + inventory + reviews simultaneously)",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User query for comprehensive product information"}},
            "required": ["request"],
        },
    )

    refund_workflow_tool = genai_types.FunctionDeclaration(
        name="refund_workflow",
        description="SequentialAgent: Validated refund processing workflow (validate order → check eligibility → process refund)",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User refund request"}},
            "required": ["request"],
        },
    )

    multi_product_details_tool = genai_types.FunctionDeclaration(
        name="multi_product_details",
        description="LoopAgent: Get details for MULTIPLE products (when user asks for 'both', 'all', etc.)",
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "User query for multiple product details"}},
            "required": ["request"],
        },
    )

    # Create agent info with all tools
    agent_info = types.evals.AgentInfo(
        agent_resource_name=agent_resource_name,
        name="customer_support",
        instruction="You are a customer support routing coordinator. Route user queries to specialist agents and workflow agents, then relay their responses.",
        tool_declarations=[genai_types.Tool(function_declarations=[
            product_agent_tool,
            order_agent_tool,
            billing_agent_tool,
            comprehensive_product_lookup_tool,
            refund_workflow_tool,
            multi_product_details_tool
        ])],
    )

    print("✅ Agent info defined with 6 tools (3 domain agents + 3 workflow agents)\n")

    return agent_info


def create_evaluation_run(client, dataset_with_inference, agent_info, gcs_dest):
    """Create evaluation run (persisted to GCS)."""
    print("📈 Creating evaluation run...")
    print(f"   Results will be saved to: {gcs_dest}")
    print(f"   Metrics: FINAL_RESPONSE_QUALITY, TOOL_USE_QUALITY, HALLUCINATION, SAFETY\n")

    evaluation_run = client.evals.create_evaluation_run(
        dataset=dataset_with_inference,
        agent_info=agent_info,
        metrics=[
            types.RubricMetric.FINAL_RESPONSE_QUALITY,
            types.RubricMetric.TOOL_USE_QUALITY,
            types.RubricMetric.HALLUCINATION,
            types.RubricMetric.SAFETY,
        ],
        dest=gcs_dest,
    )

    print(f"✅ Evaluation run created: {evaluation_run.name}")
    print(f"   Initial status: {evaluation_run.state}\n")

    return evaluation_run


def wait_for_completion(client, evaluation_run):
    """Poll for evaluation completion."""
    print("⏳ Waiting for evaluation to complete...")
    print("   Polling every 10 seconds...\n")

    poll_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 3

    while evaluation_run.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        time.sleep(10)
        poll_count += 1

        try:
            evaluation_run = client.evals.get_evaluation_run(name=evaluation_run.name)
            consecutive_errors = 0  # Reset on success

            if poll_count % 3 == 0:  # Every 30 seconds
                print(f"   Status: {evaluation_run.state} (elapsed: {poll_count * 10}s)")
        except Exception as e:
            consecutive_errors += 1
            print(f"   Warning: Polling error (attempt {consecutive_errors}/{max_consecutive_errors})")

            if consecutive_errors >= max_consecutive_errors:
                print(f"\n⚠️  Too many consecutive polling errors")
                print(f"   Evaluation run: {evaluation_run.name}")
                raise

    print(f"\n✅ Evaluation completed with status: {evaluation_run.state}\n")

    if evaluation_run.state != "SUCCEEDED":
        print(f"⚠️  Evaluation did not succeed")
        print(f"   State: {evaluation_run.state}")
        if hasattr(evaluation_run, 'state_error') and evaluation_run.state_error:
            print(f"   Error: {evaluation_run.state_error}")
        print(f"\n   Check GCS destination for details: {GCS_EVAL_BUCKET}")
        return None

    return evaluation_run


def display_results(evaluation_run):
    """Display evaluation results."""
    print_header("EVALUATION RESULTS")

    print("Displaying evaluation results...\n")
    try:
        evaluation_run.show()
    except Exception as e:
        print(f"Note: .show() requires IPython environment. Error: {e}\n")


def save_results(evaluation_run, dataset, timestamp, gcs_dest):
    """Save evaluation summary."""
    print_header("SAVING RESULTS")

    # Create results directory
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Create summary
    summary = {
        "timestamp": timestamp,
        "agent_resource_name": AGENT_ENGINE_RESOURCE_NAME,
        "evaluation_run_name": evaluation_run.name,
        "evaluation_state": evaluation_run.state,
        "gcs_destination": gcs_dest,
        "total_tests": len(dataset),
        "dataset_file": DATASET_FILE,
    }

    # Save summary as JSON
    json_path = os.path.join(RESULTS_DIR, f"eval_summary_{timestamp}.json")
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✅ Evaluation summary: {json_path}")
    print(f"✅ Full results in GCS: {gcs_dest}")
    print(f"✅ Evaluation run name: {evaluation_run.name}\n")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function."""
    print_header("AGENT ENGINE ONLINE EVALUATION")

    print(f"Configuration:")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Agent: {AGENT_ENGINE_RESOURCE_NAME}")
    print(f"  Dataset: {DATASET_FILE}")
    print(f"  Results Bucket: {GCS_EVAL_BUCKET}")

    # Validate configuration
    if AGENT_ENGINE_RESOURCE_NAME == "projects/773461168680/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID":
        print("\n❌ ERROR: AGENT_ENGINE_RESOURCE_NAME not set")
        print("\nPlease set the environment variable:")
        print("  export AGENT_ENGINE_RESOURCE_NAME='projects/PROJECT/locations/LOCATION/reasoningEngines/ID'")
        return 1

    try:
        # Step 1: Load dataset
        eval_data = load_evaluation_dataset(DATASET_FILE)
        dataset = prepare_evaluation_dataset(eval_data)

        # Step 2: Initialize Vertex AI Client
        print("🔧 Initializing Vertex AI Client...")
        client = Client(
            project=PROJECT_ID,
            location=LOCATION,
            http_options=genai_types.HttpOptions(api_version="v1beta1"),
        )
        print("✅ Client initialized\n")

        # Step 3: Run inference
        dataset_with_inference = run_inference(client, AGENT_ENGINE_RESOURCE_NAME, dataset)

        # Step 4: Define agent info
        agent_info = define_agent_info(AGENT_ENGINE_RESOURCE_NAME)

        # Step 5: Create evaluation run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gcs_dest = f"{GCS_EVAL_BUCKET}/eval-{timestamp}"

        evaluation_run = create_evaluation_run(client, dataset_with_inference, agent_info, gcs_dest)

        # Step 6: Wait for completion
        evaluation_run = wait_for_completion(client, evaluation_run)
        if not evaluation_run:
            return 1

        # Step 7: Get detailed results
        print("📊 Retrieving detailed evaluation results...\n")
        evaluation_run = client.evals.get_evaluation_run(
            name=evaluation_run.name,
            include_evaluation_items=True
        )

        # Step 8: Display results
        display_results(evaluation_run)

        # Step 9: Save summary
        save_results(evaluation_run, dataset, timestamp, gcs_dest)

        print_header("✅ EVALUATION COMPLETE")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
