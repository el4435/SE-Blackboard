"""Evaluation metrics: Resolve Rate, Token Cost, Latency, etc."""

from __future__ import annotations

from typing import Any


def compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate metrics over a list of experiment results.

    Args:
        results: List of ExperimentResult dicts.

    Returns:
        Dict with resolve_rate, avg_tokens, avg_latency, etc.
    """
    if not results:
        return {}

    total = len(results)
    resolved = sum(1 for r in results if r.get("resolved", False))
    total_in = sum(r.get("total_input_tokens", 0) for r in results)
    total_out = sum(r.get("total_output_tokens", 0) for r in results)
    total_lat = sum(r.get("total_latency_ms", 0) for r in results)

    return {
        "total_issues": total,
        "resolved": resolved,
        "resolve_rate": resolved / total,
        "avg_input_tokens": total_in / total,
        "avg_output_tokens": total_out / total,
        "avg_latency_ms": total_lat / total,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
    }
