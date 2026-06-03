# 4. Experimental Setup

## 4.1 Benchmark

We evaluate on **SWE-bench Lite** [Jimenez et al., 2024], a curated subset of the SWE-bench benchmark comprising 300 real-world GitHub issues from 12 popular Python repositories. Each issue includes a natural language problem description, a base commit representing the repository state before the fix, and a set of test cases that the fix must pass (`FAIL_TO_PASS` tests) while not breaking existing functionality (`PASS_TO_PASS` tests).

From the 300 SWE-bench Lite issues, we select a stratified sample of **50 issues** to balance experimental feasibility with coverage. Issues were initially sampled in equal strata (20 easy, 20 medium, 10 hard) based on repository metadata. We then reclassified all 50 issues post-hoc using gold patch complexity (number of files modified and lines changed) as an objective difficulty proxy:

- **Easy** (single-file, <20 lines): 22 issues, predominantly from Django
- **Medium** (single-file, 20-50 lines or multi-file with small changes): 5 issues
- **Hard** (multi-file, >50 lines, or requiring complex reasoning): 23 issues

The sample covers 8 repositories: Django (22 issues), SymPy (15), Sphinx (4), pytest (3), Astropy (2), xarray (1), Flask (1), and pylint (1). This distribution reflects the composition of SWE-bench Lite, where Django issues are overrepresented due to the project's comprehensive test coverage and well-documented issue tracker.

## 4.2 Configurations

We evaluate three experimental configurations, each combining the Sequential Pipeline topology with a different communication mode:

| Configuration | Topology | Communication | Label |
|--------------|----------|---------------|-------|
| A-Seq(MP)    | Sequential | Message-Passing | MP |
| B-Seq(BB)    | Sequential | Blackboard | BB |
| C-Seq(Hy)    | Sequential | Hybrid | Hybrid |

*Table 1: Experimental configurations for the three communication modes.*

All configurations use identical hyperparameters:

- **LLM**: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **Temperature**: 0 (deterministic generation)
- **Max iterations**: 3 (Coder-Reviewer cycles)
- **Code context**: Retrieved via git checkout of the base commit, with function-level extraction for files exceeding 500 lines

The use of a single LLM with temperature 0 ensures that observed differences are attributable to the communication architecture rather than to model selection or sampling variance. Each of the 50 issues is evaluated once per configuration, yielding 150 total experiment runs.

## 4.3 Evaluation Metrics

### Primary Metric: Resolve Rate

An issue is considered **resolved** if the generated patch, when applied to the base commit, causes all `FAIL_TO_PASS` tests to pass while maintaining all `PASS_TO_PASS` tests. Evaluation is performed using the official SWE-bench Docker harness, which applies patches using a three-stage strategy: `git apply`, `git apply --reject`, and `patch --fuzz=5`.

### Information Fidelity Score (IFS)

We propose the **Information Fidelity Score** to quantify how well key technical information is preserved across pipeline stages. IFS is computed as follows:

1. **Entity Extraction**: From the original issue description, we extract key technical entities using rule-based patterns: function names, class names, method names, file paths, module names, error types, and significant identifiers. These entities represent the critical technical information that agents must preserve for successful bug fixing.

2. **Preservation Measurement**: For each pipeline stage (Planner, Coder, Reviewer, Tester), we check which extracted entities appear in the agent's output text.

3. **Score Computation**: IFS at stage $s$ is the ratio of preserved entities to total entities:

$$\text{IFS}_s = \frac{|\text{entities in agent}_s\text{'s output}|}{|\text{entities in issue description}|}$$

IFS ranges from 0 (no entities preserved) to 1 (all entities preserved). By computing IFS at each stage, we can observe the information decay pattern across the pipeline.

Note that IFS is only meaningful for stages where the agent produces textual output containing technical content. In MP mode, IFS is computed only at the Coder stage, as the Planner's output is the input to the Coder (making its IFS trivially tied to its own generation) and no structured state is available. In BB and Hybrid modes, IFS is computed at all four stages because the blackboard state captures each agent's structured contributions. We note that the rule-based entity extraction may undercount semantically equivalent references (e.g., "FilePathField" vs. "the file path field class"); Section 7 discusses this limitation in detail.

### Patch Quality Metrics

In addition to the primary resolve rate metric, we analyze intermediate patch quality indicators to localize the performance bottleneck within the pipeline:

- **Patch generation rate**: The proportion of issues for which the Coder produces a non-empty unified diff output (as opposed to empty or malformed output).
- **Correct file targeting rate**: Among non-empty patches, the proportion that modify at least one file present in the gold (reference) patch. This measures whether the Coder correctly identifies the source file(s) requiring modification.
- **Conditional resolve rate**: Among patches that target the correct file(s), the proportion that pass the SWE-bench evaluation. This isolates patch logic and formatting quality from file identification ability.

These intermediate metrics enable a stage-by-stage analysis of where information quality advantages translate into task performance and where downstream bottlenecks attenuate the benefit.

### Efficiency Metrics

- **Token consumption**: Total input + output tokens across all LLM calls for an issue
- **Latency**: Wall-clock time from experiment start to completion for an issue
- **Iterations**: Number of Coder-Reviewer cycles before termination

## 4.4 Statistical Methods

Given the paired experimental design (each issue evaluated under all three configurations), we employ the following statistical tests:

- **McNemar's exact test** [McNemar, 1947]: For pairwise comparison of resolve rates (paired binary outcomes). We use the exact binomial version due to small expected cell counts.
- **Wilcoxon signed-rank test** [Wilcoxon, 1945]: For pairwise comparison of continuous paired measurements (token cost, latency, IFS).
- **Cohen's $h$**: Effect size measure for comparing two proportions, computed as $h = 2\arcsin(\sqrt{p_1}) - 2\arcsin(\sqrt{p_2})$.
- **Odds Ratio**: With 95% confidence interval computed via log-transform to quantify the relative likelihood of resolution under different configurations.

All tests use $\alpha = 0.05$ as the significance threshold. We note upfront that with $N=50$ paired observations and expected resolve rates of 12--16%, the statistical power for detecting differences in resolve rate is limited. We therefore interpret resolve rate results in conjunction with IFS and failure analysis to build a comprehensive picture.
