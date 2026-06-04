# Project Handoff — SE-Blackboard (IEEE Access Submission)

> **Status as of**: 2026-06-04 (final files submitted; awaiting IEEE administrator response on source-vs-accepted PDF table count discrepancy)
> **Maintainer**: Erxi Liu (el4435@nyu.edu)
> **Corresponding author**: Qiang Zhu (zhuqiang@nim.ac.cn)
> **Repository**: `el4435/SE-Blackboard` (**public**, on `master` branch)

---

## 1. One-sentence project description

Empirical study of how communication architecture (message passing vs. shared-state blackboard vs. hybrid) in multi-agent LLM pipelines affects information fidelity and end-task performance on 50 SWE-bench Lite issues, written up as an IEEE Access journal paper.

---

## 2. Submission status

| Item | Status |
|---|---|
| Manuscript ID | **Access-2026-10514** |
| DOI (assigned by IEEE) | **10.1109/ACCESS.2026.3695435** |
| Acceptance decision | ✅ Received (with reviewer comments for minor revision) |
| Open Access license | ✅ CC BY |
| Final files first submission | ⚠️ Submitted 17 May 2026 (past-due reminders received) |
| Source-vs-accepted PDF mismatch flagged by IEEE Publications | ⚠️ Open (see §6) |
| Clarification email sent to IEEE article administrator | ✅ Sent (to s.malo@ieee.org, Cc Qiang Zhu) — awaiting reply |

**Why "Past Due" appears on the portal**: not a real problem; IEEE Access soft deadlines are admin reminders, not hard cutoffs. Acceptance does not get revoked. Only consequence: publication date shifts by a few days.

---

## 3. The two-versions situation (critical to understand)

The repository contains snapshots of **two paper versions** under `versions/`:

| Folder | Pages | Tables | References | What it is |
|---|---:|---:|---:|---|
| `versions/8tables-accepted/` | 12 | 8 | 28 | Matches the structure IEEE Publications refers to as "the accepted PDF." Original accepted manuscript + three format-level fixes only (affiliation typography, placeholder DOI, DOI added to existing Jimenez entry). |
| `versions/10tables-revised/` | 15 | 10 | 32 | Reviewer-requested revisions incorporated (two new tables, three new sub-subsections, abstract reframing, expanded acknowledgment + case study + future work, four reviewer-named new references, full DOI completeness pass). This was uploaded to the Author Portal in May 2026. |

**The current "live" copy in `paper/ACCESS_latex_template_20240429/main.tex`** is the 8-table version (with A1+A2+D1 fixes). It was rolled back from the 10-table version on 2026-06-03 as a precaution; the 10-table tex/bib are preserved as `main_revised_keepforrecord.tex` and `references_revised_keepforrecord.bib` in the same directory.

**Which version gets resubmitted depends on Sridam Malo's reply** (see §6).

---

## 4. The IEEE Publications discrepancy notice

IEEE Publications notified the authors on 2026-05-19 that the accepted PDF on file has 8 tables but the source file submitted has 10 tables (with text differences as well). The corresponding author (Qiang Zhu) was the initial addressee; a "Dear Authors" reminder was forwarded to all authors on 2026-06-03.

**Hypothesis of cause**: the May 2026 final-files upload accidentally paired an *old* PDF (the 8-table version from the initial submission, which is what IEEE has on file as "accepted") with the *new* 10-table source — i.e., a mismatch between the submitted PDF and source rather than a violation of revision policy. The downloaded current portal files are consistent (both 10 tables), suggesting the original upload was actually the 10-table pair; IEEE's "8 tables" refers to a different document stored from the acceptance stage.

**Clarification email sent on 2026-06-04** (drafted by Erxi Liu, awaiting reply from Sridam Malo) asks:

1. Whether "the accepted version" means the pre-revision manuscript or the post-revision manuscript.
2. Whether the reviewer-requested changes were incorporated incorrectly (in scope or in principle).
3. How to view the "accepted version" IEEE has on file.

**Two corrected file bundles are pre-built and ready to send**, depending on the reply:

- **(a)** `versions/8tables-accepted/` — matching the accepted-PDF structure
- **(b)** `versions/10tables-revised/` — matching what is currently in the portal

---

## 5. Reviewer-comment outcome map

The reviewer comments came with the acceptance decision. In the 10-table revised version each comment was addressed in the paper; in the 8-table version most are addressed only via the Response-to-Reviewers document (`paper/Response_to_Reviewers.md`, also a `.docx` version).

| Comment ID | Source | What it asks for | Where addressed |
|---|---|---|---|
| A1 | R1#1 / R3#9 | Fix "32" affiliation superscript | ✅ Both versions (typography only) |
| A2 | R1#2 | Clear placeholder DOI | ✅ Both versions |
| D1 | R1#4 | DOI on Jimenez SWE-bench entry | ✅ Both versions (format only) |
| B1 | R1#3 | Planner-stage IFS for MP | ✅ 10-table (Table 4 footnote + value); Response only in 8-table |
| B2 | R1-gap-1, R2-major-1 | Per-repository IFS breakdown | ✅ 10-table (Table 5); Response only in 8-table |
| B3 | R1-gap-2, R2-major-3 | Hybrid empty-patch deep dive | ✅ 10-table (§V-C paragraph); Response only in 8-table |
| B4 | R1-gap-3, R2-comp-1 | Reviewer accept/reject dynamics | ✅ 10-table (§V-D-3); Response only in 8-table |
| B5 | R3#5 | IFS variance per configuration | ✅ 10-table (Table 4 with ±std); Response only in 8-table |
| B6 | R3#7, R2-cost | Cost-efficiency / tokens-per-resolved | ✅ 10-table (Table 9 + §V-F rewrite); Response only in 8-table |
| B7 | R1-concern-4 | Tool-ablation 10-issue caveat | ✅ 10-table (one sentence); Response only in 8-table |
| B8 | R2-major-2 | IFS fuzzy-matching robustness | ✅ 10-table (§V-B-5); Response only in 8-table |
| C-series (C1..C15) | R3 + others | Knowledge-drift definition, abstract reframing, ack expansion, case study path-wise, future work expansion, S/W(k) definitions, etc. | ✅ 10-table; Response only in 8-table |
| D2/D3/D4 | R1#4, R2-ref-2 | Add Zhong, Sumers, Lou, Tao MAGIS references | ✅ 10-table (4 new bib entries + cites); acknowledged in Response only in 8-table |

The Response document (`paper/Response_to_Reviewers.md` and `.docx`) currently corresponds to the **8-table** scenario (treats every substantive ask as "addressed in this Response" rather than in the manuscript). If IEEE clarifies that the 10-table version is acceptable, the Response should be **switched back to the 10-table Response** preserved in git history (commit `52e2eed`, before the 2026-06-03 rollback).

---

## 6. Open action items

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Await Sridam Malo's reply on which paper version is the "accepted version" | Sridam → Erxi/Qiang | ⏳ Open |
| 2 | Once reply received, resubmit the matching file set (a) or (b) via reply to IEEE Publications | Qiang Zhu (corresponding author) | ⏳ Blocked on #1 |
| 3 | If 10-table version is accepted: restore Response_to_Reviewers to the 10-table version from git commit `52e2eed` | Erxi | ⏳ Blocked on #1 |
| 4 | If 8-table version is required: keep current Response (8-table framing); resubmit `versions/8tables-accepted/` | Erxi / Qiang | ⏳ Blocked on #1 |
| 5 | Pay APC (separate workflow via Copyright Clearance Center) | Qiang Zhu (Primary Author / billing) | ⏳ Awaiting CCC email |
| 6 | Rotate Anthropic API key (the local `.env` had a real key; never reached GitHub but exposed locally) | Erxi | Optional / not urgent |

---

## 7. Key file locations

```
SE-Blackboard/
├── HANDOFF.md                          ← this document
├── README.md
├── pyproject.toml
├── .env.example                        ← placeholder; real key is in local .env (gitignored)
├── .gitignore
│
├── versions/
│   ├── README.md                       ← explains the two snapshots
│   ├── 8tables-accepted/               ← matches IEEE's "accepted PDF" structure
│   │   ├── main.tex                    (55 KB, 593 lines)
│   │   ├── references.bib              (8 KB, 229 lines, 28 entries)
│   │   └── FINAL Article.pdf           (12 pages, 2.3 MB)
│   └── 10tables-revised/               ← reviewer-requested revisions incorporated
│       ├── main.tex                    (73 KB)
│       ├── references.bib              (11 KB, 32 entries)
│       └── FINAL Article.pdf           (15 pages, 2.4 MB)
│
├── paper/                              ← active manuscript working directory
│   ├── ACCESS_latex_template_20240429/
│   │   ├── main.tex                    ← currently 8-table (after 2026-06-03 rollback)
│   │   ├── references.bib              ← currently 8-table state + Jimenez DOI
│   │   ├── main_original.tex           ← pure accepted version backup
│   │   ├── references_original.bib     ← pure accepted bib backup
│   │   ├── main_revised_keepforrecord.tex      ← 10-table version preserved
│   │   ├── references_revised_keepforrecord.bib← 10-table bib preserved
│   │   ├── ieeeaccess.cls / IEEEtran.cls / IEEEtran.bst / spotcolor.sty
│   │   ├── author_liu.jpg / author_zhu.png / author_dong.jpg
│   │   ├── figures/                    (fig1..fig5 PNGs)
│   │   └── t1-*.pfb / .tfm / .fd / .map (Formata/Times/Giovannistd font files)
│   ├── FINAL Article.pdf               ← currently 8-table 12pp
│   ├── GA.jpg                          ← Graphical Abstract (660×295, 19.8 KB)
│   ├── GA_caption.docx                 ← GA caption (54 words; from fig4 bottleneck model)
│   ├── Response_to_Reviewers.md        ← currently 8-table framing
│   ├── Response_to_Reviewers.docx
│   ├── SE_Blackboard_FINAL.zip         ← packaged final-files submission (currently 8-table)
│   └── references.bib                  ← STALE, ignore (not used by main.tex)
│
├── src/                                ← framework code
│   ├── agents/                         (planner, coder, reviewer, tester, coder_tools)
│   ├── blackboard/                     (shared-state schema, Pydantic models)
│   ├── communication/                  (mp / blackboard / hybrid context functions)
│   ├── topologies/                     (sequential, debate pipelines)
│   ├── evaluation/                     (metrics, IFS, statistical tests, swebench runner)
│   └── utils/                          (logger, llm_client)
│
├── experiments/
│   ├── run_experiment.py               ← main entry to run a full config
│   ├── compute_ifs.py                  ← IFS computation pipeline
│   ├── statistical_tests.py            ← McNemar, Wilcoxon, Cohen's h
│   ├── generate_fig{2,3,4,5}*.py       ← regenerate paper figures
│   ├── analyze_*.py                    ← per-day-iteration analysis scripts
│   ├── revision_analyses/              ← new for paper revision
│   │   ├── b2_per_repo_ifs.py          ← R1-gap-1 / R2-major-1 analysis
│   │   ├── b3_hybrid_empty_patch.py    ← R1-gap-2 / R2-major-3 / R3#6
│   │   ├── b4_reviewer_dynamics.py     ← R1-gap-3 / R2-comp-1
│   │   ├── b5_ifs_variance.py          ← R3#5
│   │   ├── b6_cost_per_resolved.py     ← R2-cost / R3#7
│   │   ├── b8_fuzzy_ifs.py             ← R2-major-2
│   │   ├── make_graphical_abstract.py  ← GA + caption docx
│   │   ├── md_to_docx.py               ← Response_to_Reviewers.md → .docx
│   │   ├── build_final_zip.py          ← packaging script
│   │   └── check_abstract.py           ← word-count sanity check
│   ├── select_issues.py                ← original 50-issue stratified sample
│   └── build_all_env_images.py
│
├── config/
│   ├── settings.py
│   └── prompts/                        (planner.txt, coder.txt, reviewer.txt, tester.txt, …)
│
├── tests/                              (63 unit tests, all passing)
│
├── data/
│   ├── selected_issues.json            ← 50 chosen SWE-bench Lite issues
│   ├── results/                        ← per-config × per-issue JSON outputs (used by analyses)
│   │   ├── sequential_message_passing/ (50 JSONs)
│   │   ├── sequential_blackboard/      (50)
│   │   ├── sequential_hybrid/          (50)
│   │   ├── debate_*/                   (debate-pipeline results, supplementary)
│   │   └── sequential_*_phase1_*       (whole-file-rewrite / fallback-apply experiments)
│   ├── ifs/                            ← computed IFS values (entities + per-issue per-stage)
│   ├── analysis/
│   │   ├── revision/                   ← outputs of B2/B3/B4/B5/B6/B8 scripts
│   │   ├── failure_analysis.json
│   │   ├── statistical_tests.json
│   │   └── *_report.txt
│   └── logs/                           ← *_experiment.jsonl per-call telemetry (no text bodies)
│
└── feedback/                           ← GITIGNORED (reviewer comments, checklist)
    ├── reviewers comment.txt
    └── _ Final-Files-Checklist.docx
```

**Gitignored** (not on GitHub): `.env` (real Anthropic key), `data/workspaces/` (143 MB of cloned target repos), `feedback/` (private reviewer correspondence), `Day 1/`–`Day 10/` (early dev prompt logs), `SE-Blackboard-Code/` and `SE-Blackboard-Data/` (earlier duplicate snapshots), all `*_backup_*` directories, LaTeX build artifacts (`*.aux`/`.log`/`.bbl`/.../etc.), `.claude/`, pre-revision zip backups in `paper/`.

---

## 8. Important context (do not forget)

### 8.1 IEEE Access policy on "minor revision before final files"

- Checklist statement: *"Carefully review all comments from the Editor and reviewers to ensure that you make the necessary minor changes to your manuscript before submitting final files."* — implicitly authorizes incorporating reviewer-requested changes.
- Checklist statement: *"You are not permitted to add or remove authors or references post-acceptance."* — the only **explicit** hard prohibition. **The four new references we added (Zhong / Sumers / Lou / Tao MAGIS) are the one area that unambiguously violates the checklist**, even though reviewers explicitly asked for them.
- The "minor changes" boundary between what is OK and what is not is genuinely ambiguous; Sridam Malo's reply will define it.

### 8.2 Why the 10-table version was submitted

Reviewer comments came **with** the acceptance email. The natural reading of the checklist is that authors should "incorporate the reviewers' minor-revision asks before submitting final files." The 10-table version implements that interpretation. It is plausible IEEE will accept this; it is also plausible IEEE will require the 8-table version. Both are pre-built.

### 8.3 Author / contact information

| Role | Person | Email |
|---|---|---|
| First author / maintainer | Erxi Liu | el4435@nyu.edu |
| Corresponding author / PI | Qiang Zhu | zhuqiang@nim.ac.cn |
| Third author | Xinru Dong | 18339301370@163.com |
| IEEE article administrator | Sridam Malo | s.malo@ieee.org |

### 8.4 Sensitive content

- `paper/Response_to_Reviewers.md` includes the reviewers' comments paraphrased. The full reviewer report (`feedback/reviewers comment.txt`) is **gitignored** and must not be made public.
- `.env` contains the real Anthropic API key. Never committed to git. Should be rotated.

---

## 9. How to re-run / re-compile

### Compile a paper version

```bash
cd paper/ACCESS_latex_template_20240429
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Requires MiKTeX (Windows) or TeX Live. On Windows: `winget install MiKTeX.MiKTeX --scope user --silent --accept-source-agreements --accept-package-agreements`.

To switch between versions:

```bash
# To 10-table revised state
cp main_revised_keepforrecord.tex main.tex
cp references_revised_keepforrecord.bib references.bib

# Back to 8-table accepted-structure state
cp main_original.tex main.tex
cp references_original.bib references.bib
# then re-apply A1, A2 in main.tex and D1 (Jimenez DOI) in references.bib
```

### Re-run the paper-revision analyses (B2 / B3 / B4 / B5 / B6 / B8)

```bash
python experiments/revision_analyses/b2_per_repo_ifs.py
python experiments/revision_analyses/b3_hybrid_empty_patch.py
python experiments/revision_analyses/b4_reviewer_dynamics.py
python experiments/revision_analyses/b5_ifs_variance.py
python experiments/revision_analyses/b6_cost_per_resolved.py
python experiments/revision_analyses/b8_fuzzy_ifs.py
```

Outputs land in `data/analysis/revision/{*.json, *.md}`. All scripts are pure post-processing of `data/results/*` — no experiments are re-run, no LLM calls made.

### Re-build the submission ZIP

```bash
python experiments/revision_analyses/build_final_zip.py
```

Produces `paper/SE_Blackboard_FINAL.zip` containing the current `paper/FINAL Article.pdf`, `main.tex`, `references.bib`, cls/sty/fonts/figures, GA + caption, and Response documents.

### Regenerate the Graphical Abstract

```bash
python experiments/revision_analyses/make_graphical_abstract.py
```

Source: `paper/ACCESS_latex_template_20240429/figures/fig4_bottleneck_model.png` → `paper/GA.jpg` (660×295, ≤45 KB JPEG) + `paper/GA_caption.docx` (54-word caption).

### Run the full experiment pipeline (only needed for fresh evaluation; ~6 hours and ~$50 of API cost for 50 issues × 3 configs)

```bash
python experiments/run_experiment.py --topology sequential --comm message_passing
python experiments/run_experiment.py --topology sequential --comm blackboard
python experiments/run_experiment.py --topology sequential --comm hybrid
```

Requires: a valid Anthropic API key in `.env`, Docker (for SWE-bench harness), `data/workspaces/` populated with the target repos (run `experiments/build_all_env_images.py` first), and SWE-bench Lite gold patches accessible.

---

## 10. Things to be careful about

### 10.1 Do not let `.env` slip into git

The repository's `.gitignore` excludes `.env` and `.env.example` exists only as a placeholder. If you create a new `.env` from `.env.example`, do not commit it. The `.env.example` placeholder must never be replaced with a real key.

### 10.2 Do not delete `versions/`

After 2026-06-04 the canonical "what was submitted" snapshots live under `versions/`. The live `paper/ACCESS_latex_template_20240429/main.tex` may diverge from either snapshot as the submission is iterated.

### 10.3 Do not modify Response_to_Reviewers without noting which version

The Response document is tightly coupled to the manuscript version. Current Response = 8-table framing. If 10-table version is reinstated, restore Response from git commit `52e2eed`.

### 10.4 Do not push the data/workspaces/ folder

It contains full clones of django/sympy/etc. (~143 MB). Already gitignored.

### 10.5 Do not change author order or affiliations

Per IEEE Access checklist, post-acceptance author changes are not permitted.

---

## 11. Git remote and branches

```
remote:  git@github.com:el4435/SE-Blackboard.git
branch:  master
```

Commit history (latest first):
- `52e2eed` Paper revision (May 2026): IEEE Access final files + reviewer-response analyses
- `062b620` Add .gitignore and remove egg-info build artifact
- `d3381f5` Initial release: SE-Blackboard multi-agent code repair framework

The 2026-06-04 rollback (8-table state) and the `versions/` snapshots are in the next commit (the one created together with this `HANDOFF.md`).

---

*Last updated: 2026-06-04 by Erxi Liu (with Claude assistance).*
