# 6. Discussion

## 6.1 The Information Preservation Advantage

Our results provide clear evidence that the Blackboard architecture improves information preservation in multi-agent SE pipelines. The 50% improvement in Coder-stage IFS (0.584 vs. 0.390) demonstrates that shared-state access meaningfully increases the retention of key technical entities from the original issue description to the code generation stage. This finding aligns with prior work on Blackboard architectures for reasoning tasks [Wang et al., 2025] and data science [Salemi et al., 2025], extending the evidence to the software engineering domain.

The mechanism behind this improvement is straightforward: in Message-Passing mode, the Coder's only source of information about the issue is the Planner's natural language summary, which inevitably compresses and paraphrases the original content. In Blackboard mode, the Coder has simultaneous access to both the Planner's analysis and the original issue text, enabling cross-referencing and recovery of details that may be absent from the Planner's summary. This architectural guarantee of information access is the Blackboard's fundamental advantage.

The marginal significance of the IFS difference ($p=0.058$) is noteworthy. With 28 paired observations showing non-zero differences, the test approaches conventional significance despite the relatively small sample. A post-hoc power analysis suggests that approximately 35--40 paired observations with non-zero IFS differences would be needed to achieve $p<0.05$ at the observed effect size, indicating that a modestly larger experiment would likely yield statistical significance.

## 6.2 Why Is the Resolve Rate Difference Limited?

The central puzzle of our results is the gap between the large IFS improvement (50%) and the modest resolve rate improvement (4 percentage points). The patch quality analysis (Section 5.4) and tool use ablation (Section 5.5) together reveal a clear causal chain that explains this gap.

**Information Flow Bottleneck.** We propose an *information flow bottleneck model* that traces how BB's advantages propagate---and where they are attenuated---through the pipeline:

1. **Upstream: BB significantly outperforms MP.** BB achieves 50% higher IFS at the Coder stage, which translates to a 27.5 percentage-point advantage in correct file targeting (82.6% vs. 55.1%). These are large, practically meaningful differences that demonstrate BB's effectiveness at information preservation and code localization.

2. **Downstream: A systematic bottleneck limits all modes.** Once the correct file is identified, all three communication modes achieve nearly identical conditional resolve rates (~22%). The LLM's inability to reliably generate context-correct unified diffs---with exactly matching context lines, correct hunk headers, and proper formatting---acts as a rate-limiting step that is independent of communication architecture.

3. **Tool use does not resolve the bottleneck.** Our ablation study (Section 5.5) tested whether equipping the Coder with file reading and patch validation tools could address this limitation. Despite the demonstrated potential of tool-augmented LLMs for code generation [Chen et al., 2021; Roziere et al., 2023], access to actual source files and the ability to detect format errors via `validate_patch` does not enable the LLM to generate corrected patches. Tool use increases token consumption by 2--4$\times$ without improving resolve rates.

4. **The bottleneck attenuates upstream advantages.** Because only ~22% of correctly-targeted patches succeed regardless of communication mode, BB's 27.5pp file-targeting advantage translates to approximately $27.5 \times 0.22 \approx 6$ additional resolve-rate percentage points in expectation---close to the observed 4pp gain.

This model reframes the discussion: the question is not why BB's advantage is "small," but rather that BB's advantage is *exactly the size predicted* by the downstream bottleneck. As LLM diff generation precision improves---or as alternative patch representations (search-and-replace, AST-level edits) bypass the bottleneck---BB's upstream advantage should translate more fully into resolve rate gains.

**Sample Size Limitation.** With only 50 issues and resolve rates of 12--16%, McNemar's test has very low power. The 4 discordant pairs ($b=1$, $c=3$) are far below the ~20 discordant pairs typically needed for adequate power. A power analysis indicates that approximately 200 issues would be needed to detect a 4 percentage-point difference with 80% power at $\alpha=0.05$, assuming similar discordant pair proportions.

## 6.3 Why Does Hybrid Not Outperform?

The Hybrid configuration (12.0%) matches MP rather than exceeding BB, contrary to the intuition that combining both information channels should be at least as effective as either alone. The patch quality analysis (Section 5.4) reveals a nuanced picture.

**Context Overload and Empty Patches.** Hybrid mode's most striking failure is its 36% empty-patch rate (18/50), compared to 2% for MP and 8% for BB. The Coder, when presented with both message-passing summaries and structured blackboard state, frequently produces no diff output. The combined context increases average token consumption to 43,278 (1.71$\times$ over MP), and the dual information channels appear to confuse rather than assist the Coder.

**Strong Performance When Functional.** However, among the 32 issues where Hybrid *does* produce a non-empty patch, its correct file targeting rate is 78.1%---close to BB's 82.6% and far above MP's 55.1%. Furthermore, Hybrid's conditional resolve rate (24.0% of correctly-targeted files) is the highest of the three modes. This indicates that when the Coder successfully processes the hybrid input, it benefits from the blackboard's information richness nearly as much as in pure BB mode.

**Implication.** The Hybrid architecture's failure is not one of information quality but of *input format compatibility*. The dual-channel input overwhelms the Coder in 36% of cases, but produces competitive results otherwise. Future hybrid designs should focus on reducing context overload---for example, through selective sharing, progressive disclosure, or structured summarization of the blackboard state---rather than abandoning the hybrid concept entirely.

## 6.4 Implications for Practice and System Design

Our findings, together with the information flow bottleneck model (Section 6.2), carry several implications for the design of multi-agent SE systems.

**Adopt shared state for long pipelines.** The Blackboard architecture's information preservation benefit is likely to increase with pipeline length, as each additional agent handoff in message-passing introduces another compression step. For pipelines with more than 2--3 stages, shared state access should be considered a default architectural choice.

**Communication and code generation are orthogonal concerns.** Our results show that communication architecture optimization (upstream: information preservation, file targeting) and code generation optimization (downstream: patch correctness, diff formatting) address fundamentally different pipeline stages. Shared-state architectures determine *what* the system attempts to modify, while the LLM's patch generation capability determines *how well* the modification is executed. These concerns should be addressed independently.

**Recommended design strategy.** Multi-agent SE systems should adopt Blackboard or similar shared-state architectures for upstream optimization, while investing separately in downstream improvements---such as alternative patch representations (search-and-replace, AST-based edits), retrieval-augmented generation [Lewis et al., 2020] for context lines, or model fine-tuning for diff generation. The combination is expected to be multiplicative: BB's file-targeting advantage (83%) combined with improved patch precision would yield substantially higher resolve rates than either optimization alone.

**Information fidelity as a diagnostic metric.** IFS provides a stage-by-stage diagnostic independent of downstream task success. Even when resolve rates appear similar, IFS differences can reveal underlying information quality gaps that may become significant as other bottlenecks are resolved.

**Avoid naive hybrid designs.** Simply combining communication channels without careful integration can degrade rather than improve performance, as evidenced by Hybrid's 36% empty-patch rate. Future hybrid approaches should investigate selective sharing or progressive disclosure of blackboard state.
