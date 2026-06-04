# Paper Versions Snapshot

Two snapshots of the IEEE Access manuscript "SE-Blackboard: A Shared-State Architecture for Multi-Agent Software Engineering Pipelines" (Access-2026-10514, DOI 10.1109/ACCESS.2026.3695435), kept for archival and submission-debugging purposes.

## `8tables-accepted/`

Matches the **structure** of the version IEEE has on file as "the accepted PDF" (the version referenced in IEEE Publications' source-files discrepancy notice as having 8 tables). It is the *original accepted manuscript* plus three small, strictly format-level corrections:

- **A1** — affiliation superscript on the third author rendered as `^{3,2}` rather than the unintended `^{32}` (typography fix; same intent as accepted version)
- **A2** — placeholder DOI `10.1109/ACCESS.2024.0429000` cleared to `\doi{}` so IEEE production fills the final DOI
- **D1** — DOI `10.48550/arXiv.2310.06770` added to the existing Jimenez et al. SWE-bench bibliography entry

No new tables, sections, references, or substantive text changes.

**Output**: 12 pages, 8 tables, 28 references.

## `10tables-revised/`

The version that incorporates the reviewer-requested revisions (the version that was actually uploaded to the IEEE Author Portal in May 2026). On top of the 8-table version it adds:

- **Two new tables** explicitly requested by reviewers:
  - **Table 5** — per-repository Coder-stage IFS and correct file targeting (R1-gap-1, R2-major-1)
  - **Table 9** — mean tokens consumed per agent role and per run (R2-cost, R3-7)
- **Table 4** augmented with `mean ± std` notation and a Planner-MP footnote
- **New subsections** addressing reviewer asks:
  - §V-B-4 Per-Repository Breakdown
  - §V-B-5 Robustness of IFS to Matcher Choice
  - §V-D-3 Reviewer Accept/Reject Dynamics
- **Abstract reframed** to lead with the diagnostic/methodological contribution (R2-minor-4)
- **Acknowledgment expanded** with specifics on Claude-assisted components (R2-minor-3)
- **Case study path-wise comparison** bullet list added to §V-G (R3-10)
- **Future Work** expanded with three concrete patch-representation candidates (R3-11)
- **Four new bibliography entries**, all reviewer-named:
  - Zhong et al. *MemoryBank* (R1#4)
  - Sumers et al. *Cognitive Architectures for Language Agents* (R1#4)
  - Lou et al. *Boosting Coverage-Based Fault Localization* (R1#4)
  - Tao et al. *MAGIS* (R2 reference gap)
- **DOI completeness pass** over existing entries (28/30 now carry DOIs)

**Output**: 15 pages, 10 tables, 32 references.

## Why both versions are kept

When the IEEE Access final-files package was submitted in May 2026, IEEE Publications flagged a discrepancy between the source manuscript file (10 tables) and what they have on file as the accepted PDF (8 tables). At the time of writing we are awaiting guidance from the article administrator on which version should be the basis for the final-files submission. Both versions are preserved here so that whichever way the resolution goes, the corresponding artifact can be uploaded immediately.

See `HANDOFF.md` at the repository root for the current submission status.
