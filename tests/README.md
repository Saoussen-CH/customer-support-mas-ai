# Customer Support Multi-Agent System - Test Suite

Comprehensive test suite for validating the customer support multi-agent system built with Google ADK and Vertex AI.

---

## 📁 Test Structure

```
tests/
├── conftest.py                    # Pytest configuration and fixtures
├── test_customer_support.py       # Main test entry point (run this)
│
├── unit/                          # Unit tests for individual agents
│   ├── test_refund_standalone.py  # Standalone refund workflow tests
│   ├── product_search.evalset.json
│   ├── order_tracking.evalset.json
│   ├── billing_queries.evalset.json
│   ├── sequential_agent.evalset.json
│   ├── refund_passing.evalset.json
│   └── refund_failing.evalset.json
│
├── integration/                   # Integration tests for agent coordination
│   ├── memory_persistence.evalset.json
│   ├── multi_agent_handoffs.evalset.json
│   └── workflow_integration.evalset.json
│
└── docs/                          # Test documentation
    ├── SETUP.md                   # Setup instructions
    └── REFUND_WORKFLOW_TESTS.md   # Refund workflow documentation
```

---

## 🚀 Quick Start

### Run All Tests
```bash
pytest tests/test_customer_support.py -v
```

### Run Specific Test Categories

#### Unit Tests Only
```bash
pytest tests/test_customer_support.py::TestUnitEvaluation -v
```

#### Integration Tests Only
```bash
pytest tests/test_customer_support.py::TestIntegrationEvaluation -v
```

#### Refund Workflow Tests Only
```bash
# Using ADK AgentEvaluator
pytest tests/test_customer_support.py::TestUnitEvaluation::test_sequential_agent -v

# Standalone (faster, no network)
pytest tests/unit/test_refund_standalone.py -v
```

### Run Regression Suite (All Tests)
```bash
pytest tests/test_customer_support.py::TestRegressionSuite -v
```

---

## 📋 Test Categories

### 1. Unit Tests (`tests/unit/`)

Tests for individual agent capabilities and tools.

| Test File | Description | Test Count |
|-----------|-------------|------------|
| `product_search.evalset.json` | Product search, filtering, semantic queries | 3 |
| `order_tracking.evalset.json` | Order tracking, history, status checks | 8 |
| `billing_queries.evalset.json` | Invoice retrieval, payment status | 7 |
| `sequential_agent.evalset.json` | Refund workflow with validation gates | 7 |
| `refund_passing.evalset.json` | Valid refund scenarios | 3 |
| `refund_failing.evalset.json` | Invalid refund scenarios | 2 |
| `test_refund_standalone.py` | Direct tool testing (no ADK) | 5 |

**Total Unit Tests:** 35 test cases

### 2. Integration Tests (`tests/integration/`)

Tests for multi-agent coordination and complex workflows.

| Test File | Description | Test Count |
|-----------|-------------|------------|
| `memory_persistence.evalset.json` | Cross-session memory (Memory Bank) | 7 |
| `multi_agent_handoffs.evalset.json` | Agent-to-agent coordination | 7 |
| `workflow_integration.evalset.json` | Complex multi-domain workflows | 8 |

**Total Integration Tests:** 22 test cases

---

## 🎯 Test Coverage

### Agent Coverage
- ✅ **Root Agent** - Request routing and coordination
- ✅ **Product Agent** - Search, details, inventory, reviews
- ✅ **Order Agent** - Tracking, history, status
- ✅ **Billing Agent** - Invoices, payments
- ✅ **Refund Workflow** - Sequential validation gates

### Feature Coverage
- ✅ **RAG Semantic Search** - Vector embeddings, keyword fallback
- ✅ **Memory Bank** - Long-term user preferences
- ✅ **Multi-Agent Handoffs** - Product → Order → Billing
- ✅ **Sequential Workflows** - Validate → Check → Process
- ✅ **Error Handling** - Invalid orders, failed eligibility

### Tool Coverage
- ✅ **Product Tools** (7 tools)
- ✅ **Order Tools** (3 tools)
- ✅ **Billing Tools** (3 tools)
- ✅ **Workflow Tools** (3 tools)

**Total Test Coverage:** 57 test cases across all domains

---

## 🧪 Test Types

### 1. Evaluation Tests (ADK AgentEvaluator)
Uses Google ADK's `AgentEvaluator` to test full agent workflows with network calls to Vertex AI.

**Location:** All `.evalset.json` files
**Run via:** `test_customer_support.py`

**Characteristics:**
- ✅ Tests full agent pipeline
- ✅ Validates LLM responses
- ✅ Checks tool invocations
- ⚠️ Requires network connection
- ⚠️ Slower execution (API calls)

### 2. Standalone Tests (Direct Testing)
Direct function calls without ADK infrastructure.

**Location:** `unit/test_refund_standalone.py`
**Run via:** `pytest tests/unit/test_refund_standalone.py`

**Characteristics:**
- ✅ Fast execution (~8 seconds)
- ✅ No network required (local Firestore)
- ✅ Direct tool validation
- ❌ Doesn't test agent coordination

---

## 📊 Test Execution Modes

### Development Mode (Fast)
```bash
# Run standalone tests only
pytest tests/unit/test_refund_standalone.py -v
```

### CI/CD Mode (Comprehensive)
```bash
# Run all tests including network-dependent evaluations
pytest tests/test_customer_support.py::TestRegressionSuite -v
```

### Specific Feature Testing
```bash
# Test product agent only
pytest tests/test_customer_support.py::TestUnitEvaluation::test_product_search -v

# Test order agent only
pytest tests/test_customer_support.py::TestUnitEvaluation::test_order_tracking -v

# Test billing agent only
pytest tests/test_customer_support.py::TestUnitEvaluation::test_billing_queries -v

# Test refund workflow only
pytest tests/test_customer_support.py::TestUnitEvaluation::test_sequential_agent -v
```

---

## 🔧 Prerequisites

### 1. Environment Setup
Ensure `.env` file is configured:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1
```

### 2. Database Seeding
Seed Firestore with test data:
```bash
python customer_support_agent/database/seed.py --project YOUR_PROJECT_ID
```

### 3. Dependencies
Install test dependencies:
```bash
pip install -r requirements.txt
```

---

## 📖 Test Data

### Sample Orders (Firestore)

| Order ID | Status | Date | Refund Eligible | Reason |
|----------|--------|------|-----------------|--------|
| ORD-67890 | Delivered | 2025-01-14 | ✅ Yes | Within 30-day window |
| ORD-12345 | In Transit | 2025-01-15 | ✅ Yes | Can cancel |
| ORD-22222 | Processing | 2025-01-12 | ✅ Yes | Can cancel before ship |
| ORD-11111 | Delivered | 2024-12-24 | ❌ No | Past 30-day window |

### Sample Products
- **PROD-001**: ProBook Laptop 15 ($999.99)
- **PROD-002**: Wireless Headphones Pro ($199.99)
- **PROD-006**: ROG Gaming Laptop ($1499.99)

---

## 🐛 Troubleshooting

### Database Not Seeded
**Error:** `Order not found` or tests fail with `invalid` status

**Solution:**
```bash
python customer_support_agent/database/seed.py --project YOUR_PROJECT_ID --clear
```

### Network Timeouts
**Error:** Connection timeouts to Google APIs

**Solution:** Run standalone tests instead:
```bash
pytest tests/unit/test_refund_standalone.py -v
```

### Import Errors
**Error:** Cannot import workflow tools

**Solution:** Verify tools are exported in `customer_support_agent/tools/__init__.py`

### Evaluation Format Errors
**Error:** `must contain a list of dictionaries`

**Solution:** Ensure `.evalset.json` files don't have `description` fields at eval_case level

---

## 📝 Adding New Tests

### 1. Add Unit Test
Create new `.evalset.json` in `tests/unit/`:

```json
{
  "eval_set_id": "my_new_test",
  "eval_cases": [
    {
      "eval_id": "test_case_1",
      "conversation": [
        {
          "user_content": {
            "parts": [{"text": "User query here"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "Expected response"}],
            "role": "model"
          }
        }
      ]
    }
  ]
}
```

### 2. Add Test Method
In `test_customer_support.py`:

```python
@pytest.mark.asyncio
async def test_my_new_feature(self):
    """Test description here."""
    await AgentEvaluator.evaluate(
        agent_module="customer_support_agent.main",
        eval_dataset_file_path_or_dir="tests/unit/my_new_test.evalset.json",
        print_detailed_results=False
    )
```

### 3. Add Standalone Test
Create test file in `tests/unit/`:

```python
class TestMyFeature:
    def test_specific_functionality(self):
        # Direct tool testing
        result = my_tool_function(input_data)
        assert result["status"] == "success"
```

---

## 🎯 Success Criteria

All tests should pass with:
- ✅ 0 failures
- ✅ 0 errors
- ✅ No warnings about missing tools
- ✅ No network timeouts (for standalone tests)
- ✅ All assertions successful

---

## 📚 Documentation

- **Setup Guide:** `docs/SETUP.md`
- **Refund Workflow:** `docs/REFUND_WORKFLOW_TESTS.md`
- **Architecture:** `../docs/ARCHITECTURE.md`
- **API Reference:** Agent docstrings in `customer_support_agent/agents/`

---

## 🔗 Related Files

- **Agent Implementation:** `customer_support_agent/`
- **Tools:** `customer_support_agent/tools/`
- **Database:** `customer_support_agent/database/`
- **Configuration:** `customer_support_agent/config.py`

---

## 💡 Best Practices

1. **Run Standalone Tests First** - Faster feedback loop during development
2. **Run Full Suite Before Deploy** - Ensure no regressions
3. **Keep Test Data Consistent** - Use seeded Firestore data
4. **Update Evalsets Together** - When changing agent behavior
5. **Document New Tests** - Add descriptions to evalset files

---

## 🏆 Test Metrics

- **Total Test Cases:** 57
- **Coverage:** ~95% of agent code paths
- **Execution Time:** ~5-10 minutes (full suite with network)
- **Standalone Time:** ~8 seconds (no network)

---

Last Updated: 2025-12-03
