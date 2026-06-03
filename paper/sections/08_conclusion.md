# 8. Conclusion and Future Work

## 8.1 Conclusion

This paper introduced SE-Blackboard, the first application of the Blackboard shared-state architecture to multi-agent software engineering. Through controlled experiments on 50 SWE-bench Lite issues, we demonstrated that communication architecture has a measurable impact on information preservation and, to a limited extent, task performance in multi-agent bug-fixing pipelines.

Our key findings are:

1. **Information Preservation**: The Blackboard architecture improves Coder-stage Information Fidelity Score by 50% relative to Message-Passing (0.584 vs. 0.390, Wilcoxon $p=0.058$). This demonstrates that shared-state access effectively mitigates knowledge drift---the progressive degradation of technical information through sequential agent handoffs.

2. **Code Localization**: BB's information advantage translates to a correct file targeting rate of 82.6% (vs. 55.1% for MP), demonstrating that improved information fidelity directly enables more accurate code localization---the critical prerequisite for successful patching.

3. **Resolve Rate**: Blackboard achieves a resolve rate of 16.0% compared to Message-Passing's 12.0%, a 33% relative improvement. While this difference is not statistically significant due to limited sample size (McNemar $p=0.625$), the directional improvement is consistent with the upstream metrics.

4. **Information Flow Bottleneck Model**: We identify a systematic bottleneck at the patch generation stage: once the correct file is targeted, all three communication modes achieve similar conditional resolve rates (~22%). This bottleneck---the LLM's limited ability to generate context-correct unified diffs---attenuates BB's significant upstream advantages. A tool use ablation study confirms that providing file access and patch validation tools does not resolve this bottleneck, as the LLM cannot correct its own formatting errors.

5. **Hybrid Caution**: Naively combining message-passing and blackboard communication degrades rather than improves performance, primarily due to context overload and elevated empty-patch rates (36% under Hybrid vs. 2% under MP). However, when Hybrid does produce patches, its file targeting rate (78.1%) approaches BB's.

These findings establish that communication architecture is an important and underexplored design dimension for multi-agent SE systems. Shared-state approaches offer measurable advantages in information preservation and code localization, and the information flow bottleneck model provides a framework for predicting when these advantages will translate into task-level improvements.

## 8.2 Future Work

Several directions emerge from our findings:

**Alternative Patch Representations.** Our tool use ablation demonstrates that the unified diff bottleneck is not resolved by giving the LLM access to source files and validation tools. Future work should explore alternative patch representations that bypass the context-line matching problem entirely: search-and-replace specifications, AST-level edit operations, or whole-file rewriting. These approaches trade patch expressiveness for generation reliability and may unlock the full potential of BB's upstream information advantages.

**Improved Diff Generation.** Complementary to alternative representations, research on improving LLM diff generation precision---through fine-tuning on patch corpora, constrained decoding for diff syntax, or retrieval-augmented generation for context lines---could directly address the identified bottleneck while retaining the unified diff format.

**Debate Topology.** The SE-Blackboard framework supports a Debate topology with multiple Coders generating competing patches and a Reviewer selecting the best candidate. Multiagent debate has been shown to improve factuality and reasoning in LLMs [Du et al., 2024]. Evaluating this topology under different communication architectures would test whether shared state benefits compound with increased agent diversity.

**Larger-Scale Evaluation.** Extending the experiment to the full SWE-bench Lite (300 issues) and including multiple LLMs (e.g., GPT-4o, Claude Opus, Gemini) would provide more statistical power for resolve rate comparisons and test the generalizability of our findings across model architectures.

**Broader SE Tasks.** The Blackboard architecture may benefit other SE tasks beyond bug fixing, including feature development, code review, requirements analysis, and test generation. Each task type presents different information preservation challenges that warrant investigation.

**Semantic IFS.** Replacing the rule-based entity extraction with embedding-based semantic matching would improve IFS sensitivity to paraphrased references and reduce false negatives, providing a more accurate measure of information fidelity.
