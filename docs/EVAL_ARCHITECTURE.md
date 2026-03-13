# Production Evaluation Architecture

> This document covers the deployed agent evaluation architecture. For CI/CD pipeline evaluation strategy and profiles, see [EVAL_STRATEGY.md](./EVAL_STRATEGY.md).

## Overview

This document describes the 6-stage production evaluation architecture for the Customer Support Multi-Agent System. Each stage uses different tools and serves a different purpose in the quality assurance pipeline.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EVALUATION PIPELINE                              │
│                                                                     │
│  Stage 1       Stage 2       Stage 3       Stage 4       Stage 5-6 │
│  ┌─────┐      ┌─────┐      ┌─────┐      ┌─────┐      ┌─────┐     │
│  │LOCAL│──────│ CI  │──────│STAGE│──────│PROD │──────│MONIT│     │
│  │ DEV │      │PIPE │      │EVAL │      │SMOKE│      │  OR │     │
│  └─────┘      └─────┘      └─────┘      └─────┘      └─────┘     │
│  ADK local    ADK+pytest   Vertex AI    Vertex AI    Vertex AI    │
│  InMemory     InMemory     Eval Svc     Eval Svc     Monitoring   │
│  Runner       Runner       (deployed)   (deployed)   (continuous) │
└─────────────────────────────────────────────────────────────────────┘
```

## Stage Summary

| Stage | Name | Tool | Trigger | Status |
|-------|------|------|---------|--------|
| 1 | Local Development | ADK AgentEvaluator + InMemoryRunner | Manual | **BUILT** |
| 2 | CI Pipeline | ADK AgentEvaluator + pytest | PR/push/nightly | **BUILT** |
| 3 | Staging Eval | Vertex AI Gen AI Eval Service | Post-deploy to staging | **TESTED** |
| 4 | Production Smoke | Vertex AI Gen AI Eval Service | Post-deploy to prod | **TESTED** (same script) |
| 5 | Production Monitor | Vertex AI Model Monitoring | Continuous | Beyond scope |
| 6 | Periodic Regression | Vertex AI Gen AI Eval Service | Nightly/weekly cron | **TESTED** (same script) |

---

## Stage 1: Local Development

**Purpose:** Fast feedback loop during development.

**Tools:** ADK `AgentEvaluator`, `InMemoryRunner`, mocked Firestore backend

**Metrics:** Rouge-1, tool trajectory (exact match on structured args)

**How to run:**
```bash
# Run unit tests with eval
pytest tests/unit/ -v -s

# Run integration tests
pytest tests/integration/ -v -s

# Use fast profile for quick feedback
EVAL_PROFILE=fast pytest tests/unit/ -v -s
```

**Key files:**
- `tests/unit/test_agent_eval_ci.py` — unit-level agent evals
- `tests/integration/test_integration_eval_ci.py` — integration evals
- `tests/conftest.py` — mock setup for Firestore

---

## Stage 2: CI Pipeline

**Purpose:** Automated quality gate on every PR/push.

**Tools:** ADK `AgentEvaluator` + `InMemoryRunner` + pytest

**Metrics:** Vary by profile:
- `fast` (PR): Rouge-1 only — free, fast
- `standard` (push to main): + tool trajectory (unit), rubric-based LLM judge (integration)
- `full` (nightly/release): + final_response_match_v2

**CI/CD mapping:**
| Event | Profile | Gate |
|-------|---------|------|
| Pull Request | `fast` | Must pass to merge |
| Push to main | `standard` | Blocks deployment |
| Nightly | `full` | Alerts on degradation |
| Release gate | `full` | Must pass to deploy |

**How to run:**
```bash
# Simulate CI profiles locally
EVAL_PROFILE=fast pytest tests/ -v
EVAL_PROFILE=standard pytest tests/ -v
EVAL_PROFILE=full pytest tests/ -v
```

**Key files:**
- `.github/workflows/` — CI workflow definitions
- `tests/eval_configs/unit/{fast,standard,full}.json`
- `tests/eval_configs/integration/{fast,standard,full}.json`
- `tests/eval_configs/__init__.py` — profile loader

---

## Stage 3: Staging Deployment Eval

**Purpose:** Evaluate the *deployed* agent (not local code) before promoting to production.

**Tools:** Vertex AI Gen AI Evaluation Service (`client.evals`)

**Metrics:**
- `TOOL_USE_QUALITY` — Did the agent use the right tools with correct parameters?
- `FINAL_RESPONSE_QUALITY` — Is the response accurate and helpful?
- `HALLUCINATION` (full profile) — Did the agent fabricate information?
- `SAFETY` (full profile) — Is the response safe and appropriate?

**How it works:**
1. Deploy agent to staging Agent Engine
2. Run `eval_vertex.py` against the staging deployment
3. Script sends prompts → collects responses → runs Vertex AI eval metrics
4. HTML report saved locally as `eval-TIMESTAMP.html` (e.g. `eval-20260306-152928.html`)
5. If `GOOGLE_CLOUD_STORAGE_BUCKET` is set: report uploaded to `gs://BUCKET/eval-reports/eval-TIMESTAMP.html`
6. Results logged to Vertex AI Experiments as run `eval-TIMESTAMP`; GCS URI recorded as a param in the run — all three (file, GCS path, experiment run) share the same timestamp for easy correlation
7. If all metrics pass thresholds → promote to production
8. If any metric fails → block promotion, alert team

**How to run:**
```bash
# Standard eval (tool use + response quality) — uses custom inference adapter
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID

# Full eval (+ hallucination + safety)
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID \
    --profile full

# Custom dataset
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID \
    --dataset tests/post_deploy/datasets/post_deploy_cases.json

# Save results + debug inference
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID \
    --output eval_results.json \
    --save-inference inference_debug.json

# Use SDK's built-in inference (single-agent systems only)
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID \
    --sdk-inference

# Adjust delay between prompts (default 3s, increase for rate limit issues)
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID \
    --delay 8.0
```

**CLI flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--agent-engine-id` | required | Full resource name of the deployed Agent Engine |
| `--profile` | `standard` | Eval config profile (`standard` or `full`) |
| `--dataset` | `post_deploy_cases.json` | Path to eval dataset JSON |
| `--output` | none | Save results to JSON file |
| `--delay` | `3.0` | Seconds between prompts (rate limit protection) |
| `--sdk-inference` | off | Use SDK's `run_inference()` instead of custom adapter |
| `--save-inference` | none | Save raw prompt/response pairs to JSON for debugging |

**Key files:**
- `scripts/eval_vertex.py` — main eval script
- `tests/eval_configs/post_deploy/{standard,full}.json` — metric configs
- `tests/post_deploy/datasets/post_deploy_cases.json` — eval dataset (10 cases)
- `tests/post_deploy/dataset_converter.py` — ADK → Vertex AI format converter

### Custom Inference Adapter vs SDK Inference

The eval script uses a **custom inference adapter** by default instead of the SDK's built-in `run_inference()`. This is required for multi-agent systems that use `AgentTool`.

**Why the SDK's `run_inference()` fails for AgentTool:**

The SDK's internal parser extracts the final response with:
```python
resp_item[-1]["content"]["parts"][0]["text"]
```

With `AgentTool`, the conversation flow is:
1. Root agent emits a `function_call` event (delegating to sub-agent)
2. Sub-agent returns a `function_response` event (with result text)
3. Root agent emits a final `text` event (human-readable response)

The SDK only captures events 1-2 and stops — it never sees the final text response (event 3). When it tries to parse event 2 (a `function_response`), it fails with `'text'` key not found.

**How the custom adapter works:**

The custom adapter uses `async_stream_query()` which yields ALL events including the final text response. This matches how the production backend (`backend/app/agent_client.py`) processes Agent Engine responses.

```
SDK run_inference():         function_call → function_response → STOPS (parse error)
Custom adapter:              function_call → function_response → text response → DONE
Production backend:          function_call → function_response → text response → DONE
```

> **Note:** `stream_query()` (sync) also has issues — it only yields the first event for AgentTool calls. Always use `async_stream_query()`.

**When to use `--sdk-inference`:**
- Only for single-agent systems or agents that don't use `AgentTool`
- For debugging/comparison with the custom adapter

### Resilience Features

The script includes retry logic for common transient failures:

- **Agent Engine 503s:** `async_stream_query()` sometimes returns `503 UNAVAILABLE` (gRPC connection issues). The adapter retries up to 3 times with exponential backoff (5s, 10s).
- **Polling SSL errors:** `get_evaluation_run()` can hit transient SSL/connection errors during the polling loop. Up to 5 consecutive failures are tolerated before giving up.

### Judge Rate Limits

The eval service uses Gemini as an LLM judge to score responses. With 10 items and 2 metrics, that's 20 judge calls which can hit `RESOURCE_EXHAUSTED` rate limits. Items that fail at the judge level show as `failed_items` in the results — they are excluded from scoring, not counted as quality failures.

**Tips to improve judge success rate:**
- Use smaller datasets (3-5 items) for more reliable scoring
- Increase `--delay` between prompts
- Run at off-peak hours

### Prerequisites

Before running post-deploy eval:

1. **Agent Engine deployed** with a valid resource name
2. **Firestore permissions:** The Vertex AI service agent (`service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com`) must have `roles/datastore.user` to access Firestore:
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com" \
     --role="roles/datastore.user"
   ```
3. **GCS bucket** for report upload: set `GOOGLE_CLOUD_STORAGE_BUCKET` in `.env` — the script uploads the HTML report to `gs://BUCKET/eval-reports/eval-TIMESTAMP.html` and records the URI in the Vertex AI Experiments run. Without this, the report is saved locally only and the experiment run will have no `report_gcs_uri` param.
4. **Dataset IDs must match seeded Firestore data** — use real order/invoice IDs (e.g., `ORD-12345`, `ORD-67890`, `INV-2025-001`), not placeholder IDs

### AgentInfo Workaround

The eval service requires `AgentInfo` to provide tool declarations and agent instructions. The standard method `AgentInfo.load_from_agent()` fails for this project because:
- ADK `PreloadMemoryTool` lacks `__globals__` → `typing.get_type_hints()` crashes
- Sub-agents wrapped as `AgentTool` cause recursive introspection failures

The script builds `AgentInfo` manually instead:
```python
agent_info = types.evals.AgentInfo(
    agent_resource_name=agent_engine_id,
    name=root_agent.name,
    instruction=root_agent.instruction or "",
)
```

---

## Stage 4: Production Smoke Test

**Purpose:** Quick sanity check after deploying to production.

**Tools:** Same as Stage 3 (`eval_vertex.py`)

**How it differs from Stage 3:**
- Uses a smaller dataset (fewer prompts)
- Runs with `standard` profile (no hallucination/safety — faster)
- If smoke test fails → automatic rollback

**How to run:**
```bash
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/apps/PROD_APP_ID \
    --dataset tests/post_deploy/datasets/post_deploy_cases.json
```

---

## Stage 5: Production Monitoring (Beyond Scope)

**Purpose:** Continuously monitor live traffic for quality degradation.

**Tools:** Vertex AI Model Monitoring, Cloud Logging, custom pipelines

**What it would measure:**
- Response latency percentiles
- Error rates by agent
- Tool call success rates
- Quality scores on sampled traffic
- Safety/hallucination on sampled traffic

**Why it's beyond scope:** Requires logging infrastructure, dashboards, and sampling pipelines that are separate from the eval system.

---

## Stage 6: Periodic Regression

**Purpose:** Detect model drift and quality degradation over time.

**Tools:** Same as Stage 3 (`eval_vertex.py`), run on a schedule

**How to run:**
```bash
# Nightly full regression
python scripts/eval_vertex.py \
    --agent-engine-id projects/PROJECT/locations/LOCATION/apps/PROD_APP_ID \
    --profile full \
    --output results/nightly-$(date +%Y%m%d).json
```

---

## Tool Comparison: ADK AgentEvaluator vs Vertex AI Eval Service

| Feature | ADK AgentEvaluator | Vertex AI Eval Service |
|---------|-------------------|----------------------|
| **Runs against** | Local agent (InMemoryRunner) | Deployed Agent Engine app |
| **Speed** | Fast (in-process) | Slower (network calls) |
| **Cost** | Free (local compute) | Vertex AI pricing |
| **Metrics** | Rouge-1, tool trajectory, response match, rubric judges | TOOL_USE_QUALITY, FINAL_RESPONSE_QUALITY, HALLUCINATION, SAFETY |
| **Use case** | Dev/CI (Stages 1-2) | Post-deploy (Stages 3-4, 6) |
| **Mocking** | Mocked backends | Real backends (Firestore, etc.) |
| **Environment** | Local / CI runner | GCP project with Agent Engine |

**When to use which:**
- **ADK AgentEvaluator**: Development and CI — fast, free, tests agent logic
- **Vertex AI Eval Service**: Post-deployment — tests the full deployed stack including infrastructure, latency, and real data access

---

## Eval Profile System

All stages support the `EVAL_PROFILE` environment variable:

| Profile | Unit Metrics | Integration Metrics | Post-Deploy Metrics |
|---------|-------------|--------------------|--------------------|
| `fast` | Rouge-1 | Rouge-1 | — |
| `standard` | Rouge-1 + tool trajectory | Rouge-1 + rubric judge | TOOL_USE_QUALITY + FINAL_RESPONSE_QUALITY |
| `full` | + response match v2 | + response match v2 | + HALLUCINATION + SAFETY |

**CI/CD mapping:**
```
PR          → fast       (quick feedback, free)
Push main   → standard   (balanced quality gate)
Nightly     → full       (comprehensive regression)
Release     → full       (must pass before deploy)
Post-deploy → standard   (deployed agent quality)
```

---

## Dataset Format

### Post-Deploy Dataset (`post_deploy_cases.json`)

Simple JSON array for the Vertex AI Eval Service:

```json
[
  {
    "prompt": "Where is my order ORD-12345?",
    "reference": "Your order ORD-12345 is currently in transit via FastShip.",
    "expected_tool_use": [
      {"tool_name": "order_agent", "tool_input": {"request": "track order ORD-12345"}}
    ]
  }
]
```

**Important:** The `"prompt"` column name is required — the eval service SDK looks for this exact key when building `EvaluationItemRequest` objects. Using `"request"` instead will cause all items to fail with `INTERNAL` errors.

**Dataset IDs must match seeded Firestore data:**

| Entity | Valid IDs (demo-user-001) |
|--------|--------------------------|
| Orders | `ORD-12345` (In Transit), `ORD-67890` (Delivered, refundable), `ORD-11111` (Delivered, past window) |
| Invoices | `INV-2025-001` (Pending), `INV-2025-002` (Paid), `INV-2024-003` (Paid) |
| Products | `PROD-001` through `PROD-006` |

### ADK EvalSet (`.evalset.json`)

Use the dataset converter to transform ADK evalsets to Vertex AI format:

```python
from tests.post_deploy.dataset_converter import adk_evalset_to_dataframe

df = adk_evalset_to_dataframe("tests/integration/product_agent_handoffs.evalset.json")
```

---

## Thresholds

### Standard Profile
| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| TOOL_USE_QUALITY | 0.5 | Agent uses correct tools for >50% of queries |
| FINAL_RESPONSE_QUALITY | 0.5 | Responses are accurate and helpful >50% of time |

### Full Profile
| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| TOOL_USE_QUALITY | 0.5 | Same as standard |
| FINAL_RESPONSE_QUALITY | 0.5 | Same as standard |
| HALLUCINATION | 0.5 | Agent doesn't fabricate information |
| SAFETY | 0.8 | Higher bar — safety is critical |

Thresholds should be adjusted upward as the agent matures. Start conservative and ratchet up.
