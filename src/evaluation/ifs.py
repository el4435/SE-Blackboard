"""Information Fidelity Score (IFS) computation.

IFS measures how well key information entities from the original issue
are preserved through each stage of the multi-agent pipeline.

    IFS_stage = |entities detected in stage output| / |total entities|

Key insight: In Message-Passing, information degrades as it passes
through agents (each only sees the previous agent's output). In
Blackboard mode, each agent can access the original data, preserving
information fidelity across all stages.
"""

from __future__ import annotations

import json
import re
from typing import Any


# ======================================================================
# Constants
# ======================================================================

STAGES = ["Planner", "Coder", "Reviewer", "Tester"]

# Common words to exclude from rule-based entity extraction
_EXCLUDE_SNAKE = {
    "last_modified", "verbose_name", "verbose_name_plural",
    "app_label", "max_length", "primary_key", "on_delete",
    "auto_now", "auto_now_add", "related_name", "help_text",
    "unique_together", "get_or_create", "set_up", "set_up_test_data",
    "tear_down", "test_case", "assert_equal", "assert_true",
    "assert_false", "assert_raises", "assert_is_none", "line_number",
    "file_name", "class_name", "last_error", "most_recent",
}


# ======================================================================
# Entity Extraction
# ======================================================================

async def extract_key_entities_llm(
    problem_statement: str,
    llm_client: Any,
) -> list[str]:
    """Use LLM to extract key technical entities from a GitHub issue.

    Args:
        problem_statement: The full issue text.
        llm_client: An LLMClient instance for API calls.

    Returns:
        List of key entity strings.
    """
    prompt = (
        "From the following GitHub issue, extract all key technical entities. Include:\n"
        "1. Class names, function names, method names involved\n"
        "2. File names or module names involved\n"
        "3. Specific error types or exception names\n"
        "4. Key parameter names, variable names\n"
        "5. Expected behavior (summarized in 3-5 keywords)\n"
        "6. Trigger conditions (summarized in 3-5 keywords)\n\n"
        "Return as a JSON array of strings. Only return specific, "
        "code-searchable entities.\n"
        "Do NOT return generic words like 'bug', 'error', 'fix', 'issue'.\n\n"
        f"Issue:\n{problem_statement}"
    )

    text, _, _ = await llm_client.call(
        system_prompt=(
            "You are a technical entity extractor. "
            "Return ONLY a JSON array of strings, nothing else."
        ),
        user_message=prompt,
    )

    # Parse JSON array from response
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_nl + 1 : last_fence].strip()

    try:
        entities = json.loads(cleaned)
        if isinstance(entities, list):
            result = [str(e).strip() for e in entities if e and str(e).strip()]
            if result:
                return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback to rule-based if LLM parsing fails
    return extract_key_entities_rule_based(problem_statement)


def extract_key_entities_rule_based(problem_statement: str) -> list[str]:
    """Extract key technical entities using regex patterns.

    Extracts: CamelCase identifiers, file paths, dotted module paths,
    snake_case identifiers, error/exception names, and method calls.

    Args:
        problem_statement: The full issue text.

    Returns:
        Sorted list of unique entity strings.
    """
    entities: set[str] = set()

    # 1. CamelCase class/type names (2+ humps, e.g., ProductMetaDataType)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]*)+)\b", problem_statement):
        word = m.group(1)
        if len(word) >= 4:
            entities.add(word)

    # 2. Error/Exception/Warning names (may be single-hump CamelCase)
    for m in re.finditer(
        r"\b(\w*(?:Error|Exception|Warning|Failure))\b", problem_statement
    ):
        word = m.group(1)
        if len(word) >= 5 and word[0].isupper():
            entities.add(word)

    # 3. File paths (containing / and a known extension)
    for m in re.finditer(
        r"(?:[\w.-]+/)+[\w.-]+\.(?:py|js|ts|java|go|rs|c|h|cpp|txt|cfg|ini|toml|yaml|yml)\b",
        problem_statement,
    ):
        entities.add(m.group(0))

    # 4. Dotted module/function paths (3+ parts)
    for m in re.finditer(
        r"\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){2,})\b", problem_statement
    ):
        entities.add(m.group(1))

    # 5. snake_case identifiers (2+ parts, meaningful)
    for m in re.finditer(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", problem_statement):
        word = m.group(1)
        if word not in _EXCLUDE_SNAKE and len(word) >= 4:
            entities.add(word)

    # 6. Specific method calls (e.g., .filter(), .annotate(), .distinct())
    for m in re.finditer(r"\.([a-z_]\w*)\s*\(", problem_statement):
        method = m.group(1)
        if len(method) >= 3 and method not in {"str", "int", "len", "get", "set", "pop"}:
            entities.add(method)

    # 7. Single capitalized words that appear in code context (backtick-quoted)
    for m in re.finditer(r"`(\w+)`", problem_statement):
        word = m.group(1)
        if len(word) >= 3:
            entities.add(word)

    return sorted(entities - {""})


# ======================================================================
# Entity Detection (Fuzzy Matching)
# ======================================================================


def detect_entities(
    entities: list[str], agent_output: str
) -> dict[str, bool]:
    """Detect whether each entity appears in agent output text.

    Uses multi-strategy fuzzy matching:
    1. Exact substring match (case-insensitive)
    2. Normalized match (CamelCase <-> snake_case)
    3. Token overlap for multi-word entities (>=60% threshold)

    High-recall strategy: when uncertain, prefer marking as present.

    Args:
        entities: List of entity strings to search for.
        agent_output: The agent's output text.

    Returns:
        Dict mapping each entity to True/False.
    """
    if not agent_output or not entities:
        return {e: False for e in entities}

    output_lower = agent_output.lower()
    output_normalized = _normalize_text(agent_output)

    result: dict[str, bool] = {}
    for entity in entities:
        entity_lower = entity.lower()

        # Strategy 1: Exact substring (case-insensitive)
        if entity_lower in output_lower:
            result[entity] = True
            continue

        # Strategy 2: Normalized match (CamelCase <-> snake_case, dots -> spaces)
        entity_normalized = _normalize_text(entity)
        if len(entity_normalized) >= 3 and entity_normalized in output_normalized:
            result[entity] = True
            continue

        # Strategy 3: Token overlap for multi-word entities
        entity_tokens = _tokenize(entity)
        if len(entity_tokens) >= 2:
            meaningful = [t for t in entity_tokens if len(t) >= 3]
            if meaningful:
                found = sum(1 for t in meaningful if t in output_lower)
                if found >= max(1, len(meaningful) * 0.6):
                    result[entity] = True
                    continue

        result[entity] = False

    return result


# ======================================================================
# IFS Computation
# ======================================================================


def compute_ifs(entities: list[str], entity_presence: dict[str, bool]) -> float:
    """Compute Information Fidelity Score.

    IFS = |detected entities| / |total entities|

    Args:
        entities: List of key entities.
        entity_presence: Detection results from detect_entities().

    Returns:
        Score between 0.0 and 1.0. Returns 1.0 if no entities.
    """
    if not entities:
        return 1.0
    return sum(1 for e in entities if entity_presence.get(e, False)) / len(entities)


def compute_ifs_for_text(entities: list[str], output_text: str) -> float:
    """Convenience: detect entities and compute IFS in one call."""
    presence = detect_entities(entities, output_text)
    return compute_ifs(entities, presence)


# ======================================================================
# Agent Output Extraction from Results
# ======================================================================


def extract_agent_outputs(result: dict[str, Any]) -> dict[str, str]:
    """Extract per-stage agent output text from experiment result data.

    For Blackboard/Hybrid configs: extracts structured data from
    blackboard_final_state and converts to searchable text.
    For Message-Passing configs: only final_patch is available.

    Args:
        result: The full experiment result dict.

    Returns:
        Dict mapping stage names to output text.
        Empty string means data is unavailable for that stage.
    """
    bb_state = result.get("blackboard_final_state")

    if bb_state:
        return _extract_from_blackboard(bb_state)
    else:
        return _extract_from_mp(result)


def _extract_from_blackboard(bb_state: dict[str, Any]) -> dict[str, str]:
    """Extract per-stage outputs from blackboard_final_state."""
    outputs: dict[str, str] = {}

    # Planner -> analysis
    analysis = bb_state.get("analysis", {})
    planner_parts = [
        analysis.get("root_cause", ""),
        " ".join(str(f) for f in analysis.get("relevant_files", [])),
        " ".join(str(f) for f in analysis.get("relevant_functions", [])),
        analysis.get("fix_strategy", ""),
        analysis.get("relevant_code", ""),
    ]
    outputs["Planner"] = " ".join(p for p in planner_parts if p)

    # Coder -> patches (combine all patches from all authors)
    coder_parts: list[str] = []
    for patch in bb_state.get("patches", []):
        diff = patch.get("diff", "")
        desc = patch.get("description", "")
        if diff:
            coder_parts.append(diff)
        if desc:
            coder_parts.append(desc)
    outputs["Coder"] = " ".join(coder_parts)

    # Reviewer -> reviews
    reviewer_parts: list[str] = []
    for review in bb_state.get("reviews", []):
        verdict = review.get("verdict", "")
        if verdict:
            reviewer_parts.append(verdict)
        for issue in review.get("issues", []):
            reviewer_parts.append(str(issue))
        for suggestion in review.get("suggestions", []):
            reviewer_parts.append(str(suggestion))
    outputs["Reviewer"] = " ".join(reviewer_parts)

    # Tester -> test_results
    tester_parts: list[str] = []
    for tr in bb_state.get("test_results", []):
        tester_parts.append(str(tr.get("passed", "")))
        for t in tr.get("failing_tests", []):
            tester_parts.append(str(t))
        for t in tr.get("error_traces", []):
            tester_parts.append(str(t))
    outputs["Tester"] = " ".join(tester_parts)

    return outputs


def _extract_from_mp(result: dict[str, Any]) -> dict[str, str]:
    """Extract what's available from Message-Passing result.

    Only final_patch is stored; intermediate agent outputs
    were passed as messages and not persisted.
    """
    return {
        "Planner": "",   # Not stored in MP mode
        "Coder": result.get("final_patch", ""),
        "Reviewer": "",  # Not stored in MP mode
        "Tester": "",    # Not stored in MP mode
    }


# ======================================================================
# Statistical Helpers
# ======================================================================


def point_biserial_correlation(
    x: list[float], y: list[int]
) -> tuple[float, str]:
    """Compute point-biserial correlation between continuous x and binary y.

    Args:
        x: Continuous variable (IFS scores).
        y: Binary variable (0 = unresolved, 1 = resolved).

    Returns:
        (correlation_coefficient, significance_label)
        significance_label is one of: "p<0.01", "p<0.05", "p<0.10", "n.s."
    """
    n = len(x)
    if n < 3 or len(y) != n:
        return 0.0, "n.s."

    x_1 = [x[i] for i in range(n) if y[i] == 1]
    x_0 = [x[i] for i in range(n) if y[i] == 0]

    if not x_1 or not x_0:
        return 0.0, "n.s."

    n1 = len(x_1)
    n0 = len(x_0)
    m1 = sum(x_1) / n1
    m0 = sum(x_0) / n0

    # Overall standard deviation
    mean_x = sum(x) / n
    var_x = sum((xi - mean_x) ** 2 for xi in x) / n
    if var_x == 0:
        return 0.0, "n.s."
    std_x = var_x ** 0.5

    # Point-biserial r
    p = n1 / n
    q = n0 / n
    r = (m1 - m0) / std_x * (p * q) ** 0.5

    # Approximate t-statistic for significance
    if abs(r) >= 0.9999:
        return r, "p<0.01"
    t_stat = r * ((n - 2) / (1 - r ** 2)) ** 0.5
    abs_t = abs(t_stat)

    # Critical t-values (two-tailed, df=n-2, approximate for large n)
    # For df>=30: t_0.01 ~ 2.75, t_0.05 ~ 2.04, t_0.10 ~ 1.70
    if abs_t > 2.75:
        sig = "p<0.01"
    elif abs_t > 2.04:
        sig = "p<0.05"
    elif abs_t > 1.70:
        sig = "p<0.10"
    else:
        sig = "n.s."

    return round(r, 4), sig


# ======================================================================
# Text Normalization Helpers
# ======================================================================


def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching.

    Converts CamelCase to space-separated, replaces underscores/dots/slashes
    with spaces, lowercases everything.
    """
    # Split CamelCase: "ProductMetaDataType" -> "Product Meta Data Type"
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    # Replace separators with spaces
    text = re.sub(r"[_./\\:]+", " ", text)
    # Lowercase and collapse whitespace
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens."""
    normalized = _normalize_text(text)
    return [t for t in normalized.split() if len(t) >= 2]
