"""Evaluation module: metrics, IFS scoring, and SWE-bench runner."""

from .metrics import compute_metrics
from .ifs import (
    STAGES,
    compute_ifs,
    compute_ifs_for_text,
    detect_entities,
    extract_agent_outputs,
    extract_key_entities_llm,
    extract_key_entities_rule_based,
    point_biserial_correlation,
)

__all__ = [
    "STAGES",
    "compute_ifs",
    "compute_ifs_for_text",
    "compute_metrics",
    "detect_entities",
    "extract_agent_outputs",
    "extract_key_entities_llm",
    "extract_key_entities_rule_based",
    "point_biserial_correlation",
]
