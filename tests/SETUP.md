# Evaluation Testing Setup

## Prerequisites

### 1. Install Python Dependencies

```bash
# Install pytest
pip install pytest pytest-asyncio

# Install ADK evaluation dependencies
pip install "google-adk[eval]"
```

### 2. Set PYTHONPATH

Before running pytest, ensure the project root is in PYTHONPATH:

```bash
export PYTHONPATH=/home/saoussen/customer-support-mas
```

Or run pytest with PYTHONPATH inline:

```bash
PYTHONPATH=/home/saoussen/customer-support-mas pytest tests/
```

## Running Tests

### Run All Tests

```bash
PYTHONPATH=$(pwd) pytest tests/
```

### Run Specific Test Category

```bash
# Unit tests only
PYTHONPATH=$(pwd) pytest tests/test_customer_support.py::TestUnitEvaluation

# Integration tests only
PYTHONPATH=$(pwd) pytest tests/test_customer_support.py::TestIntegrationEvaluation

# Regression suite
PYTHONPATH=$(pwd) pytest tests/test_customer_support.py::TestRegressionSuite
```

### Run Single Test

```bash
PYTHONPATH=$(pwd) pytest tests/test_customer_support.py::TestUnitEvaluation::test_product_search -v
```

### Run with Detailed Output

```bash
# Verbose output
PYTHONPATH=$(pwd) pytest tests/ -v

# Show print statements
PYTHONPATH=$(pwd) pytest tests/ -v -s

# Short traceback
PYTHONPATH=$(pwd) pytest tests/ --tb=short
```

## Troubleshooting

### Error: "No module named 'customer_support_agent'"

**Solution:** Set PYTHONPATH to project root:
```bash
export PYTHONPATH=/home/saoussen/customer-support-mas
```

### Error: "No module named 'rouge_score'"

**Solution:** Install evaluation dependencies:
```bash
pip install "google-adk[eval]"
```

### Error: "AgentEvaluator.evaluate() got an unexpected keyword argument 'config_file_path'"

**Solution:** The `config_file_path` parameter is not supported in pytest tests. Evaluation criteria should be defined in the evalset files themselves, not in a separate config file.

### Tests Are Slow

**Note:** Agent evaluation tests can take several minutes because they:
1. Load the full agent system
2. Run inference with the LLM
3. Evaluate responses using multiple metrics
4. Run each test case multiple times (default: 2 runs)

Expect ~30-60 seconds per test case.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Agent Evaluation Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio
          pip install "google-adk[eval]"
          pip install -r requirements.txt

      - name: Run evaluation tests
        run: |
          PYTHONPATH=$(pwd) pytest tests/
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Running agent evaluation tests..."
PYTHONPATH=$(pwd) pytest tests/

if [ $? -ne 0 ]; then
  echo "❌ Tests failed. Commit aborted."
  exit 1
fi

echo "✅ All tests passed."
```

## Test Configuration

### Adjusting Number of Runs

The `AgentEvaluator.evaluate()` method runs each test case multiple times (default: 2).

To change this, you would need to modify the test code:

```python
await AgentEvaluator.evaluate(
    agent_module="customer_support_agent.agent",
    eval_dataset_file_path_or_dir="tests/unit/product_search.evalset.json",
    num_runs=3,  # Run each test 3 times
    print_detailed_results=True
)
```

### Evaluation Criteria

Evaluation criteria are embedded in the evalset JSON files:
- `tool_uses` - Expected tool calls with parameters
- `final_response` - Expected response text

The evaluator automatically compares:
- **Tool trajectory** - Did agent use correct tools?
- **Response match** - Is response similar to expected output?

## Useful Commands

```bash
# Run tests with coverage
PYTHONPATH=$(pwd) pytest tests/ --cov=customer_support_agent

# Run tests and generate HTML report
PYTHONPATH=$(pwd) pytest tests/ --html=report.html

# Run tests in parallel (if you have pytest-xdist)
PYTHONPATH=$(pwd) pytest tests/ -n auto

# Run tests and stop on first failure
PYTHONPATH=$(pwd) pytest tests/ -x
```
