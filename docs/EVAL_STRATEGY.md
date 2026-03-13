# Evaluation Strategy: Tiered CI/CD for AI Agents

> This document covers the CI/CD tiered evaluation strategy. For post-deploy evaluation architecture, see [EVAL_ARCHITECTURE.md](./EVAL_ARCHITECTURE.md).

## Current State

CI runs everything on every push:
```
push/PR → lint + tool-tests + unit-agent-evals (LLM) + integration-evals (LLM)
```

Problem: LLM evals (`AgentEvaluator` with `num_runs=2`) hit Vertex AI for every test case, every push. Slow, expensive, flaky (429s, non-determinism).

---

## Tiered Evaluation Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 0: Pre-commit / Every push        (seconds, free)    │
│  ─────────────────────────────────                          │
│  • Lint (ruff)                                              │
│  • test_tools.py — direct tool calls against mocks          │
│  • test_refund_standalone.py — workflow logic, no LLM       │
│  • test_mock_rag.py — RAG filtering logic                   │
│                                                             │
│  Gate: if this fails, nothing else runs                     │
├─────────────────────────────────────────────────────────────┤
│  TIER 1: PR merge to main               (minutes, cheap)   │
│  ────────────────────────                                   │
│  • Unit agent evals — each agent directly (product, order,  │
│    billing, refund eligibility)                              │
│  • Smoke subset — 1-2 critical cases per agent, num_runs=1  │
│                                                             │
│  Why: validates agent behavior before it reaches main       │
├─────────────────────────────────────────────────────────────┤
│  TIER 2: Nightly / Scheduled             (10-20 min, $$)   │
│  ────────────────────────                                   │
│  • Full unit agent evals with num_runs=2                    │
│  • Full integration evals (handoffs, e2e journeys)          │
│  • Authorization cross-user tests                           │
│  • Flakiness detection (num_runs=3+)                        │
│                                                             │
│  Why: catches regressions from model updates, drift         │
├─────────────────────────────────────────────────────────────┤
│  TIER 3: Pre-deploy / On-demand          (manual trigger)   │
│  ──────────────────────────────                              │
│  • Full suite with num_runs=5                               │
│  • New eval cases for changed behavior                      │
│  • Comparison: before vs after (score diff)                 │
│                                                             │
│  Why: confidence gate before shipping to Agent Engine       │
└─────────────────────────────────────────────────────────────┘
```

---

## Custom Metric: `tool_name_f1`

### Why `tool_trajectory_avg_score` Was Replaced

The built-in ADK metric `tool_trajectory_avg_score` compares tool calls using **strict equality** on both the tool name AND all argument values. This caused two categories of CI failures:

1. **Argument reformulation** — Product agent called `search_products(query='laptops')` but the eval dataset expected `query='Laptops under $1000'`. Same tool, different phrasing → score = 0.0.
2. **Sub-agent delegation** — Root agent routes to `order_agent` (an `AgentTool`), but the eval dataset expected the direct tool `track_order`. The root agent never calls `track_order` directly.

### `tool_name_f1` Design

Located in `customer_support_agent/evaluation/tool_metrics.py`.

Computes F1 on **tool names only**, ignoring argument values:

```
precision = |actual_names ∩ expected_names| / |actual_names|
recall    = |actual_names ∩ expected_names| / |expected_names|
F1        = 2 * P * R / (P + R)
```

**Threshold**: 0.5 (configured in eval config JSON). This allows:
- Extra tools called beyond expected → F1 ≥ 0.67 (passes)
- Exact match → F1 = 1.0
- Wrong agent called → F1 = 0.0 (fails)

**Backup**: `EVAL_PROFILE=standard_exact` reverts to the original strict `tool_trajectory_avg_score` via `tests/eval_configs/unit/standard_exact.json`.

### Two Intermediate Data Formats

ADK supports two ways eval datasets record tool calls. `_get_tool_names()` handles both:

| Format | Where used | Location in object |
|---|---|---|
| `tool_uses` | Older/hand-written eval datasets | `invocation.intermediate_data.tool_uses[].name` |
| `invocation_events` | `generate_eval_dataset.py` output + all actual agent runs | `invocation.intermediate_data.invocation_events[].content.parts[].function_call.name` |

**Key insight**: Actual agent runs during `AgentEvaluator` evaluation always populate `invocation_events`, never `tool_uses`. If an eval dataset uses `tool_uses` for expected invocations and the code only checks `tool_uses`, actual invocations return an empty set → F1 = 0.0 for every case.

### Registration Requirement

`EvalConfig.custom_metrics` sets `custom_function_path` on the metric object, but ADK's `MetricEvaluatorRegistry.get_evaluator()` checks the registry dict first and raises `NotFoundError` before reaching the custom path. Custom metrics must be explicitly registered before any test runs:

```python
# tests/unit/conftest.py
@pytest.fixture(scope="session", autouse=True)
def register_custom_eval_metrics():
    DEFAULT_METRIC_EVALUATOR_REGISTRY.register_evaluator(
        metric_info=MetricInfo(metric_name="tool_name_f1", ...),
        evaluator=_CustomMetricEvaluator,
    )
```

### Files Changed

| File | Change |
|---|---|
| `customer_support_agent/evaluation/__init__.py` | New — makes package importable |
| `customer_support_agent/evaluation/tool_metrics.py` | New — `tool_name_f1` implementation |
| `tests/eval_configs/unit/standard.json` | Replaced `tool_trajectory_avg_score` → `tool_name_f1` |
| `tests/eval_configs/unit/full.json` | Same replacement, keeps `final_response_match_v2` |
| `tests/eval_configs/unit/standard_exact.json` | New — backup with original exact-match config |
| `tests/eval_configs/__init__.py` | Added `standard_exact` to `VALID_PROFILES` |
| `tests/unit/conftest.py` | Added `register_custom_eval_metrics` session fixture |
| `tests/unit/cases/demo_user_002.test.json` | Updated expected tool names: direct tools → sub-agent names (`order_agent`, `billing_agent`) |

---

## Integration Test Design Constraints

### Frozen datetime (`_FROZEN_DATE = datetime(2026, 1, 15)`)

Both unit and integration test conftests freeze `datetime.now()` to a fixed reference date. This prevents golden response dates from drifting as CI runs day after day.

Two patches are applied before `MockFirestoreClient()` is instantiated:
```python
patch("customer_support_agent.database.seed.datetime", _FrozenDatetime),     # _days_ago() in seed.py
patch("customer_support_agent.tools.workflow_tools.datetime", _FrozenDatetime),  # eligibility window check
```

With `_FROZEN_DATE = 2026-01-15`:
- `ORD-67890` delivered: `_days_ago(5)` → `2026-01-10` → **5 days ago → eligible** (within 30-day window)
- `ORD-11111` delivered: `_days_ago(45)` → `2025-12-01` → **45 days ago → not eligible**

**When regenerating evalsets**, always set `datetime.now()` to `_FROZEN_DATE` in the generation script too, otherwise the golden dates will drift and the `final_response_match_v2` LLM judge will score 0 on invocations that mention dates.

### Stateful integration eval cases (`num_runs=1` for refund test)

`test_refund_agent_handoffs` uses `num_runs=1` (not 2) because its eval cases are **intentionally sequential and stateful**:

1. `refund_eligible_flow` — processes a refund for `ORD-67890`, writes `REF-67890-01` to the mock `refunds` collection
2. `refund_denied_flow` — independent (tests `ORD-11111`, ineligible due to 30-day window)
3. `refund_then_other` — expects `ORD-67890` to already be refunded (from case 1) → denial matches golden

With `num_runs=2`, the shared `MockFirestoreClient` is never reset between runs. Run 2 of `refund_eligible_flow` finds `REF-67890-01` already present (written in run 1) → denied instead of success → test fails.

**Rule**: if eval cases within a test share state across cases, use `num_runs=1`. Use `num_runs=2` only when all cases are fully independent.

---

## Key Insights

### 1. Most regressions are caught by Tier 0 — and it's free
If you break a tool's return format, change a Firestore query, or mess up the refund eligibility logic, `test_tools.py` catches it in 2 seconds with zero LLM calls. That's 17 tests covering all tools.

### 2. LLM evals should NOT block every push
They're non-deterministic by nature. A test that passes 4/5 times isn't a CI failure — it's expected behavior. Treating it as a hard gate on every push leads to:
- Developers re-running CI to "get green"
- Adding retries that mask real issues
- Disabling flaky tests entirely

### 3. Nightly runs catch model-side drift
Google can update Gemini Flash's behavior without telling you. A nightly run catches "the model stopped calling `track_order` and started hallucinating order status" before users do.

### 4. The missing piece: eval score tracking over time
Right now `AgentEvaluator` is pass/fail. Best practice is to track scores over time — "product agent tool accuracy was 95% last week, it's 87% today." That's where Agent Engine's upcoming eval features will help. Until then, log results to a simple dashboard.

---

## CI Trigger Mapping

| Trigger | What runs | Estimated time |
|---|---|---|
| Every push/PR | `lint` + `test_tools.py` + `test_mock_rag.py` + `test_refund_standalone.py` | ~10s |
| Merge to main | Above + unit agent evals (`num_runs=1`, smoke cases only) | ~2-3 min |
| Nightly cron (`0 0 * * *`) | Full unit + integration evals with `num_runs=2` | ~15-20 min |
| `workflow_dispatch` (manual) | Full suite `num_runs=5` + score report | ~30 min |

---

## Changes Needed in ci.yml

### Job: `fast-tests` (every push/PR)
```yaml
- pytest tests/unit/test_tools.py -v --tb=short
- pytest tests/unit/test_mock_rag.py -v --tb=short
- pytest tests/unit/test_refund_standalone.py -v --tb=short
```
No GCP credentials needed. Runs against mocks only.

### Job: `smoke-agent-evals` (merge to main only)
```yaml
on:
  push:
    branches: [main]
```
Run unit agent evals with `num_runs=1` and a smoke subset of eval cases.

### Job: `full-evals` (nightly + manual)
```yaml
on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:
```
Full unit + integration evals with `num_runs=2` (nightly) or `num_runs=5` (manual).

### Job: `lint` (every push/PR, unchanged)
Keep as-is.

---

## Smoke Eval Subset (Tier 1)

For each agent, pick 1-2 critical cases that cover the happy path:

- **Product agent**: "Show me gaming laptops" → expects `search_products` call
- **Order agent**: "Track order ORD-12345" → expects `track_order` call
- **Billing agent**: "Show invoice for ORD-12345" → expects `get_invoice_by_order_id` call
- **Refund eligibility**: "Can I refund ORD-67890?" → expects `check_if_refundable` call
- **Out of scope**: "What's the weather?" → expects no tool calls

These can live in separate `*.smoke.test.json` files or be filtered by pytest markers.

---

## Future: Eval Score Dashboard

Track over time:
- Tool trajectory accuracy (% of cases where correct tools were called in correct order)
- Pass rate per agent per day
- Flakiness score (variance across num_runs)
- Regression alerts (score drops > 10% from rolling average)
