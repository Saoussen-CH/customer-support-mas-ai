# Online Agent Evaluation

This directory contains tools for evaluating the Customer Support Agent deployed to Vertex AI Agent Engine using the Gen AI Evaluation Service.

> **⚠️ Known Issue:** The evaluation service may fail with "Judge model resource exhausted" errors due to quota limits. The agent responses are working correctly - only the metrics computation is affected. See [Troubleshooting](#evaluation-run-shows-failed-but-agent-responses-are-correct) for solutions.

## Overview

The evaluation follows the official Google Cloud pattern from [create_genai_agent_evaluation.ipynb](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/create_genai_agent_evaluation.ipynb):

1. **Run Agent Inference**: Query the deployed agent to get real responses
2. **Create Evaluation Run**: Evaluate responses using Gen AI metrics (persisted to GCS)
3. **Display Results**: View evaluation scores and analysis

## Files

- **`run_agent_evaluation.py`** - Main evaluation script following official Vertex AI pattern
- **`run_single_eval.py`** - Single test case evaluation (to avoid quota limits)
- **`run_sequential_eval.sh`** - Sequential evaluation with delays
- **`datasets/`** - Test datasets:
  - `billing_queries.evalset.json` - 3 billing queries
  - `parallel_agent.evalset.json` - 3 ParallelAgent tests (comprehensive lookup)
  - `sequential_agent.evalset.json` - 3 SequentialAgent tests (refund workflow)
  - `loop_agent.evalset.json` - 2 LoopAgent tests (multi-product details)
- **`results/`** - Directory for evaluation summaries (auto-created)

## Workflow Agents

The evaluation now supports testing the three workflow agent patterns:

1. **ParallelAgent** (`comprehensive_product_lookup`)
   - Executes sub-agents concurrently for faster responses
   - Example: Get product details + inventory + reviews simultaneously
   - Performance: 3x faster than sequential execution

2. **SequentialAgent** (`refund_workflow`)
   - Executes sub-agents in order with validation gates
   - Example: Validate order → Check eligibility → Process refund
   - Benefit: Each step must pass before proceeding

3. **LoopAgent** (`multi_product_details`)
   - Iterates through multiple products
   - Example: "Show me laptops" → "Give me details on all of them"
   - Benefit: Handles "both", "all", "each" queries automatically

## Quick Start

### 1. Set Environment Variables

The script reads from your `.env` file in the project root, or you can export:

```bash
export GOOGLE_CLOUD_PROJECT="project-ddc15d84-7238-4571-a39"
export GOOGLE_CLOUD_LOCATION="us-central1"
export AGENT_ENGINE_RESOURCE_NAME="projects/773461168680/locations/us-central1/reasoningEngines/3015349066524524544"
```

### 2. Run Evaluation

**Option A: Full Evaluation (All Test Cases)**
```bash
# From project root
python online_evaluation/run_agent_evaluation.py

# Or with explicit environment variables
GOOGLE_CLOUD_PROJECT=project-ddc15d84-7238-4571-a39 \
AGENT_ENGINE_RESOURCE_NAME=projects/773461168680/locations/us-central1/reasoningEngines/3015349066524524544 \
python online_evaluation/run_agent_evaluation.py
```

**Option B: Single Test Case (Recommended to avoid quota issues)**
```bash
# Evaluate test case 0
python online_evaluation/run_single_eval.py --test-index 0 --delay 30

# Evaluate test case 1 (with 30s delay before metrics computation)
python online_evaluation/run_single_eval.py --test-index 1 --delay 30

# Evaluate test case 2
python online_evaluation/run_single_eval.py --test-index 2 --delay 30
```

**Option C: Sequential Evaluation (Automated)**
```bash
# From project root
./online_evaluation/run_sequential_eval.sh
```
This will automatically run all test cases with 2-minute delays between evaluations.

## Evaluation Process

### Step 1: Dataset Preparation
- Loads test cases from `evals/datasets/billing_queries.evalset.json`
- Formats prompts and session inputs for inference

### Step 2: Agent Inference
- Queries deployed agent with test prompts
- SDK automatically handles rate limiting
- Collects responses and intermediate events (tool calls)

### Step 3: Evaluation Run Creation
- Creates persisted evaluation run in GCS
- Evaluates using 4 metrics:
  - **FINAL_RESPONSE_QUALITY**: Overall appropriateness and helpfulness
  - **TOOL_USE_QUALITY**: Effectiveness and correctness of tool usage
  - **HALLUCINATION**: Detection of fabricated information
  - **SAFETY**: Response safety and compliance

### Step 4: Results Analysis
- Polls for completion (every 10 seconds)
- Retrieves detailed results
- Saves summary to local JSON

## Results

Evaluation results are saved to:

- **GCS**: `gs://project-ddc15d84-7238-4571-a39-eval-results/eval-TIMESTAMP/`
- **Local**: `online_evaluation/results/eval_summary_TIMESTAMP.json`

## Viewing Results

### Command Line Output
The script displays:
- Inference progress
- Evaluation status
- Summary statistics (if available)

### GCS Storage Browser
View detailed results in the Cloud Console:
```
https://console.cloud.google.com/storage/browser/project-ddc15d84-7238-4571-a39-eval-results
```

### Vertex AI Console
Track evaluations over time:
```
https://console.cloud.google.com/vertex-ai/experiments
```

## Evaluation Metrics

### FINAL_RESPONSE_QUALITY
Measures overall appropriateness, helpfulness, and correctness of agent responses.

**Score Interpretation:**
- `< 0.7`: Needs immediate attention
- `0.7-0.85`: Good but can improve
- `> 0.85`: Excellent performance

### TOOL_USE_QUALITY
Evaluates whether the agent uses the correct tools and uses them properly.

**Evaluation Criteria:**
- Correct tool selection for the query
- Proper tool parameters
- Appropriate use of tool responses

### HALLUCINATION
Detects fabricated or incorrect information in responses.

**Detection:**
- Information not supported by tool responses
- Incorrect facts or details
- Made-up order IDs, invoice numbers, etc.

### SAFETY
Checks responses for harmful, biased, or unsafe content.

**Safety Categories:**
- Harmful content
- Bias and fairness
- Privacy violations

## Customization

### Using a Different Dataset

Available datasets:
- `billing_queries.evalset.json` - 3 billing/invoice/payment test cases
- `parallel_agent.evalset.json` - 3 ParallelAgent (comprehensive product lookup) test cases
- `sequential_agent.evalset.json` - 3 SequentialAgent (refund workflow) test cases
- `loop_agent.evalset.json` - 2 LoopAgent (multi-product details) test cases

To use a different dataset:
1. Edit the script constant in `run_agent_evaluation.py`:
   ```python
   DATASET_FILE = os.path.join(SCRIPT_DIR, "datasets", "parallel_agent.evalset.json")
   ```

For `run_single_eval.py`, change the DATASET_FILE variable or pass it as an argument.

Dataset format:
```json
{
  "eval_set_id": "your_test_set",
  "eval_cases": [
    {
      "eval_id": "test_case_1",
      "conversation": [
        {
          "user_content": {
            "parts": [{"text": "Your test query"}],
            "role": "user"
          }
        }
      ]
    }
  ]
}
```

### Changing Evaluation Metrics

Modify the metrics list in `create_evaluation_run()`:

```python
metrics=[
    types.RubricMetric.FINAL_RESPONSE_QUALITY,
    types.RubricMetric.TOOL_USE_QUALITY,
    # Add or remove metrics as needed
]
```

Available metrics:
- `FINAL_RESPONSE_QUALITY`
- `TOOL_USE_QUALITY`
- `HALLUCINATION`
- `SAFETY`

## Troubleshooting

### Evaluation Run Shows FAILED but Agent Responses Are Correct

**Problem:** The evaluation completes with `FAILED` status, but when you check GCS, the agent responses look correct.

**Root Cause:** Judge model quota exhaustion. The error in the evaluation run shows:
```
code=RESOURCE_EXHAUSTED, message=Judge model resource exhausted. Please try again later.
```

**What's happening:**
- ✅ Agent inference works perfectly
- ✅ Responses are captured in GCS
- ❌ Metrics computation fails due to judge model quota limits

**Solutions:**

1. **Wait and Retry** (Recommended)
   - Judge model quota replenishes over time
   - Wait 1-2 hours and run again:
     ```bash
     python online_evaluation/run_agent_evaluation.py
     ```

2. **Run Single Test Cases** (Best for debugging)
   - Evaluate one test case at a time:
     ```bash
     python online_evaluation/run_single_eval.py --test-index 0
     python online_evaluation/run_single_eval.py --test-index 1 --delay 120
     ```

3. **Run Sequential Evaluation** (Automated)
   - Automatically evaluates all test cases with delays:
     ```bash
     ./online_evaluation/run_sequential_eval.sh
     ```
   - Uses 2-minute delays between evaluations
   - Prompts to continue if a test fails

4. **Request Quota Increase**
   - Go to: https://console.cloud.google.com/iam-admin/quotas
   - Search for "Gen AI Evaluation" or "Vertex AI"
   - Request increase for judge model quota

**Check if this is the issue:**
```bash
# Get evaluation run details
gcloud ai evaluations runs describe EVALUATION_RUN_ID \
  --location=us-central1 \
  --format=json | grep -i "exhausted\|quota"
```

### "Agent not found" Error
- Verify `AGENT_ENGINE_RESOURCE_NAME` is correct
- Check agent is deployed:
  ```bash
  gcloud ai reasoning-engines list --location=us-central1
  ```

### "Permission denied" Error
- Ensure you have `roles/aiplatform.user` permission
- Grant `roles/storage.admin` for GCS bucket access

### Network Errors During Polling
- The script automatically retries up to 3 times
- If persistent, check evaluation status manually:
  ```python
  evaluation_run = client.evals.get_evaluation_run(name="EVAL_RUN_NAME")
  print(evaluation_run.state)
  print(evaluation_run.error)  # Check for error details
  ```

## Best Practices

### Test Coverage
- Include diverse query types (products, orders, billing)
- Add edge cases and error scenarios
- Test multi-turn conversations
- Cover all specialist agents

### Evaluation Frequency
- Run after significant agent changes
- Schedule regular evaluations (weekly/monthly)
- Compare with baseline results
- Track metrics over time

### Interpreting Results
1. Review summary metrics first
2. Identify low-scoring test cases
3. Analyze tool usage patterns
4. Check for systematic issues
5. Prioritize improvements

## Resources

- [Agent Builder Evaluation Guide](https://docs.cloud.google.com/agent-builder/agent-engine/evaluate)
- [Evaluation Metrics Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-metrics)
- [Agent Engine Documentation](https://docs.cloud.google.com/agent-builder/docs/agent-engine)
- [Official Example Notebook](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/create_genai_agent_evaluation.ipynb)
