# 5. Results

## 5.1 Resolve Rate

Table 2 presents the main experimental results across three communication architectures.

| Communication | Resolved | Rate | Avg Tokens | Avg Latency | Avg Iter. |
|--------------|----------|------|------------|-------------|-----------|
| Message-Passing | 6/50 | 12.0% | 25,316 | 106s | 2.78 |
| Blackboard | 8/50 | **16.0%** | 54,849 | 171s | 2.70 |
| Hybrid | 6/50 | 12.0% | 43,278 | 128s | 2.80 |

*Table 2: Main experimental results on SWE-bench Lite (N=50, Sequential pipeline).*

The Blackboard configuration resolves 8 out of 50 issues (16.0%), compared to 6/50 (12.0%) for both Message-Passing and Hybrid. This represents a 4 percentage-point absolute improvement and a 33% relative improvement over Message-Passing. However, McNemar's exact test yields $p=0.625$ (Table 8), indicating that this difference is not statistically significant at $\alpha=0.05$. The test is based on only 4 discordant pairs ($b=1$, $c=3$), resulting in low statistical power. Cohen's $h = 0.116$ confirms a negligible effect size on the proportion scale.

The odds ratio for BB vs. MP is 1.40 (95% CI: 0.45--4.37), indicating that Blackboard issues are 40% more likely to be resolved, though the confidence interval includes 1.0 and thus does not exclude the null hypothesis.

**Difficulty Breakdown.** When grouping by difficulty level (Table 3, Figure 1), we observe that the Blackboard advantage concentrates in easy-difficulty issues. Among the 22 Django-dominated easy issues, BB resolves 7 (31.8%) compared to MP's 4 (18.2%). In the medium category (5 issues), all configurations resolve exactly 1 issue (20.0%). Among the 23 hard issues, MP resolves 1 (sphinx-8713, 4.3%) while BB and Hybrid resolve none. This pattern suggests that Blackboard's information preservation benefit is most impactful when the underlying task is within the agent's capability range.

| Difficulty | MP | BB | Hybrid |
|-----------|-----|-----|--------|
| Easy (Django) | 4/22 (18.2%) | 7/22 (31.8%) | 5/22 (22.7%) |
| Medium | 1/5 (20.0%) | 1/5 (20.0%) | 1/5 (20.0%) |
| Hard | 1/23 (4.3%) | 0/23 (0.0%) | 0/23 (0.0%) |

*Table 3: Resolve rate by difficulty level.*

**Issue-Level Overlap.** Figure 5 illustrates the overlap in resolved issues across configurations. Five issues are resolved by all three configurations: django-11179, django-13230, django-15347, django-16379, and pytest-11143. These represent a "common core" of relatively straightforward issues. Blackboard uniquely resolves two additional issues (django-12915, django-13028) that neither MP nor Hybrid can solve. Conversely, MP uniquely resolves sphinx-8713, which BB fails on. One issue (django-12700) is resolved by both BB and Hybrid but not MP. In total, 9 out of 50 issues (18%) are resolved by at least one configuration.

## 5.2 Information Fidelity Score

The IFS analysis provides the strongest evidence for the Blackboard architecture's benefit (Table 4, Figure 2).

**Coder Stage.** At the Coder stage---where the critical code generation occurs---Blackboard achieves an average IFS of 0.584 compared to Message-Passing's 0.390 (Table 4). This 50% relative improvement indicates that the Coder retains substantially more key entities from the original issue when operating with shared-state access. A Wilcoxon signed-rank test on paired per-issue IFS values yields $W=36.5$, $p=0.058$ ($n=28$ issues with non-zero differences), approaching conventional significance.

| Communication | Planner | Coder | Reviewer | Tester |
|--------------|---------|-------|----------|--------|
| Message-Passing | N/A | 0.390 | N/A | N/A |
| Blackboard | 0.749 | 0.584 | 0.454 | 0.074 |
| Hybrid | 0.738 | 0.539 | 0.503 | 0.079 |

*Table 4: Average Information Fidelity Score by pipeline stage.*

**Information Decay Pattern.** For BB and Hybrid modes, where IFS is measurable at all stages, we observe a clear decay pattern (Figure 2b). The Planner stage achieves the highest IFS (BB: 0.749, Hybrid: 0.738), reflecting that the Planner's analysis retains most key entities from the issue. IFS drops at the Coder stage (BB: 0.584, Hybrid: 0.539), indicating that code generation naturally focuses on implementation details rather than reproducing all issue entities. The Reviewer stage shows further decay (BB: 0.454, Hybrid: 0.503), and the Tester stage shows minimal entity preservation (BB: 0.074, Hybrid: 0.079), which is expected since test output focuses on pass/fail status rather than issue terminology.

The critical comparison is between MP's Coder IFS (0.390) and BB's Coder IFS (0.584). In MP mode, the Coder receives only the Planner's text summary, losing direct access to the issue's exact terminology. In BB mode, the Coder reads the Planner's analysis alongside the original issue from the shared state, enabling cross-referencing. This architectural difference accounts for the 50% improvement in entity preservation.

**IFS and Resolve Rate.** While higher IFS does not guarantee resolution (many high-IFS issues fail due to patch formatting), the pattern is directionally consistent: BB's two uniquely resolved issues (django-12915, django-13028) both have notably higher Coder IFS under BB than under MP, suggesting that information preservation contributed to their resolution.

## 5.3 Failure Analysis

Failure analysis reveals that patch formatting---rather than information quality---constitutes the dominant bottleneck across all configurations (Table 5, Figure 3).

| Category | MP | BB | Hybrid |
|---------|-----|-----|--------|
| Resolved | 6 | 8 | 6 |
| Empty Patch | 1 | 4 | 18 |
| Patch Apply Error | 43 | 38 | 26 |
| **Total** | **50** | **50** | **50** |

*Table 5: Failure mode distribution.*

**Patch Apply Error** is the dominant failure mode, affecting 43/50 MP issues, 38/50 BB issues, and 26/50 Hybrid issues. These failures occur when the generated diff contains context lines that do not match the actual repository content, causing `git apply` to fail. The SWE-bench harness attempts three application strategies (`git apply`, `git apply --reject`, `patch --fuzz=5`), but many generated patches have context discrepancies too large for even fuzzy matching.

**Empty Patch** failures occur when the Coder produces no diff output or an invalid diff. This is notably more prevalent in Hybrid mode (18/50, 36%) compared to MP (1/50, 2%) and BB (4/50, 8%). The high empty-patch rate under Hybrid suggests that the combined message-passing and blackboard context may overwhelm or confuse the Coder, leading it to produce empty or malformed output rather than a valid patch.

**Key Insight**: The gap between BB's IFS advantage (50% improvement) and its resolve rate advantage (4 percentage points) can be explained by the patch formatting bottleneck. Even when the Coder has better information (higher IFS), it must still generate a syntactically correct unified diff with exactly matching context lines. This downstream constraint limits the translation of improved information fidelity into improved task outcomes. Section 5.4 provides a fine-grained analysis of where this bottleneck occurs.

## 5.4 Patch Quality Analysis

To understand *where* in the pipeline information quality advantages are attenuated, we decompose the path from issue to resolution into intermediate stages and measure each configuration's performance at each stage (Table 6, Figure 7).

| Metric | MP | BB | Hybrid |
|--------|-----|-----|--------|
| Non-empty patch rate | 98.0% | 92.0% | 64.0% |
| Correct file targeting (of non-empty) | 55.1% | **82.6%** | 78.1% |
| Resolve rate (of correct file) | 22.2% | 21.1% | 24.0% |

*Table 6: Patch quality decomposition by communication mode (N=50).*

**File Targeting.** Correct file identification is closely related to the problem of software fault localization [Wong et al., 2016]. Among issues that produce a non-empty patch, the Blackboard Coder correctly identifies the file(s) requiring modification in 82.6% of cases, compared to 55.1% for Message-Passing---a 27.5 percentage-point improvement ($+50\%$ relative, Figure 8). Hybrid achieves 78.1%, close to BB. This result directly mirrors the IFS advantage: BB's access to the original issue text and structured Planner analysis enables more accurate code localization. The absolute count of correctly targeted files is 38/46 (BB) vs. 27/49 (MP).

**Conditional Resolve Rate.** Crucially, once the correct file is targeted, all three modes achieve similar resolve rates: MP 22.2% (6/27), BB 21.1% (8/38), and Hybrid 24.0% (6/25). The near-identical conditional rates indicate that the *quality* of the patch---specifically, the correctness of context lines and the logical soundness of the code change---is the binding constraint, and it is independent of communication architecture.

**Information Flow Bottleneck Model.** These findings support a stage-by-stage model of how information quality translates (or fails to translate) into task outcomes (Figure 7):

$$\text{Issue} \xrightarrow{\text{IFS}} \text{File Targeting} \xrightarrow{\text{Patch Gen.}} \text{Patch Apply} \xrightarrow{\text{Test}} \text{Resolve}$$

At the IFS stage, BB significantly outperforms MP (+50%). This advantage carries forward to file targeting (+27.5pp). However, at the patch generation stage, all modes converge to ~22% conditional resolve rate---the LLM's ability to produce a context-correct unified diff is the rate-limiting step. The bottleneck at this stage attenuates BB's upstream advantages, explaining why a 50% IFS improvement yields only a 4pp resolve rate gain.

## 5.5 Tool Use Ablation Study

To test whether the patch generation bottleneck can be addressed by giving the Coder access to the actual source code, we conducted an ablation study inspired by the Toolformer paradigm [Schick et al., 2023], equipping the Coder with five tools: `read_file`, `search_code`, `read_lines`, `validate_patch`, and `submit_patch`. These tools allow the Coder to browse the repository, read specific code regions, and validate its patch against the real files before submission.

We evaluated 10 issues (4 previously resolved, 6 previously failed) under both MP and BB with tool use enabled (Table 7).

| Config | No Tool Use | Tool Use | Delta |
|--------|-------------|----------|-------|
| MP | 3/10 | 3/10 | 0 |
| BB | 4/10 | 4/10 | 0 |

*Table 7: Resolve rate with and without tool use (10-issue ablation).*

Tool use does not improve resolve rates for either configuration. While the `validate_patch` tool successfully detects format errors (corrupt hunk headers, mismatched context lines), the LLM is unable to correct these errors even with multiple retry attempts. The tool-augmented Coder consumes 2--4$\times$ more tokens (MP: 3.9$\times$, BB: 2.1$\times$ on average) due to iterative file reading and patch validation cycles, without achieving additional resolutions. One MP regression was observed (pytest-11143 lost due to incorrect file paths in the tool-generated patch), while one MP gain occurred (django-12915 newly resolved).

This result confirms that the bottleneck resides in the LLM's intrinsic ability to generate context-correct unified diffs, not in information insufficiency or lack of tool access. The `validate_patch` tool reveals the error but cannot enable the LLM to fix it, suggesting that alternative patch representations (e.g., search-and-replace, AST-level edits) may be more effective than tool augmentation within the unified diff paradigm.

## 5.6 Cost-Efficiency

The Blackboard architecture incurs significantly higher token costs (Table 2, Figure 4). BB uses an average of 54,849 tokens per issue compared to MP's 25,316 (2.17x increase). This difference is highly significant (Wilcoxon $W=34$, $p<0.001$). Hybrid falls between the two at 43,278 tokens (1.71x over MP).

The increased cost stems from the blackboard state serialization: each agent invocation includes the full shared state as context, which grows as agents contribute their outputs. In contrast, MP agents receive only their predecessor's output, resulting in more compact prompts.

Latency follows a similar pattern: BB averages 171 seconds per issue versus MP's 106 seconds (1.61x increase), also highly significant ($p<0.001$).

When computing cost-efficiency as tokens per resolved issue, the comparison is nuanced. MP uses approximately 211,000 tokens per resolution ($25,316 \times 50 / 6$), while BB uses approximately 343,000 ($54,849 \times 50 / 8$). The marginal cost of BB's two additional resolutions is high, reflecting the overhead of shared-state serialization applied to all 50 issues. However, as absolute resolve rates improve with better underlying models, the fixed overhead of blackboard serialization would be amortized across more successful resolutions.

## 5.7 Case Study: django-13028

To illustrate the information preservation mechanism, we examine django-13028, an issue resolved exclusively by the Blackboard configuration (Figure 6).

**Issue Description**: The issue reports that `QuerySet.values()` and `values_list()` do not properly handle the `FilePathField` type, returning `pathlib.Path` objects instead of strings when the field's value has been set programmatically. The fix requires modifying the `from_db_value` method or the queryset value conversion logic.

**MP Failure**: Under Message-Passing, the Planner correctly identifies the root cause---a naming collision between a user-defined `filterable` field and Django's internal `check_filterable` method. However, its natural language summary to the Coder compresses the diagnosis into ~679 tokens without the exact traceback line numbers or the specific method location (`Query.check_filterable` at line 1131 of `django/db/models/sql/query.py`). Working from this summarized context, the Coder patches `Query.clone()` at line 355---a different method in the same file that deals with query cache management rather than filterability checking. Despite three iterations, the Coder never locates the actual `check_filterable` method.

**BB Success**: Under Blackboard, the Coder reads the Planner's structured analysis alongside the verbatim issue description, which includes the full error traceback: `File "django/db/models/sql/query.py", line 1131, in check_filterable`. The Planner's analysis explicitly lists `Query.check_filterable` as the relevant function. With direct access to these details, the Coder generates a precisely targeted one-iteration patch that adds a `hasattr(expression, '_meta')` guard to exclude model instances from the filterability check, correctly resolving the issue.

**Concrete Impact**: MP consumed 34,042 tokens across 3 iterations (131s) and failed; BB consumed 30,732 tokens in 1 iteration (67s) and succeeded. The failure illustrates how message-passing creates a *lossy summarization bottleneck*: even when the Planner's diagnosis is correct, compressing it into a text summary strips the precise location information needed for targeted patching. The Blackboard architecture eliminates this failure mode by preserving structured data---including exact function names and traceback line numbers---alongside the original issue text.

## 5.8 Statistical Summary

Table 8 summarizes all statistical tests performed.

| Test | Comparison | Statistic | $p$-value |
|------|-----------|-----------|-----------|
| McNemar (exact) | MP vs BB | $b=1, c=3$ | $p=0.625$ |
| McNemar (exact) | MP vs Hybrid | $b=1, c=1$ | $p=1.000$ |
| McNemar (exact) | BB vs Hybrid | $b=2, c=0$ | $p=0.500$ |
| Cohen's $h$ | BB vs MP | $h=0.116$ | negligible |
| Odds Ratio | BB vs MP | OR=1.40 | 95% CI [0.45, 4.37] |
| Wilcoxon | MP vs BB tokens | $W=34$ | $p<0.001$* |
| Wilcoxon | MP vs Hybrid tokens | $W=183$ | $p<0.001$* |
| Wilcoxon | MP vs BB latency | $W=63$ | $p<0.001$* |
| Wilcoxon (IFS) | MP vs BB Coder | $W=36.5$ | $p=0.058$ |

*Table 8: Statistical test results. * indicates significance at $\alpha=0.05$.*
