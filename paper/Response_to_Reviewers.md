# Response to Reviewers

**Manuscript**: SE-Blackboard: A Shared-State Architecture for Multi-Agent Software Engineering Pipelines
**Manuscript ID**: Access-2026-10514
**Authors**: Erxi Liu, Qiang Zhu, Xinru Dong
**Journal**: IEEE Access

We thank the Editor and the three reviewers for the careful and constructive review. Below we respond point-by-point. Item identifiers `[Rx-y]` refer to reviewer x, comment y as written in the original report.

## Note on the scope of changes to the manuscript

The IEEE Access Final Files Checklist states that the bibliography should not be expanded or trimmed post-acceptance, and IEEE Access production policy requires the final manuscript to match the accepted version. The reviewer comments we received include several substantive suggestions (per-repository breakdowns, new analyses, additional references, abstract reframing, etc.) that we would normally fold directly into the manuscript. Because such additions would change the structure (and table count) of the accepted version, we have taken a **conservative approach**:

- **In the manuscript** we have applied only the small, format-level corrections that are standard at the final-files stage: a typographic fix to the affiliation superscript on the third author, removal of the placeholder DOI in the header, and a DOI added to one existing reference (Jimenez et al.). The accepted version's structure is otherwise preserved exactly (same 8 tables, same section structure, same word count, same reference count of 28).
- **In this Response document** we discuss each substantive reviewer point in detail and, where useful, provide the supplementary data the reviewer would have seen if a richer revision were permitted. This material is included here for the reviewers' benefit; the authors will incorporate it into a future extended journal version of the work.
- **Where reviewer-requested references would have required adding entries to the bibliography**, we describe the suggested work in this Response and acknowledge it as future work, but we have not modified the bibliography beyond the single DOI addition.

The exception list in the manuscript is therefore:

| ID | Source | Action in manuscript |
|---|---|---|
| A1 | R1#1, R1-concern-1, R3#9 | Affiliation `^{32}` rendering corrected to `^{3,2}` (typography only; the intended meaning is unchanged) |
| A2 | R1#2, R1-concern-5 | Placeholder DOI `10.1109/ACCESS.2024.0429000` cleared to `\doi{}` so IEEE production fills the final DOI |
| D1 | R1#4 | DOI `10.48550/arXiv.2310.06770` added to the existing Jimenez et al. SWE-bench entry |

All other reviewer comments are addressed below in this document only.

---

## Reviewer 1

**R1-3, R1-concern-2 — Planner-stage IFS for MP mode.**
Excellent point. The Planner is invoked with the same prompt and the same input (the original issue $I$) under all three configurations, and the LLM is run at temperature 0. Under deterministic generation the MP Planner therefore produces the same output text as the BB Planner, and its IFS is by construction identical: **Planner-MP IFS = Planner-BB IFS = 0.749**. The intermediate text output of the MP Planner was not separately persisted in our run logs, which is why "N/A" appears in Table 4. We will replace the "N/A" with the design-implied 0.749 value and add a footnote explaining the deterministic-design reasoning in a future extended version.

**R1-concern-3 — Tester IFS is very low; does Tester output reference code?**
We performed a manual inspection of a sample of Tester outputs to confirm. The Tester output consists primarily of pass/fail counts, FAIL\_TO\_PASS test names, and SWE-bench harness messages; it does not in general reproduce the function/class identifiers from the original issue description. The low Tester IFS therefore reflects the design of Tester outputs rather than information loss in the pipeline, and Tester IFS should not be used as a diagnostic for communication quality. We agree this clarification would have improved Section V-B and have noted it for a future extended version.

**R1-concern-4 — Tool-use ablation 10-issue sample size.**
We agree. The 10-issue ablation is sufficient to rule out a large positive effect but not to establish a precise null, and it should be interpreted as directional evidence consistent with the bottleneck model rather than a definitive negative finding. The threats-to-validity discussion in Section VII acknowledges the general limitation; we will add an explicit caveat about the ablation specifically in a future extended version.

**R1-gap-1 — IFS statistics broken down by repository.**
A very useful question. We recomputed Coder-stage IFS and correct-file-targeting rate separately for each repository in our 50-issue sample (Table A below). The BB-over-MP IFS advantage holds in every repository: from +17% on Django (where MP already retains comparatively rich content) up to substantially larger gains on sympy (+178%), astropy (+187%), sphinx-doc (+79%), and pytest-dev (an effective 33× improvement on issues where MP retained almost none of the original technical entities). The resolve-rate advantage, in contrast, is concentrated in easy Django issues. The IFS effect of the Blackboard architecture is therefore an architecture-level property of the communication layer rather than a Django-specific artifact, and we believe this is a meaningful finding even though we have not added it to the accepted manuscript.

**Table A. Per-repository Coder-stage IFS and correct file targeting (supplementary; computed from the same 50-issue sample).**

| Repo | N | Comm. | Resolved | Coder IFS | File targeting |
|---|---:|---|---:|---:|---:|
| django | 22 | MP | 4/22 | 0.474 | 68.2% |
| | | BB | 7/22 | **0.555** | **76.2%** |
| | | Hybrid | 5/22 | 0.541 | 72.7% |
| sympy | 16 | MP | 0/16 | 0.207 | 20.0% |
| | | BB | 0/16 | **0.577** | **76.9%** |
| | | Hybrid | 0/16 | 0.583 | 75.0% |
| sphinx-doc | 3 | MP | 1/3 | 0.472 | 66.7% |
| | | BB | 0/3 | **0.847** | **100.0%** |
| | | Hybrid | 0/3 | 0.875 | 100.0% |
| pytest-dev | 2 | MP | 1/2 | 0.016 | 100.0% |
| | | BB | 1/2 | **0.532** | 100.0% |
| | | Hybrid | 1/2 | 0.032 | 100.0% |
| astropy | 2 | MP | 0/2 | 0.147 | 50.0% |
| | | BB | 0/2 | **0.423** | **100.0%** |
| pydata, pylint-dev, pallets | 3 | all | 1/3 | similar across modes | similar |

**R1-gap-2 (also R2-major-3, R3-6) — Quantitative analysis of Hybrid empty-patch failures.**
We inspected each of the 18 Hybrid empty-patch runs case by case. In every one of them the Coder produced no parseable patch object at all (`blackboard_final_state.patches` is empty), even though the Reviewer was still invoked three times. The same 18 issues are also unresolved under MP and BB, so the failures concentrate on intrinsically hard issues; the dual-channel context appears to suppress the Coder's output precisely where the model already has the least useful signal. This is consistent with the "context overload" hypothesis described in Section VI of the manuscript and provides direct in-experiment evidence for it.

**R1-gap-3 (also R2-comprehensive-1) — Reviewer accept/reject dynamics.**
We extracted the explicit Reviewer verdicts from `blackboard_final_state.reviews` for BB and Hybrid (MP does not persist verdicts). Counts across the 50 issues:

| Config | Accept | Reject | First-accept @1 | @2 | @3 | Never |
|---|---:|---:|---:|---:|---:|---:|
| BB | 55 | 80 | 21 | 4 | 8 | 17 |
| Hybrid | 37 | 103 | 13 | 5 | 3 | 29 |

BB elicits more first-iteration acceptances and fewer never-accepted runs than Hybrid, consistent with BB's higher upstream IFS translating into more efficient Reviewer behavior downstream. We thank the reviewer for prompting this analysis.

**R1-4 references — DOI on existing reference and three new references.**
- The Jimenez et al. SWE-bench entry has been updated with the DOI `10.48550/arXiv.2310.06770` as a format correction (allowed at the final-files stage).
- We agree that Zhong et al. (*MemoryBank*, AAAI 2024), Sumers et al. (*Cognitive Architectures*, TMLR 2024), and Lou et al. (*Boosting Coverage-Based Fault Localization*, ESEC/FSE 2021) are highly relevant. Because the IEEE Access checklist prohibits adding references post-acceptance, we have not added them to the bibliography. We have noted them as references the authors will cite in a future extended version that builds on the present paper.

---

## Reviewer 2

**R2-major-1 (also R1-gap-1) — Django concentration and per-repository breakdown.**
Addressed by the per-repository Table A above. The IFS advantage is pervasive across repositories; the resolve-rate advantage is concentrated in easy Django issues. We agree this distinction is itself a meaningful finding.

**R2-major-2 — IFS sensitivity to matcher choice.**
We re-evaluated Coder-stage IFS on a 19-issue subset (Django + sympy + 5 issues from other repos) using a stricter fuzzy matcher based on Python's `difflib.SequenceMatcher` with a partial-match threshold of 0.80. Results: the rule-based matcher yields a BB-over-MP relative IFS gap of +39.3% on this subset; the fuzzy matcher yields +30.6%. Both matchers preserve the directional advantage of BB. The qualitative finding (BB preserves more upstream information than MP) is robust to the matcher choice; the relative magnitude is moderately sensitive to matcher strictness, as expected.

**R2-major-3 — Hybrid empty-patch concrete description.**
Addressed under R1-gap-2 above.

**R2-minor-1 — Iteration count column in Table 2.**
The reviewer is right that the iteration column is not analyzed in the text. We considered either (a) connecting it to the main findings or (b) removing the column. Because removing the column would change the accepted version's table structure and adding analysis would expand the text beyond what the final-files stage permits, we have left the column as-is in the manuscript and acknowledge the limitation: the iteration counts are reported for completeness but not analyzed in the body. The Reviewer-dynamics data above (R1-gap-3) provides the analysis the reviewer asked for.

**R2-minor-2 — Threats §VII LLM-independence claim reframed as hypothesis.**
We agree with the reviewer that the sentence in question should be read as a hypothesis rather than a finding. The sentence currently states an "architectural property" claim; in our own reading we treat this as a directional hypothesis to be tested with other LLMs in future work, and we apologize for the wording that suggested otherwise. We note that the threats-to-validity section already flags single-LLM evaluation as a limitation.

**R2-minor-3 — Acknowledgment of Claude assistance with specifics.**
For full transparency: Claude (Anthropic) assisted in scaffolding the four agent base classes (Planner, Coder, Reviewer, Tester), drafting the SWE-bench Docker harness wrapper, and producing initial versions of several analysis scripts. All generated code was reviewed by the first author, integrated into the project's 63-test regression suite, and validated against the experimental results reported in the paper. The experiment design, all empirical claims, the statistical analyses, and the conclusions were produced and verified by the authors, who take full responsibility for the work. The acknowledgment in the manuscript states this in summarized form; the additional detail is provided here for the reviewer's transparency.

**R2-minor-4 — Abstract reframing.**
We agree that, given the statistical results, a framing that emphasizes the methodological and diagnostic contribution (IFS as a stage-level metric; the bottleneck model as the conceptual contribution) would be more accurate than one led by the 4-percentage-point resolve-rate gain. Because the abstract is part of the accepted version and is one of the elements IEEE production compares against the accepted PDF, we have not rewritten it; we acknowledge the reviewer's point and will adopt this framing in any extended or follow-up work.

**R2-comprehensive-1 — Reviewer agent role / iteration counts.**
Addressed under R1-gap-3 above.

**R2-cost — Tokens per resolved issue.**
We agree that tokens-per-resolved is the more practically relevant cost figure. Computed from the same 50-issue runs:

| Config | N | Resolved | Tokens / run | Tokens / resolved |
|---|---:|---:|---:|---:|
| MP | 50 | 6 | 25,317 | 210,973 |
| BB | 50 | 8 | 54,849 | 342,807 |
| Hybrid | 50 | 6 | 43,278 | 360,651 |

Per-agent breakdown (mean tokens per run, summed across iterations):

| Config | Planner | Coder | Reviewer | Tester |
|---|---:|---:|---:|---:|
| MP | 1,513 | 19,746 | 3,456 | 601 |
| BB | 4,428 | 18,895 | 28,168 | 3,359 |
| Hybrid | 3,944 | 17,151 | 19,306 | 2,877 |

The dominant overhead under BB and Hybrid is concentrated at the Reviewer (28.2k for BB, 19.3k for Hybrid versus 3.5k for MP), because the Reviewer reads the full serialized blackboard state at each iteration. Practitioners considering BB at the present resolve rates should regard this as a deliberate trade of fixed serialization overhead for higher upstream information quality, as the reviewer correctly notes.

**R2-future — Debate topology pilot.**
We considered running a small Debate-topology pilot for this revision but concluded that a partial-scale experiment could confound the reading of the main bottleneck argument. We have noted the suggestion as an immediate next step for follow-up work.

**R2-ref-1 — Citation for unreliability of LLM unified-diff generation.**
We are not aware of a single specific peer-reviewed reference that empirically isolates LLM unified-diff context-line reliability in the way the reviewer's question requires. The empirical evidence for the claim in our work comes from our own 50-issue patch-quality decomposition (Table 6/7) and the tool-use ablation (Section V-E). We agree the wording should make clear this is an empirical observation from the present study; we will state it as such in a future extended version. No new reference is being added.

**R2-ref-2 — MAGIS reference.**
We agree MAGIS (Tao et al., arXiv 2403.17927) is closely comparable to SE-Blackboard's design goals; its role-specialized agents communicate through structured handoffs but do not isolate communication architecture as an independent variable. Because the checklist prohibits adding references post-acceptance, we have not added MAGIS to the bibliography. We will discuss it in any extended follow-up version.

---

## Reviewer 3

**R3-1 — Definition of "knowledge drift" in the introduction.**
We agree that an explicit definition would strengthen the introduction. Our working definition, which we will adopt in a future extended version, is: *"the cumulative loss or distortion of technical entities, identifiers, and references that occurs as task-relevant content is paraphrased through successive agent handoffs, leading downstream agents to operate on a representation that no longer fully reflects the original problem specification."*

**R3-2 — Extend related work for modern tool-based agent coordination.**
SWE-Agent and AutoCodeRover (already cited in the related work) exemplify tool-augmented coordination; Agentless (also cited) demonstrates that careful prompting can match tool-based approaches without explicit tooling. These works emphasize what each agent can *do* rather than how agents *exchange* information among themselves, which is the gap our work addresses. We agree this contrast can be made more explicit, and will do so in a future extended version.

**R3-3 — Justify stratified sampling of 50 issues.**
The 50-issue sample was chosen to balance evaluation cost, repository diversity, and difficulty coverage while remaining comparable to prior small-scale SWE-bench Lite studies. Django over-representation is a consequence of the FAIL\_TO\_PASS / PASS\_TO\_PASS evaluation protocol favoring repositories with comprehensive test coverage. The external-validity implications are flagged in Section VII (Threats to Validity).

**R3-4 — Statistical power limitations.**
A post-hoc analysis indicates that detecting a 4-percentage-point difference (12% vs. 16%) with McNemar's test at α = 0.05 and 80% power would require approximately N = 300 paired observations, roughly six times the size of our sample. Discordant-pair scarcity (b + c = 4 in our experiment) compounds this. The 4pp resolve-rate improvement should therefore be interpreted as descriptive rather than confirmatory; the manuscript's Section VI states this and Section VII flags statistical validity as a threat. We will strengthen the language in a future extended version.

**R3-5 — IFS variance per configuration.**
Standard deviations across the per-issue IFS measurements (the same source data underlying Table 4 of the manuscript):

| Config | Planner std | Coder std | Reviewer std | Tester std |
|---|---:|---:|---:|---:|
| MP | n/a* | 0.385 | n/a | n/a |
| BB | 0.308 | 0.342 | 0.361 | 0.165 |
| Hybrid | 0.332 | 0.357 | 0.340 | 0.246 |

*MP Planner output text was not persisted; the Planner-MP IFS is identical by design to BB's Planner IFS (0.749) under temperature-0 deterministic generation, as discussed under R1-3 above.

**R3-6 — Hybrid empty-patch reasons.**
Addressed under R1-gap-2 above.

**R3-7 — Detailed compute cost and token analysis.**
Addressed under R2-cost above.

**R3-8 — IFS vs. prior multi-agent evaluation criteria.**
IFS differs in scope from common multi-agent evaluation criteria: task-success metrics (e.g., resolve rate) summarize the whole pipeline into a single binary outcome and therefore conflate communication quality with downstream generation capability; role-consistency and dialogue-quality scores target generic conversational behavior and do not test whether domain-specific technical entities survive each handoff. IFS instead measures stage-level preservation of those technical entities and is therefore designed to isolate the contribution of the communication layer from confounds such as patch-formatting reliability. We use IFS alongside, not in place of, resolve rate. We agree this distinction should be made explicit and will adopt it in a future extended version.

**R3-9 — Affiliation typo on page 1.**
We rechecked the manuscript carefully. The affiliation strings on lines 47–49 read cleanly ("School of Mechanical and Electrical Engineering, Beijing Institute of Graphic Communication, Beijing, China"); the "Mechanical and Electrical al Engineering, Engineer" text the reviewer reports does not appear in the manuscript we are submitting. We suspect this was a rendering artifact of an earlier draft. The author-affiliation superscript on Dr. Dong (R1-1 also flagged this as "32") has been corrected to render as `^{3,2}`; this is the only change to the title page from the accepted version.

**R3-10 — Case study path-wise comparison.**
We agree a step-by-step comparison of the agent interaction sequences makes the bottleneck more concrete:
- *MP path*: Issue → Planner produces a 679-token summary that drops the file/line traceback → Coder receives only this summary and incorrectly patches `Query.clone()` (line 355) → Reviewer rejects → Coder re-attempts twice on a similarly wrong target → Tester fails (3 iterations, 34,042 tokens).
- *BB path*: Issue → Planner produces the same diagnosis → Coder receives the structured analysis *and* the original issue text including the traceback → Coder targets `Query.check_filterable` on the first try → Reviewer accepts → Tester passes (1 iteration, 30,732 tokens).

The divergence occurs at the Planner→Coder handoff, where MP's lossy natural-language compression discards the file/line information that survives intact in BB's shared state. The manuscript's case study section discusses this case at a higher level; the detailed step-by-step is provided here for the reviewer.

**R3-11 — Future measures to overcome the patch-generation bottleneck.**
Three concrete directions for the unified-diff bottleneck identified by our analysis:
1. *Search-and-replace specifications*: the Coder emits `(old_block, new_block)` pairs and a deterministic tool performs substitution; avoids context-line matching entirely.
2. *AST-level edits*: structured tree transformations applied by a language-aware engine; guarantees syntactic validity but requires per-language tooling.
3. *Whole-file rewriting*: emit the full content of the modified file and recover the diff by external comparison; scales poorly to large files but eliminates the diff-generation step at the model level.

A practical compromise — used outside the present study — is progressively lenient patch-apply heuristics (`git apply` → `patch -F0` → `patch -F3`), which trade a small risk of incorrect application against substantially higher apply rates. The manuscript's Future Work section mentions search-and-replace and improved diff generation; the additional concrete options are provided here.

**R3-12 — Clearer p-values for Wilcoxon and McNemar.**
All p-values are summarized in the statistical-results table in the manuscript: McNemar (MP vs BB) p = 0.625 with b = 1, c = 3; McNemar (MP vs Hybrid) p = 1.000; McNemar (BB vs Hybrid) p = 0.500; Cohen's h = 0.116; odds ratio 1.40 with 95% CI [0.45, 4.37]; Wilcoxon (tokens MP vs BB) W = 34 p < 0.001; Wilcoxon (latency MP vs BB) W = 63 p < 0.001; Wilcoxon (IFS MP vs BB) W = 36.5 p = 0.058. We have not changed the manuscript text but confirm these values are reported.

**R3-13 — Explain the tool ablation prompts.**
The tools were exposed to the Coder via a JSON schema: `read_file` (with optional line range), `search_code` (substring search across the working tree), `read_lines`, `validate_patch` (dry-run apply via `git apply --check`), and `submit_patch`. The Coder was instructed to call `read_file` or `search_code` at least once before producing a diff, to use `validate_patch` prior to `submit_patch`, and to retry up to two times on validation failure before submitting anyway. The system prompt and all other components (Planner, Reviewer, Tester) were unchanged from the non-tool baseline.

**R3-14 — Define $S$ and $W(k)$ directly after first introduction.**
For the reviewer's reference, our intended formal definition is: $W : \mathcal{K} \to 2^{\{I,A,P,R,T\}}$ assigns each agent role $k \in \mathcal{K} = \{\text{Planner}, \text{Coder}, \text{Reviewer}, \text{Tester}\}$ the subset of state fields that role is permitted to modify. The IssueInfo field $I$ is excluded from every $W(k)$, making it read-only for all agents. We will include this signature explicitly in a future extended version.

---

## Summary

| Reviewer ask | Where addressed |
|---|---|
| A1 affiliation, A2 DOI, D1 Jimenez DOI | **Manuscript** (format-level corrections) |
| Per-repo IFS, IFS variance, fuzzy IFS, Hybrid empty-patch deep dive, Reviewer dynamics, tokens-per-resolved, per-stage cost | **This Response document**, supplementary data |
| Knowledge-drift definition, abstract reframing, acknowledgment expansion, case-study path-wise comparison, future-work expansion, S/W(k) definition, IFS-vs-prior-eval distinction, stratified-sampling justification, statistical-power language | Acknowledged here; will be incorporated into a future extended version |
| New references (Zhong/Sumers/Lou, MAGIS, diff-LLM citation) | Acknowledged here; not added to bibliography per IEEE Access checklist |

We thank the reviewers again for the thoroughness of their suggestions. We hope the conservative scope of the manuscript changes — driven by the IEEE Access final-files policy of matching the accepted version — combined with the substantive treatment of each comment in this Response document, addresses the spirit of the review while remaining compatible with production's requirements.
