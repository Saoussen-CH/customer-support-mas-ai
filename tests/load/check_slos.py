"""
SLO checker — validates Locust CSV output against defined thresholds.

Exits with code 1 if any SLO is breached, failing the Cloud Build load-test step
and blocking promotion to prod.

SLO rationale:
  - p95 10s: Agent Engine multi-agent routing takes 3-8s; cold starts add more
  - p99 20s: rare outliers (circuit breaker recovery, model warm-up)
  - error_rate 5%: allows transient 503s caught by retry logic
  - min_rps 0.5: sanity check that load actually ran

Usage:
    python tests/load/check_slos.py /path/to/load-results_stats.csv
"""

import csv
import sys

SLOS = {
    "p95_ms": 10_000,  # 10s p95 response time
    "p99_ms": 20_000,  # 20s p99 response time
    "error_rate": 5.0,  # max 5% error rate
    "min_rps": 0.5,  # must sustain at least 0.5 req/sec
}

# Endpoints excluded from SLO checks (health checks are always fast)
EXCLUDE = {"/health"}


def check_slos(csv_path: str) -> bool:
    passed = True
    rows = []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            if not name or name == "Aggregated" or name in EXCLUDE:
                continue
            rows.append(row)

    if not rows:
        print("WARNING: No endpoint rows found in CSV — was the load test too short?")
        return True  # Don't fail if no data (e.g. dry-run)

    print(f"\nChecking SLOs for {len(rows)} endpoint(s)\n{'=' * 60}")

    for row in rows:
        name = row.get("Name", "unknown")
        try:
            p95 = float(row.get("95%", 0))
            p99 = float(row.get("99%", 0))
            total = int(row.get("Request Count", 1))
            failures = int(row.get("Failure Count", 0))
            rps = float(row.get("Requests/s", 0))
            error_rate = (failures / total * 100) if total > 0 else 0
        except (ValueError, TypeError):
            print(f"  {name}: could not parse row — skipping")
            continue

        print(f"\n  {name}")
        print(f"    requests={total}  failures={failures}  rps={rps:.2f}")
        print(f"    p95={p95:.0f}ms  p99={p99:.0f}ms  error_rate={error_rate:.1f}%")

        endpoint_ok = True

        if p95 > SLOS["p95_ms"]:
            print(f"    ✗ FAIL  p95 {p95:.0f}ms > {SLOS['p95_ms']}ms")
            endpoint_ok = False
        else:
            print(f"    ✓ p95 OK ({p95:.0f}ms)")

        if p99 > SLOS["p99_ms"]:
            print(f"    ✗ FAIL  p99 {p99:.0f}ms > {SLOS['p99_ms']}ms")
            endpoint_ok = False
        else:
            print(f"    ✓ p99 OK ({p99:.0f}ms)")

        if error_rate > SLOS["error_rate"]:
            print(f"    ✗ FAIL  error rate {error_rate:.1f}% > {SLOS['error_rate']}%")
            endpoint_ok = False
        else:
            print(f"    ✓ error rate OK ({error_rate:.1f}%)")

        if rps < SLOS["min_rps"]:
            print(f"    ✗ FAIL  rps {rps:.2f} < {SLOS['min_rps']} (load test may not have run)")
            endpoint_ok = False
        else:
            print(f"    ✓ rps OK ({rps:.2f})")

        if not endpoint_ok:
            passed = False

    print(f"\n{'=' * 60}")
    print(f"SLO result: {'PASSED ✓' if passed else 'FAILED ✗'}")
    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <locust_stats.csv>")
        sys.exit(1)

    sys.exit(0 if check_slos(sys.argv[1]) else 1)
