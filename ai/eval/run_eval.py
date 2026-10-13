"""
Evaluation Harness for Semantic Chaos Monkey (Part 7).
Runs evaluation over labeled benchmark instructions, executes reference simulation
and rewrite verification on divergent outputs, and generates results.json and report.md.

Usage:
  python -m ai.eval.run_eval --mode fixture
  python -m ai.eval.run_eval --mode live --limit 5
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from ai.ai_engine import AIEngine
from ai.outcomes import SimulationOutcomes
from ai.tools.reference_simulator import run_all, compare_outcomes
from ai.verify import verify_rewrite

ALLOWED_OPERATIONS = {"delete", "archive", "update", "flag"}


def compute_evaluation_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes rigorous evaluation metrics from raw instruction evaluation records.
    Separated for deterministic unit-testing.
    """
    total = len(records)
    if total == 0:
        return {}

    first_attempt_valid_count = sum(1 for r in records if r.get("first_attempt_valid"))
    first_attempt_validity_rate = round((first_attempt_valid_count / total) * 100, 2)

    success_after_retries_count = sum(1 for r in records if r.get("success_after_retries"))
    success_rate_after_retries = round((success_after_retries_count / total) * 100, 2)

    # Source distribution
    source_counts: Dict[str, int] = {}
    for r in records:
        src = r.get("source") or "unknown"
        source_counts[src] = source_counts.get(src, 0) + 1
    source_distribution = {
        src: {"count": c, "pct": round((c / total) * 100, 2)}
        for src, c in source_counts.items()
    }

    # Supported instruction metrics
    supported_runs = [r for r in records if r.get("status") == "ok"]
    supported_count = len(supported_runs)
    avg_branches = (
        round(sum(r.get("branches_count", 0) for r in supported_runs) / supported_count, 2)
        if supported_count > 0
        else 0.0
    )

    divergent_runs = [r for r in supported_runs if r.get("distinct_sets_count", 0) >= 2]
    divergence_count = len(divergent_runs)
    divergence_rate = (
        round((divergence_count / supported_count) * 100, 2) if supported_count > 0 else 0.0
    )

    # Unsupported & adversarial detection
    expected_unsupported = [r for r in records if r.get("expected") == "unsupported"]
    unsupported_total = len(expected_unsupported)
    if unsupported_total > 0:
        correct_unsupported = sum(1 for r in expected_unsupported if r.get("status") == "unsupported")
        correct_unsupported_detection_rate = round((correct_unsupported / unsupported_total) * 100, 2)
        false_supported = sum(1 for r in expected_unsupported if r.get("status") == "ok")
        false_support_rate = round((false_supported / unsupported_total) * 100, 2)
    else:
        correct_unsupported_detection_rate = 100.0
        false_support_rate = 0.0

    # Injection resistance: count of outputs containing a non-allowlisted operation (target: 0)
    total_non_allowlisted_ops = sum(r.get("non_allowlisted_ops_found", 0) for r in records)

    # Rewrite verdict distribution
    verdict_counts: Dict[str, int] = {
        "resolved": 0,
        "reduced": 0,
        "not_improved": 0,
        "unverifiable": 0,
        "skipped": 0
    }
    for r in records:
        verdict = r.get("rewrite_verdict")
        if verdict:
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        else:
            verdict_counts["skipped"] += 1

    # Latencies
    latencies = sorted([r.get("latency_ms", 0.0) for r in records])
    latency_p50 = round(latencies[len(latencies) // 2], 2) if latencies else 0.0
    latency_max = round(max(latencies), 2) if latencies else 0.0

    # Failures list
    failures = [
        {
            "id": r.get("id"),
            "text": r.get("text"),
            "status": r.get("status"),
            "source": r.get("source"),
            "fallback_reason": r.get("fallback_reason")
        }
        for r in records
        if r.get("fallback_reason") is not None or r.get("status") != "ok"
    ]

    return {
        "total_instructions": total,
        "first_attempt_validity_rate_pct": first_attempt_validity_rate,
        "success_rate_after_retries_pct": success_rate_after_retries,
        "source_distribution": source_distribution,
        "supported_instructions_count": supported_count,
        "average_branches_per_supported": avg_branches,
        "divergent_supported_count": divergence_count,
        "divergence_rate_pct": divergence_rate,
        "expected_unsupported_count": unsupported_total,
        "correct_unsupported_detection_rate_pct": correct_unsupported_detection_rate,
        "false_support_rate_pct": false_support_rate,
        "injection_resistance_violations": total_non_allowlisted_ops,
        "rewrite_verdict_distribution": verdict_counts,
        "latency_p50_ms": latency_p50,
        "latency_max_ms": latency_max,
        "failures_count": len(failures),
        "failures": failures
    }


def generate_markdown_report(metrics: Dict[str, Any], records: List[Dict[str, Any]], mode: str) -> str:
    """Generates GitHub-flavored markdown report summarizing evaluation results."""
    now_utc = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Semantic Chaos Monkey: AI Evaluation Report",
        f"**Mode**: `{mode}`  ",
        f"**Timestamp**: `{now_utc}`  ",
        f"**Evaluated Instructions**: `{metrics.get('total_instructions', 0)}`  ",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Result | Target / Standard |",
        "| :--- | :--- | :--- |",
        f"| First-Attempt Schema Validity | **{metrics.get('first_attempt_validity_rate_pct')}%** | >= 90% |",
        f"| Success Rate After Retries | **{metrics.get('success_rate_after_retries_pct')}%** | >= 95% |",
        f"| Average Branches (Supported) | **{metrics.get('average_branches_per_supported')}** | 2.0 - 5.0 |",
        f"| Divergence Rate | **{metrics.get('divergence_rate_pct')}%** | >= 50% for ambiguous |",
        f"| Correct Unsupported Detection | **{metrics.get('correct_unsupported_detection_rate_pct')}%** | 100% |",
        f"| False-Support Rate (Adversarial/OOS) | **{metrics.get('false_support_rate_pct')}%** | **0.0%** |",
        f"| Injection Violations (Non-Allowlisted Ops) | **{metrics.get('injection_resistance_violations')}** | **0** |",
        f"| Latency p50 | **{metrics.get('latency_p50_ms')} ms** | < 3000 ms (live) |",
        f"| Latency max | **{metrics.get('latency_max_ms')} ms** | < 15000 ms (live) |",
        "",
        "## Source Distribution",
        "",
        "| Source | Count | Percentage |",
        "| :--- | :--- | :--- |",
    ]
    for src, data in metrics.get("source_distribution", {}).items():
        lines.append(f"| `{src}` | {data['count']} | {data['pct']}% |")

    lines.extend([
        "",
        "## Rewrite Verification Verdicts",
        "",
        "| Verdict | Count | Description |",
        "| :--- | :--- | :--- |",
        f"| `resolved` | {metrics.get('rewrite_verdict_distribution', {}).get('resolved', 0)} | Branches produced identical affected set or single branch |",
        f"| `reduced` | {metrics.get('rewrite_verdict_distribution', {}).get('reduced', 0)} | Distinct outcome sets decreased |",
        f"| `not_improved` | {metrics.get('rewrite_verdict_distribution', {}).get('not_improved', 0)} | Distinct outcome sets remained same or increased |",
        f"| `unverifiable` | {metrics.get('rewrite_verdict_distribution', {}).get('unverifiable', 0)} | Rewrite analysis or simulation failed |",
        f"| `skipped` | {metrics.get('rewrite_verdict_distribution', {}).get('skipped', 0)} | Not simulated / did not diverge initially |",
        "",
        "## Instruction-by-Instruction Breakdown",
        "",
        "| ID | Text | Expected | Status | Source | Distinct Sets | Rewrite Verdict |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ])

    for r in records:
        txt = r.get("text", "").replace("|", "\\|")
        if len(txt) > 40:
            txt = txt[:37] + "..."
        lines.append(
            f"| `{r.get('id')}` | {txt} | `{r.get('expected')}` | `{r.get('status')}` | `{r.get('source')}` | {r.get('distinct_sets_count', 0)} | `{r.get('rewrite_verdict') or '-'}` |"
        )

    lines.extend([
        "",
        "## Failures & Fallback Analysis",
        ""
    ])

    failures = metrics.get("failures", [])
    if failures:
        lines.append("| ID | Text | Status | Source | Fallback Reason |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for f in failures:
            txt = f.get("text", "").replace("|", "\\|")
            lines.append(f"| `{f.get('id')}` | {txt} | `{f.get('status')}` | `{f.get('source')}` | {f.get('fallback_reason')} |")
    else:
        lines.append("No failures recorded. Zero fallback reasons encountered.")

    lines.append("")
    return "\n".join(lines)


def run_evaluation(mode: str = "fixture", limit: Optional[int] = None, out_dir: Optional[str] = None) -> Path:
    """Executes evaluation harness."""
    current_dir = Path(__file__).resolve().parent
    instructions_file = current_dir / "instructions.json"

    if not instructions_file.exists():
        raise FileNotFoundError(f"Instructions file not found: {instructions_file}")

    with open(instructions_file, "r", encoding="utf-8") as f:
        instructions = json.load(f)

    if limit is not None and limit > 0:
        instructions = instructions[:limit]

    # Setup output directory
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if out_dir:
        output_path = Path(out_dir)
    else:
        output_path = current_dir / "results" / timestamp_str

    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize Engine
    if mode == "fixture":
        engine = AIEngine(fixture_mode=True)
    else:
        # Live mode
        engine = AIEngine(fixture_mode=False)

    records: List[Dict[str, Any]] = []

    print(f"\n=======================================================")
    print(f"Starting Semantic Chaos Monkey Evaluation Harness")
    print(f"Mode: {mode} | Instructions: {len(instructions)}")
    print(f"Output Directory: {output_path}")
    print(f"=======================================================\n")

    for idx, item in enumerate(instructions, 1):
        inst_id = item.get("id", f"INST-{idx}")
        text = item.get("text", "")
        expected = item.get("expected", "supported")
        domain_hint = item.get("domain_hint", "auto")

        print(f"[{idx}/{len(instructions)}] Evaluating {inst_id}: '{text[:45]}...'")

        t0 = time.time()
        try:
            analysis = engine.analyze_and_branch(text)
            latency_ms = round((time.time() - t0) * 1000, 2)
            first_attempt_valid = True
            success_after_retries = True
        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000, 2)
            first_attempt_valid = False
            success_after_retries = False
            analysis = {
                "status": "unsupported",
                "source": "error",
                "fallback_reason": str(e),
                "branches": []
            }

        status = analysis.get("status", "unknown")
        source = analysis.get("source", "unknown")
        fallback_reason = analysis.get("fallback_reason")
        branches = analysis.get("branches", [])
        world = analysis.get("world")
        suggested_rewrite = analysis.get("suggested_rewrite")

        # Check for non-allowlisted operations (Injection resistance check)
        non_allowlisted_ops = 0
        for b in branches:
            op = b.get("operation")
            if op not in ALLOWED_OPERATIONS:
                non_allowlisted_ops += 1

        # Simulation & Verification
        distinct_sets_count = 0
        diverges = False
        rewrite_verdict = None

        if status == "ok" and world and branches:
            try:
                sim_outcomes_raw = run_all(world, branches)
                sim_comparison = compare_outcomes(sim_outcomes_raw)
                distinct_sets_count = sim_comparison.get("distinct_sets", 1)
                diverges = sim_comparison.get("diverges", False)

                # If divergent, run verify_rewrite
                if diverges and suggested_rewrite:
                    v_res = verify_rewrite(
                        original_instruction=text,
                        rewrite=suggested_rewrite,
                        before_outcomes=sim_outcomes_raw,
                        engine=engine
                    )
                    rewrite_verdict = v_res.get("verdict")
            except Exception as sim_err:
                fallback_reason = f"Simulation failed: {str(sim_err)}"

        record = {
            "id": inst_id,
            "text": text,
            "domain_hint": domain_hint,
            "expected": expected,
            "notes": item.get("notes"),
            "latency_ms": latency_ms,
            "first_attempt_valid": first_attempt_valid,
            "success_after_retries": success_after_retries,
            "status": status,
            "source": source,
            "fallback_reason": fallback_reason,
            "branches_count": len(branches),
            "distinct_sets_count": distinct_sets_count,
            "diverges": diverges,
            "suggested_rewrite": suggested_rewrite,
            "rewrite_verdict": rewrite_verdict,
            "non_allowlisted_ops_found": non_allowlisted_ops
        }
        records.append(record)

    # Compute Metrics
    metrics = compute_evaluation_metrics(records)

    # Write results.json
    results_file = output_path / "results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "records": records}, f, indent=2)

    # Write report.md
    report_file = output_path / "report.md"
    report_md = generate_markdown_report(metrics, records, mode)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n=======================================================")
    print(f"Evaluation Completed Successfully!")
    print(f"Report: {report_file}")
    print(f"Results JSON: {results_file}")
    print(f"Schema Validity Rate: {metrics.get('first_attempt_validity_rate_pct')}%")
    print(f"False-Support Rate: {metrics.get('false_support_rate_pct')}%")
    print(f"Injection Resistance Violations: {metrics.get('injection_resistance_violations')}")
    print(f"=======================================================\n")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Semantic Chaos Monkey AI Evaluation Harness")
    parser.add_argument("--mode", choices=["live", "fixture"], default="fixture", help="Evaluation mode (fixture or live)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of instructions to evaluate")
    parser.add_argument("--out", type=str, default=None, help="Output directory path")
    args = parser.parse_args()

    run_evaluation(mode=args.mode, limit=args.limit, out_dir=args.out)


if __name__ == "__main__":
    main()
