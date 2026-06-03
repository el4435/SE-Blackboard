# Response to Reviewers

**Manuscript**: SE-Blackboard: A Shared-State Architecture for Multi-Agent Software Engineering Pipelines
**Authors**: Erxi Liu, Qiang Zhu, Xinru Dong
**Journal**: IEEE Access (minor revision before final files)

We thank the Editor and the three reviewers for the careful, constructive review. Below we respond point-by-point. Item identifiers `[Rx-y]` refer to reviewer x, comment y as written in the original report. Section/Table references in **bold** indicate locations in the revised manuscript.

**Note on the reference list.** The IEEE Access Final Files Checklist states that the bibliography should not be expanded or trimmed post-acceptance, while also encouraging the authors to verify reference formatting. We have therefore observed the following discipline:

- We have **not removed** any existing reference.
- We have **added only references that were explicitly named by a reviewer** in this round, each tied to the specific reviewer comment that requested it (mapping below). No other references were added.
- We have **added DOIs to existing bibliography entries** as part of the encouraged formatting review.

The new references and the corresponding reviewer comments are listed at the end of this document for the Editor's and production team's convenience.

---

## Reviewer 1

**R1-1, R1-concern-1 (also R3-9) — Affiliation typo on Xinru Dong.**
We have corrected the rendering. In `main.tex` line 45 we changed `\authorrefmark{3}\authorrefmark{2}` to `\authorrefmark{3},\authorrefmark{2}`, which renders as the intended `^{3,2}` rather than `^{32}`. We also re-read the affiliation strings (lines 47--49) carefully and confirm they are correctly composed; the "Mechanical and Electrical al Engineering, Engineer" wording flagged by R3-9 is not present in the version of `main.tex` we are submitting, and we expect it was a rendering artifact of an earlier draft.

**R1-2, R1-concern-5 — Placeholder DOI in the header.**
The placeholder DOI `10.1109/ACCESS.2024.0429000` has been replaced with an empty `\doi{}` accompanied by a LaTeX comment indicating that the final DOI is to be assigned by IEEE Access production (`main.tex` line 40).

**R1-3, R1-concern-2 — Planner-stage IFS for MP mode.**
Thank you for this excellent suggestion. The Planner is invoked with an identical prompt and an identical input (the original issue text $I$) in all configurations, and the LLM is run with temperature 0. The MP Planner's output text was not separately persisted in our run logs, but under deterministic generation it is identical to the BB Planner's output, so the Planner-stage IFS for MP equals the BB Planner-stage IFS of 0.749. We have updated **Table IV** to report this value with a footnote explaining the deterministic-design reasoning. This addresses the reviewer's diagnostic intent: information loss between MP's Planner and Coder is now attributable to the message-passing handoff, not to the Planner output itself.

**R1-concern-3 — Tester IFS is very low; is Tester output expected to reference code?**
We have added an explanatory sentence in **Section V-B-2 (Information Decay Pattern)**: manual inspection of Tester outputs confirms they primarily report pass/fail counts and FAIL\_TO\_PASS test names, and do not generally reproduce the function/class identifiers from the original issue description. The low Tester IFS therefore reflects the design of Tester outputs rather than a failure of information preservation, and Tester IFS should not be used as a diagnostic for upstream communication quality.

**R1-concern-4 — Tool-use ablation 10-issue sample size.**
We have added an explicit caveat at the end of **Section V-E (Tool Use Ablation Study)**: the 10-issue ablation is sufficient to rule out a large positive effect but not to establish a precise null, and the result should be treated as directional evidence consistent with the bottleneck model rather than as a definitive negative finding.

**R1-gap-1 — IFS statistics broken down by repository.**
We have added **Section V-B-4 (Per-Repository Breakdown)** and the new **Table 5** (per-repo Coder IFS and file targeting). The Coder-IFS advantage of BB over MP holds on every repository in the sample: from $+17$% on Django (where MP already retains relatively rich content) to $+178$% on sympy, $+187$% on astropy, $+79$% on sphinx-doc, and an effective $33\times$ on pytest-dev. The resolve-rate advantage, in contrast, is concentrated on Django easy issues, consistent with the bottleneck model: on harder repositories the downstream patch-generation bottleneck dominates and upstream gains do not translate into additional resolved issues. The IFS effect of BB is therefore an architectural property of the communication layer rather than a Django-specific artifact.

**R1-gap-2 (also R2-major-3, R3-6) — Quantitative analysis of Hybrid empty-patch failures.**
We performed a case-by-case inspection of the 18 Hybrid empty-patch runs and added a paragraph in **Section V-C (Failure Analysis)**. In all 18 cases the Coder produced no parseable patch object at all (`blackboard_final_state.patches` is empty), even though the Reviewer was invoked three times as expected. The same 18 issues are also unresolved under MP and BB, so the failure concentrates on intrinsically hard issues; the dual-channel context appears to suppress the Coder's output precisely where the model already has the least useful signal. We interpret this as direct in-experiment evidence for the "context overload" hypothesis~\cite{liu2024lost} and have rewritten the discussion accordingly.

**R1-gap-3 (also R2-comprehensive-1) — Reviewer accept/reject dynamics.**
We have added **Section V-D-3 (Reviewer Accept/Reject Dynamics)**. Under BB, the Reviewer issues 55 accepts and 80 rejects; first-iteration acceptance occurs in 21 runs and the Reviewer never accepts in 17 runs. Under Hybrid the corresponding numbers are 37 accept, 103 reject, 13 first-iteration accepts, 29 never-accepted. BB therefore both elicits more first-iteration acceptances and reduces the never-accepted count. This is in-experiment evidence that BB's upstream information advantage propagates downstream into measurably more efficient Reviewer behavior. (MP does not persist verdicts; its iteration-count distribution is reported alongside in the new section.)

**R1-4 references — DOI on existing reference and three new references.**
Per the reviewer's request:
- The Jimenez et al. SWE-bench entry now includes the DOI `10.48550/arXiv.2310.06770` as a formatting correction.
- Zhong et al., *MemoryBank* (AAAI 2024, DOI `10.1609/aaai.v38i17.29946`) is now cited in **Section VI-C** alongside the discussion of context-overload remedies (selective sharing, progressive disclosure, on-demand memory management).
- Sumers et al., *Cognitive Architectures for Language Agents* (TMLR 2024, DOI `10.48550/arXiv.2309.02427`) is now cited in **Section III-A** as the theoretical grounding for our field-ownership and structured state-schema design.
- Lou et al., *Boosting Coverage-Based Fault Localization* (ESEC/FSE 2021, DOI `10.1145/3468264.3468580`) is now cited in **Section V-D-1** alongside the existing Wong et al. survey to provide a more recent fault-localization reference for the file-targeting discussion.

---

## Reviewer 2

**R2-major-1 (also R1-gap-1) — Django concentration and per-repository breakdown.**
Addressed by the new **Section V-B-4** and the new per-repository table, as described under R1-gap-1. The IFS advantage holds across every repository while the resolve-rate advantage is Django-concentrated. We report both findings explicitly and note that they are individually informative.

**R2-major-2 — IFS sensitivity to matcher choice.**
We have added **Section V-B-5 (Robustness of IFS to Matcher Choice)**. On a 19-issue subset we re-evaluated Coder-stage IFS using a stricter fuzzy matcher based on Python's `difflib.SequenceMatcher` with partial-match threshold 0.80. On this subset, the rule-based matcher yields a BB-over-MP relative IFS gap of $+39.3$%; the fuzzy matcher yields $+30.6$%. Both matchers preserve the directional advantage of BB. The qualitative conclusion (BB preserves more upstream information than MP) is robust to the matcher choice; the relative magnitude is moderately sensitive to matcher strictness, as expected.

**R2-major-3 — Hybrid empty-patch concrete description.**
Addressed by the paragraph added in **Section V-C** under R1-gap-2 above.

**R2-minor-1 — Iteration column in Table II.**
We have removed the iteration column from **Table II** as the values were not analyzed at that point. The iteration analysis now lives in the new **Section V-D-3 (Reviewer Accept/Reject Dynamics)**, where it is connected to the main findings.

**R2-minor-2 — Threats §VII LLM-independence claim reframed as hypothesis.**
The corresponding paragraph in **Section VII (Internal Validity)** now reads, "We hypothesize that the underlying direction of BB's advantage... should generalize across LLMs... This hypothesis, however, remains to be tested directly with other models and should not be treated as an empirical finding of the present study."

**R2-minor-3 — Acknowledgment of Claude assistance with specifics.**
We have expanded the Acknowledgment paragraph (line 577) to describe which components Claude assisted with (scaffolding the four agent base classes, drafting the SWE-bench Docker harness wrapper, and producing initial versions of the analysis scripts in Section V) and how outputs were reviewed (review by the first author, integration into the 63-test regression suite, and validation against the reported experimental results). We also clarify that the experiment design, all empirical claims, the statistical analyses, and the conclusions were produced and verified by the authors.

**R2-minor-4 — Abstract reframing.**
We have rewritten the abstract to lead with the methodological/diagnostic contribution (the SE-Blackboard framework as a controlled comparison, the IFS metric as a stage-level diagnostic, and the bottleneck model as the conceptual contribution), and to position the modest end-to-end resolve-rate improvement as a consequence of the bottleneck model rather than as the headline result. The new abstract is 222 words and remains within the 150--250 word limit.

**R2-comprehensive-1 — Reviewer agent role / iteration counts.**
Addressed by the new **Section V-D-3** as described under R1-gap-3 above.

**R2-cost — Tokens per resolved issue.**
We have rewritten **Section V-F (Cost-Efficiency)** to add a dedicated paragraph on tokens-per-resolved (MP $\approx$ 211k, BB $\approx$ 343k, Hybrid $\approx$ 361k), an explicit per-stage cost decomposition (new **Table 9**, per-agent token consumption, localizing BB's overhead at the Reviewer agent due to blackboard serialization), and a contrast between successful-run cost and failed-run cost in every configuration. The trade-off is now framed for practitioners as deliberate cost for higher upstream information quality rather than a free improvement.

**R2-future — Debate topology pilot.**
We have considered this. A debate-topology pilot was outside the scope we could complete within the minor-revision time frame, and we would prefer not to introduce a small auxiliary experiment that could confound the reading of the main bottleneck argument. We have however strengthened the Future Work entry on Debate (Section VIII) to make clear that it is an immediate next step. We thank the reviewer for the suggestion.

**R2-ref-1 — Citation for unreliability of LLM unified-diff generation.**
Following the reviewer's guidance, we have reframed this claim. The reviewer's exact wording: "If prior work has documented this problem, it should be cited. If this is an original finding of the current study, it should be stated more explicitly as such rather than presented as a known constraint." Because we are not aware of a specific peer-reviewed reference that empirically isolates LLM unified-diff context-line reliability in the way our argument requires, we have rewritten the relevant passage in **Section VI-B (Why Is the Resolve Rate Difference Limited?)** to state explicitly that this is an empirical observation from the present study (drawn from the 50-issue patch-quality decomposition and the tool-use ablation), and we now describe the specific failure modes we observe (mismatched context lines, incorrect line numbers in hunk headers, off-by-one offsets) rather than presenting the unreliability claim as an external given. No new reference was added for this point.

**R2-ref-2 — MAGIS reference.**
Tao et al., *MAGIS* (arXiv 2024, DOI `10.48550/arXiv.2403.17927`) is now cited in **Section II-A** in the discussion of multi-agent SE systems for issue resolution. We note explicitly that MAGIS's role-specialized agents communicate through structured handoffs and that its design goals are closely aligned with ours, while observing that MAGIS does not isolate communication architecture as an independent variable.

---

## Reviewer 3

**R3-1 — Definition of "knowledge drift" in the introduction.**
We have added an explicit definition of knowledge drift in **Section I (Introduction)**: "the cumulative loss or distortion of technical entities, identifiers, and references that occurs as task-relevant content is paraphrased through successive agent handoffs, leading downstream agents to operate on a representation that no longer fully reflects the original problem specification."

**R3-2 — Extend related work for modern tool-based agent coordination.**
We have added a paragraph in **Section II-A (Multi-Agent Systems for Software Engineering)** that explicitly contrasts SWE-Agent, AutoCodeRover, and Agentless on their agent--computer interfaces and observes that these works emphasize what each agent can \emph{do} rather than how agents \emph{exchange} information --- which is the gap our work addresses. No new citations were added for this point; the cited papers were already in our bibliography, in line with our discipline of only adding references that a reviewer explicitly named.

**R3-3 — Justify stratified sampling of 50 issues.**
We have rewritten the relevant sentences in **Section IV-A (Benchmark)** to state that issues were sampled to balance evaluation cost, repository diversity, and difficulty coverage while remaining comparable to prior small-scale SWE-bench Lite studies, and that Django over-representation is a consequence of the FAIL\_TO\_PASS / PASS\_TO\_PASS evaluation protocol favoring repositories with comprehensive test coverage. We also cross-reference Section VII for the external-validity implications.

**R3-4 — Statistical power limitations.**
We strengthened the "A note on statistical power" paragraph in **Section VI-B**. The required $N \approx 300$ is now displayed in bold; we added an explanation that intrinsic discordant-pair scarcity ($b + c = 4$ at the present discordance rate) compounds the power problem and would persist even at a doubled sample size; and we restate that the 4pp resolve-rate improvement should be interpreted as descriptive rather than confirmatory.

**R3-5 — IFS variance per configuration.**
We have updated **Table IV** to report mean $\pm$ standard deviation for every cell, with per-issue standard deviations computed across the available IFS measurements.

**R3-6 — Hybrid empty-patch reasons.**
Addressed by the deep-dive paragraph added in **Section V-C** (see R1-gap-2 above).

**R3-7 — Detailed compute cost and token analysis.**
Addressed by the rewrite of **Section V-F (Cost-Efficiency)** and the new **Table 9** (per-agent token consumption), as described under R2-cost above.

**R3-8 — IFS vs. prior multi-agent evaluation criteria.**
We have added a paragraph at the end of **Section IV-C (Evaluation Metrics)** distinguishing IFS from task-success, role-consistency, and dialogue-quality criteria, and emphasizing that IFS isolates the contribution of the communication layer from confounds such as patch-formatting reliability. We use IFS alongside, not in place of, resolve rate.

**R3-9 — Affiliation typo on page 1.**
The text "Mechanical and Electrical al Engineering, Engineer" does not appear in the version of `main.tex` we are submitting; line 49 reads "School of Mechanical and Electrical Engineering, Beijing Institute of Graphic Communication, Beijing, China." We suspect this was a rendering artifact of an earlier draft. We will reconfirm at the page-proof stage.

**R3-10 — Case study path-wise comparison.**
We have added a "Path-wise comparison" bullet list to **Section V-G (Case Study: django-13028)** that traces the MP and BB interaction sequences step by step, identifying the precise Planner $\rightarrow$ Coder handoff where MP's lossy summarization discards the file/line traceback information.

**R3-11 — Future measures to overcome the patch-generation bottleneck.**
We have expanded **Section VIII-B (Alternative Patch Representations and Improved Diff Generation)** with three concrete patch-representation candidates (search-and-replace, AST-level edits, whole-file rewriting), explicit per-candidate viability remarks, and a description of progressively lenient patch-apply heuristics (\texttt{git apply} $\rightarrow$ \texttt{patch -F0} $\rightarrow$ \texttt{patch -F3}) as a practical compromise.

**R3-12 — Clearer p-values for Wilcoxon and McNemar.**
The p-values are summarized in the Statistical Summary table (Section V-H, Table 10) and additionally cited inline at each significance claim in Sections V-A, V-B, and V-H (now including the Wilcoxon $W$ statistic and $p$-value for tokens and latency in Section V-H).

**R3-13 — Explain the tool ablation prompts.**
We have extended **Section V-E (Tool Use Ablation Study)** with a paragraph describing how tools are exposed (JSON schema), what the Coder is instructed to do (call `read_file` or `search_code` before producing a diff; use `validate_patch` before `submit_patch`; retry on validation failure up to two times), and what is unchanged from the non-tool baseline (system prompt, Planner / Reviewer / Tester implementations).

**R3-14 — Define $S$ and $W(k)$ directly after first introduction.**
We have added an explicit signature for $W$ in **Section III-A**: "$W : \mathcal{K} \to 2^{\{I,A,P,R,T\}}$ assigns each agent role $k \in \mathcal{K} = \{\text{Planner}, \text{Coder}, \text{Reviewer}, \text{Tester}\}$ the subset of state fields that role is permitted to modify." We have also added a sentence noting that the IssueInfo field $I$ is excluded from every $W(k)$, making it read-only for all agents.

---

## Summary of changes

- **4 small format / placeholder fixes**: A1 affiliation, A2 DOI, Iter-column removal in Table II, DOI added to existing Jimenez/SWE-bench entry.
- **15 textual revisions** in the Introduction, Related Work, Experimental Setup, Results, Threats, Conclusion, Future Work, Abstract, and Acknowledgment sections.
- **6 new data analyses** added to the Results section, all computed from existing experiment data without rerunning the pipeline:
  - Per-repository IFS and file targeting (new **Table 5**).
  - IFS standard deviations now reported alongside means (Table IV update).
  - Hybrid empty-patch case-by-case categorization (in-text paragraph in §V-C).
  - Reviewer accept/reject verdict dynamics (§V-D-4).
  - Per-agent token decomposition and tokens-per-resolved (new **Table 9**, §V-F).
  - IFS sensitivity to matcher choice (§V-B-5, fuzzy-matching robustness check).
- **1 new deliverable**: Graphical Abstract (`GA.jpg`, 660$\times$295, 19.8 KB) derived from the bottleneck model figure, with a 39-word caption (`GA_caption.docx`).

### New references added in this revision (each tied to a specific reviewer comment)

| Reference | Cited in | Requested by |
|---|---|---|
| Zhong et al., *MemoryBank*, AAAI 2024 (DOI `10.1609/aaai.v38i17.29946`) | §VI-C (Hybrid context overload remedies) | **R1 Comment #4** |
| Sumers, Yao, Narasimhan, Griffiths, *Cognitive Architectures for Language Agents*, TMLR 2024 (DOI `10.48550/arXiv.2309.02427`) | §III-A (theoretical justification for field ownership and structured state) | **R1 Comment #4** |
| Lou, Chen, Zhang, Hao, *Boosting Coverage-Based Fault Localization*, ESEC/FSE 2021 (DOI `10.1145/3468264.3468580`) | §V-D-1 (file targeting / fault localization) | **R1 Comment #4** |
| Tao, Zhou, Zhang, Wang, *MAGIS*, arXiv 2024 (DOI `10.48550/arXiv.2403.17927`) | §II-A (multi-agent SE systems) | **R2 reference gap #2** |

### DOI completeness pass (existing entries)

As part of the formatting review encouraged by the IEEE Access checklist, we added DOIs to every existing bibliography entry where a canonical DOI or an arXiv DOI was available and unambiguous. Two entries remain without a DOI in the submitted bibliography (`fang2025rtadev` and `he2025llm`) because we could not verify a canonical DOI with high confidence within the revision window; we are happy to add these at the proof stage if the production team has access to authoritative values.

### Not added
No references were removed. No references beyond the four listed above were added (specifically, the unified-diff-reliability claim that **R2** flagged was reframed as an empirical observation of the present study rather than supported by a new external citation).
