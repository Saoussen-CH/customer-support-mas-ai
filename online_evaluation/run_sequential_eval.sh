#!/bin/bash
# Sequential Evaluation Runner
#
# Runs evaluation on each test case sequentially with delays to avoid quota limits.
# Usage: ./online_evaluation/run_sequential_eval.sh

set -e

# Change to project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Configuration
DELAY_BETWEEN_TESTS=120  # 2 minutes between evaluations

echo "=================================================================="
echo "SEQUENTIAL EVALUATION RUNNER"
echo "=================================================================="
echo ""
echo "This script will run evaluation on each test case sequentially"
echo "with ${DELAY_BETWEEN_TESTS}s delays to avoid quota limits."
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Loaded environment from .env"
else
    echo "⚠️  No .env file found, using environment variables"
fi

# Validate required variables
if [ -z "$AGENT_ENGINE_RESOURCE_NAME" ]; then
    echo "❌ ERROR: AGENT_ENGINE_RESOURCE_NAME not set"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Project: ${GOOGLE_CLOUD_PROJECT:-project-ddc15d84-7238-4571-a39}"
echo "  Agent: $AGENT_ENGINE_RESOURCE_NAME"
echo "  Delay between tests: ${DELAY_BETWEEN_TESTS}s"
echo ""

# Get number of test cases
TEST_COUNT=$(python3 -c "
import json
with open('online_evaluation/datasets/billing_queries.evalset.json') as f:
    data = json.load(f)
print(len(data['eval_cases']))
")

echo "Total test cases: $TEST_COUNT"
echo ""
read -p "Press Enter to start evaluation..."
echo ""

# Run each test case
for i in $(seq 0 $(($TEST_COUNT - 1))); do
    echo "=================================================================="
    echo "EVALUATING TEST CASE $i / $(($TEST_COUNT - 1))"
    echo "=================================================================="
    echo ""

    python online_evaluation/run_single_eval.py --test-index $i --delay 30

    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "⚠️  Test case $i failed or encountered errors"
        read -p "Continue to next test? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Stopping sequential evaluation."
            exit 1
        fi
    fi

    # Delay before next test (except for last test)
    if [ $i -lt $(($TEST_COUNT - 1)) ]; then
        echo ""
        echo "⏰ Waiting ${DELAY_BETWEEN_TESTS}s before next test..."
        sleep $DELAY_BETWEEN_TESTS
        echo ""
    fi
done

echo ""
echo "=================================================================="
echo "✅ SEQUENTIAL EVALUATION COMPLETE"
echo "=================================================================="
echo ""
echo "Results are saved in:"
echo "  - Local: online_evaluation/results/"
echo "  - GCS: gs://${GOOGLE_CLOUD_PROJECT:-project-ddc15d84-7238-4571-a39}-eval-results/"
echo ""
