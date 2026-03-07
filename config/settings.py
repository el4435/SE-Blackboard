"""Global configuration for the SE-Blackboard project."""

MODEL: str = "claude-sonnet-4-5-20250929"
TEMPERATURE: float = 0
MAX_ITERATIONS: int = 3  # Maximum fix-review-test loop iterations
MAX_TOKENS_PER_CALL: int = 4096
NUM_ISSUES: int = 50  # Number of issues to evaluate

# Logging
LOG_DIR: str = "data/results"
LOG_FORMAT: str = "json"

# Patch generation
CODER_PATCH_MODE: str = "diff"  # "diff" (default) or "whole_file"
WHOLE_FILE_MAX_TOKENS: int = 16384  # Higher token limit for whole-file rewrite mode

# Patch application
FALLBACK_APPLY: bool = True  # Enable fallback patch apply (git apply -> patch -F0 -> patch -F3)

# SWE-bench
SWEBENCH_DATASET: str = "princeton-nlp/SWE-bench_Lite"
SWEBENCH_SPLIT: str = "test"
