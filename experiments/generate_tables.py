"""Day 6 — Generate LaTeX tables for SE-Blackboard paper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_ROOT = PROJECT_ROOT / "data"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"
TABLES_DIR.mkdir(parents=True, exist_ok=True)


def save(name: str, content: str):
    (TABLES_DIR / name).write_text(content, encoding="utf-8")
    print(f"  {name}")


# ── Load data ────────────────────────────────────────────────────────

stats = json.loads((DATA_ROOT / "analysis" / "statistical_tests.json").read_text(encoding="utf-8"))
ifs_summary = json.loads((DATA_ROOT / "ifs" / "ifs_summary_real.json").read_text(encoding="utf-8"))
failure = json.loads((DATA_ROOT / "analysis" / "failure_analysis.json").read_text(encoding="utf-8"))


# ── Table 1: Main Results ────────────────────────────────────────────

table1 = r"""\begin{table}[t]
\centering
\caption{Main experimental results on SWE-bench Lite (N=50 issues, Sequential pipeline).}
\label{tab:main-results}
\begin{tabular}{lccccc}
\toprule
\textbf{Communication} & \textbf{Resolved} & \textbf{Rate} & \textbf{Avg Tokens} & \textbf{Avg Latency} & \textbf{Avg Iter.} \\
\midrule
Message Passing & 6/50 & 12.0\% & 25,316 & 106s & 2.78 \\
Blackboard      & 8/50 & \textbf{16.0\%} & 54,849 & 171s & 2.70 \\
Hybrid          & 6/50 & 12.0\% & 43,278 & 128s & 2.80 \\
\bottomrule
\end{tabular}
\end{table}"""

save("table1_main_results.tex", table1)


# ── Table 2: Difficulty Breakdown ────────────────────────────────────

table2 = r"""\begin{table}[t]
\centering
\caption{Resolve rate by difficulty level (grouped by repository).}
\label{tab:difficulty}
\begin{tabular}{lcccccc}
\toprule
 & \multicolumn{2}{c}{\textbf{Easy (Django)}} & \multicolumn{2}{c}{\textbf{Medium}} & \multicolumn{2}{c}{\textbf{Hard}} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5} \cmidrule(lr){6-7}
\textbf{Comm.} & Resolved & Rate & Resolved & Rate & Resolved & Rate \\
\midrule
Message Passing & 4/22 & 18.2\% & 1/5 & 20.0\% & 1/23 & 4.3\% \\
Blackboard      & 7/22 & \textbf{31.8\%} & 1/5 & 20.0\% & 0/23 & 0.0\% \\
Hybrid          & 5/22 & 22.7\% & 1/5 & 20.0\% & 0/23 & 0.0\% \\
\bottomrule
\end{tabular}
\end{table}"""

save("table2_difficulty.tex", table2)


# ── Table 3: IFS by Stage ───────────────────────────────────────────

si = ifs_summary["stage_average_ifs"]


def fmt_ifs(val):
    if isinstance(val, (int, float)):
        return f"{val:.3f}"
    return "---"


table3 = r"""\begin{table}[t]
\centering
\caption{Information Fidelity Score (IFS) by pipeline stage.}
\label{tab:ifs}
\begin{tabular}{lcccc}
\toprule
\textbf{Communication} & \textbf{Planner} & \textbf{Coder} & \textbf{Reviewer} & \textbf{Tester} \\
\midrule
Message Passing & """ + fmt_ifs(si["Seq-MP"]["Planner"]) + " & " + fmt_ifs(si["Seq-MP"]["Coder"]) + " & " + fmt_ifs(si["Seq-MP"]["Reviewer"]) + " & " + fmt_ifs(si["Seq-MP"]["Tester"]) + r""" \\
Blackboard      & """ + fmt_ifs(si["Seq-BB"]["Planner"]) + " & " + fmt_ifs(si["Seq-BB"]["Coder"]) + " & " + fmt_ifs(si["Seq-BB"]["Reviewer"]) + " & " + fmt_ifs(si["Seq-BB"]["Tester"]) + r""" \\
Hybrid          & """ + fmt_ifs(si["Seq-Hybrid"]["Planner"]) + " & " + fmt_ifs(si["Seq-Hybrid"]["Coder"]) + " & " + fmt_ifs(si["Seq-Hybrid"]["Reviewer"]) + " & " + fmt_ifs(si["Seq-Hybrid"]["Tester"]) + r""" \\
\bottomrule
\end{tabular}
\end{table}"""

save("table3_ifs.tex", table3)


# ── Table 4: Statistical Tests ───────────────────────────────────────

mc = stats["mcnemar"]
ch = stats["cohens_h"]
od = stats["odds_ratio"]
wt = stats["wilcoxon"]
ifs_c = stats["ifs_comparison"]

table4 = r"""\begin{table}[t]
\centering
\caption{Statistical test results. Significance at $\alpha=0.05$ marked with *.}
\label{tab:statistics}
\begin{tabular}{llrl}
\toprule
\textbf{Test} & \textbf{Comparison} & \textbf{Statistic} & \textbf{$p$-value} \\
\midrule
\multicolumn{4}{l}{\textit{Resolve Rate (McNemar's exact)}} \\
 & MP vs BB & $b$=""" + str(mc["MP vs BB"]["b"]) + ", $c$=" + str(mc["MP vs BB"]["c"]) + " & $p=" + f'{mc["MP vs BB"]["p_value"]:.3f}' + r"""$ \\
 & MP vs Hybrid & $b=""" + str(mc["MP vs Hybrid"]["b"]) + ", $c$=" + str(mc["MP vs Hybrid"]["c"]) + " & $p=" + f'{mc["MP vs Hybrid"]["p_value"]:.3f}' + r"""$ \\
 & BB vs Hybrid & $b=""" + str(mc["BB vs Hybrid"]["b"]) + ", $c$=" + str(mc["BB vs Hybrid"]["c"]) + " & $p=" + f'{mc["BB vs Hybrid"]["p_value"]:.3f}' + r"""$ \\
\midrule
\multicolumn{4}{l}{\textit{Effect Size (Cohen's $h$)}} \\
 & BB vs MP & $h=""" + f'{ch["MP_vs_BB"]["h"]:.4f}' + r"""$ & """ + ch["MP_vs_BB"]["interpretation"] + r""" \\
\midrule
\multicolumn{4}{l}{\textit{Odds Ratio (BB vs MP)}} \\
 & BB vs MP & OR=""" + f'{od["BB_vs_MP"]["odds_ratio"]:.2f}' + r"""  & 95\%CI [""" + f'{od["BB_vs_MP"]["ci_95_lower"]:.2f}' + ", " + f'{od["BB_vs_MP"]["ci_95_upper"]:.2f}' + r"""] \\
\midrule
\multicolumn{4}{l}{\textit{Token Cost (Wilcoxon signed-rank)}} \\
 & MP vs BB & $W=""" + f'{wt["MP_vs_BB_tokens"]["statistic"]:.0f}' + r"""$ & $p<0.001$* \\
 & MP vs Hybrid & $W=""" + f'{wt["MP_vs_Hybrid_tokens"]["statistic"]:.0f}' + r"""$ & $p<0.001$* \\
\midrule
\multicolumn{4}{l}{\textit{IFS Coder Stage (Wilcoxon signed-rank)}} \\
 & MP vs BB & $W=""" + f'{ifs_c.get("MP_vs_BB_coder_ifs", {}).get("w_stat", 0):.0f}' + r"""$ & $p=""" + f'{ifs_c.get("MP_vs_BB_coder_ifs", {}).get("w_p", 1.0):.3f}' + r"""$ \\
\bottomrule
\end{tabular}
\end{table}"""

save("table4_statistics.tex", table4)


# ── Table 5: Failure Analysis ────────────────────────────────────────

fs = failure["summaries"]

table5 = r"""\begin{table}[t]
\centering
\caption{Failure mode distribution across communication architectures.}
\label{tab:failures}
\begin{tabular}{lccc}
\toprule
\textbf{Category} & \textbf{MP} & \textbf{BB} & \textbf{Hybrid} \\
\midrule
Resolved           & """ + str(fs["A-Seq(MP)"]["resolved"]) + " & " + str(fs["B-Seq(BB)"]["resolved"]) + " & " + str(fs["C-Seq(Hy)"]["resolved"]) + r""" \\
Empty Patch        & """ + str(fs["A-Seq(MP)"]["empty_patch"]) + " & " + str(fs["B-Seq(BB)"]["empty_patch"]) + " & " + str(fs["C-Seq(Hy)"]["empty_patch"]) + r""" \\
Patch Apply Error  & """ + str(fs["A-Seq(MP)"]["patch_apply_error"]) + " & " + str(fs["B-Seq(BB)"]["patch_apply_error"]) + " & " + str(fs["C-Seq(Hy)"]["patch_apply_error"]) + r""" \\
\midrule
Total              & 50 & 50 & 50 \\
\bottomrule
\end{tabular}
\end{table}"""

save("table5_failures.tex", table5)


print(f"\nAll tables saved to {TABLES_DIR}")
