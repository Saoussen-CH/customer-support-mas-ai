#!/usr/bin/env python3
"""
Single Test Case Evaluation

Run evaluation on one test case at a time to avoid judge model quota limits.

Usage:
    python online_evaluation/run_single_eval.py --test-index 0
"""

import os
import json
import time
import sys
import argparse
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Vertex AI imports
from vertexai import Client
from google.genai import types as genai_types
from vertexai import types


# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-ddc15d84-7238-4571-a39")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
AGENT_ENGINE_RESOURCE_NAME = os.getenv(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/773461168680/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"
)
GCS_EVAL_BUCKET = f"gs://{PROJECT_ID}-eval-results"

# Get script directory and construct absolute path to dataset
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(SCRIPT_DIR, "datasets", "billing_queries.evalset.json")


def main():
    parser = argparse.ArgumentParser(description='Run evaluation on single test case')
    parser.add_argument('--test-index', type=int, required=True, help='Index of test case to evaluate (0-based)')
    parser.add_argument('--delay', type=int, default=60, help='Delay in seconds before evaluation (default: 60)')
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print("SINGLE TEST CASE EVALUATION")
    print(f"{'='*80}\n")

    # Load dataset
    with open(DATASET_FILE, 'r') as f:
        eval_data = json.load(f)

    total_cases = len(eval_data['eval_cases'])
    if args.test_index >= total_cases:
        print(f"❌ Error: Test index {args.test_index} out of range (0-{total_cases-1})")
        return 1

    eval_case = eval_data['eval_cases'][args.test_index]
    prompt = eval_case['conversation'][0]['user_content']['parts'][0]['text']

    print(f"Configuration:")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Agent: {AGENT_ENGINE_RESOURCE_NAME}")
    print(f"  Test Index: {args.test_index}/{total_cases-1}")
    print(f"  Test ID: {eval_case['eval_id']}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Delay before eval: {args.delay}s")

    # Create single-case dataset
    dataset = pd.DataFrame({
        'prompt': [prompt],
        'session_inputs': [types.evals.SessionInput(user_id=f"eval_user_{args.test_index}", state={})],
    })

    try:
        # Initialize client
        print(f"\n🔧 Initializing Vertex AI Client...")
        client = Client(
            project=PROJECT_ID,
            location=LOCATION,
            http_options=genai_types.HttpOptions(api_version="v1beta1"),
        )

        # Run inference
        print(f"🤖 Running inference...")
        dataset_with_inference = client.evals.run_inference(
            agent=AGENT_ENGINE_RESOURCE_NAME,
            src=dataset,
        )
        print(f"✅ Inference completed")

        # Define agent info
        print(f"\n🔧 Defining agent info...")
        # Domain agents
        product_tool = genai_types.FunctionDeclaration(
            name="product_agent",
            description="Product search specialist",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        order_tool = genai_types.FunctionDeclaration(
            name="order_agent",
            description="Order tracking specialist",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        billing_tool = genai_types.FunctionDeclaration(
            name="billing_agent",
            description="Billing specialist",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        # Workflow agents
        comprehensive_lookup_tool = genai_types.FunctionDeclaration(
            name="comprehensive_product_lookup",
            description="ParallelAgent: Comprehensive product info (details + inventory + reviews)",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        refund_workflow_tool = genai_types.FunctionDeclaration(
            name="refund_workflow",
            description="SequentialAgent: Validated refund workflow",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        multi_product_tool = genai_types.FunctionDeclaration(
            name="multi_product_details",
            description="LoopAgent: Multi-product details iteration",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
        )
        agent_info = types.evals.AgentInfo(
            agent_resource_name=AGENT_ENGINE_RESOURCE_NAME,
            name="customer_support",
            instruction="Customer support coordinator with workflow agents",
            tool_declarations=[genai_types.Tool(function_declarations=[
                product_tool, order_tool, billing_tool,
                comprehensive_lookup_tool, refund_workflow_tool, multi_product_tool
            ])],
        )
        print(f"   Defined 6 tools (3 domain + 3 workflow agents)")

        # Wait before creating evaluation (to avoid quota)
        print(f"\n⏰ Waiting {args.delay} seconds before evaluation to avoid quota limits...")
        time.sleep(args.delay)

        # Create evaluation run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gcs_dest = f"{GCS_EVAL_BUCKET}/single-eval-{args.test_index}-{timestamp}"

        print(f"\n📈 Creating evaluation run...")
        print(f"   GCS destination: {gcs_dest}")

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

        # Wait for completion
        print(f"\n⏳ Waiting for evaluation to complete...")
        poll_count = 0
        while evaluation_run.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            time.sleep(10)
            poll_count += 1
            evaluation_run = client.evals.get_evaluation_run(name=evaluation_run.name)
            if poll_count % 3 == 0:
                print(f"   Status: {evaluation_run.state} (elapsed: {poll_count * 10}s)")

        print(f"\n✅ Evaluation completed: {evaluation_run.state}")

        if evaluation_run.state == "SUCCEEDED":
            # Get results
            evaluation_run = client.evals.get_evaluation_run(
                name=evaluation_run.name,
                include_evaluation_items=True
            )
            print(f"\n{'='*80}")
            print("RESULTS")
            print(f"{'='*80}\n")
            try:
                evaluation_run.show()
            except:
                print("Results stored in GCS")

            # Save summary
            results_dir = os.path.join(SCRIPT_DIR, "results")
            os.makedirs(results_dir, exist_ok=True)
            summary_path = os.path.join(results_dir, f"single_eval_{args.test_index}_{timestamp}.json")
            with open(summary_path, 'w') as f:
                json.dump({
                    "test_index": args.test_index,
                    "test_id": eval_case['eval_id'],
                    "prompt": prompt,
                    "evaluation_run": evaluation_run.name,
                    "state": evaluation_run.state,
                    "timestamp": timestamp,
                    "gcs_dest": gcs_dest,
                }, f, indent=2)
            print(f"\n✅ Summary saved: {summary_path}")
            print(f"✅ Full results: {gcs_dest}")

            return 0
        else:
            print(f"\n⚠️  Evaluation failed")
            if evaluation_run.error:
                print(f"Error: {evaluation_run.error}")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
