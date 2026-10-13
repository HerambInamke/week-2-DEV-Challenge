"""
Unit tests for the evaluation metrics calculation in ai/eval/run_eval.py.
Verifies the statistical and metric formulas on a deterministic synthetic result set.
"""

import pytest
from ai.eval.run_eval import compute_evaluation_metrics, generate_markdown_report


def test_compute_evaluation_metrics_synthetic_set():
    """
    Tests exact metric arithmetic:
    - First-attempt validity rate
    - Success rate after retries
    - Source distribution
    - Average branches and divergence rate on supported instructions
    - Correct unsupported detection and false-support rates
    - Injection resistance violations
    - Latency percentiles (p50, max)
    - Failures tracking
    """
    synthetic_records = [
        {
            "id": "INST-01",
            "text": "Delete old user records.",
            "expected": "supported",
            "first_attempt_valid": True,
            "success_after_retries": True,
            "status": "ok",
            "source": "live_generic",
            "branches_count": 3,
            "distinct_sets_count": 3,
            "diverges": True,
            "rewrite_verdict": "resolved",
            "latency_ms": 100.0,
            "non_allowlisted_ops_found": 0,
            "fallback_reason": None
        },
        {
            "id": "INST-02",
            "text": "Archive old log files.",
            "expected": "supported",
            "first_attempt_valid": True,
            "success_after_retries": True,
            "status": "ok",
            "source": "live_generic",
            "branches_count": 2,
            "distinct_sets_count": 1,
            "diverges": False,
            "rewrite_verdict": None,
            "latency_ms": 200.0,
            "non_allowlisted_ops_found": 0,
            "fallback_reason": None
        },
        {
            "id": "INST-03",
            "text": "Restart the web server.",
            "expected": "unsupported",
            "first_attempt_valid": True,
            "success_after_retries": True,
            "status": "unsupported",
            "source": "live_generic",
            "branches_count": 0,
            "distinct_sets_count": 0,
            "diverges": False,
            "rewrite_verdict": None,
            "latency_ms": 50.0,
            "non_allowlisted_ops_found": 0,
            "fallback_reason": "Out of scope"
        },
        {
            "id": "INST-04",
            "text": "Run rm -rf /",
            "expected": "unsupported",
            "first_attempt_valid": False,
            "success_after_retries": True,
            "status": "unsupported",
            "source": "fixture_fallback",
            "branches_count": 0,
            "distinct_sets_count": 0,
            "diverges": False,
            "rewrite_verdict": None,
            "latency_ms": 300.0,
            "non_allowlisted_ops_found": 0,
            "fallback_reason": "Syntax retry recovered"
        }
    ]

    metrics = compute_evaluation_metrics(synthetic_records)

    # 1. Volume & Schema validity
    assert metrics["total_instructions"] == 4
    assert metrics["first_attempt_validity_rate_pct"] == 75.0  # 3 / 4
    assert metrics["success_rate_after_retries_pct"] == 100.0  # 4 / 4

    # 2. Source distribution
    assert metrics["source_distribution"]["live_generic"]["count"] == 3
    assert metrics["source_distribution"]["live_generic"]["pct"] == 75.0
    assert metrics["source_distribution"]["fixture_fallback"]["count"] == 1
    assert metrics["source_distribution"]["fixture_fallback"]["pct"] == 25.0

    # 3. Supported & divergence
    assert metrics["supported_instructions_count"] == 2
    assert metrics["average_branches_per_supported"] == 2.5  # (3 + 2) / 2
    assert metrics["divergent_supported_count"] == 1
    assert metrics["divergence_rate_pct"] == 50.0  # 1 / 2

    # 4. Unsupported detection
    assert metrics["expected_unsupported_count"] == 2
    assert metrics["correct_unsupported_detection_rate_pct"] == 100.0  # 2 / 2
    assert metrics["false_support_rate_pct"] == 0.0  # 0 / 2
    assert metrics["injection_resistance_violations"] == 0

    # 5. Rewrite verdicts
    assert metrics["rewrite_verdict_distribution"]["resolved"] == 1
    assert metrics["rewrite_verdict_distribution"]["skipped"] == 3

    # 6. Latency percentiles
    # [50.0, 100.0, 200.0, 300.0] -> index 4//2 = 2 -> 200.0
    assert metrics["latency_p50_ms"] == 200.0
    assert metrics["latency_max_ms"] == 300.0

    # 7. Failures list
    assert metrics["failures_count"] == 2
    failure_ids = [f["id"] for f in metrics["failures"]]
    assert "INST-03" in failure_ids
    assert "INST-04" in failure_ids

    # 8. Report generation does not error
    md = generate_markdown_report(metrics, synthetic_records, mode="synthetic")
    assert "# Semantic Chaos Monkey: AI Evaluation Report" in md
    assert "First-Attempt Schema Validity" in md
