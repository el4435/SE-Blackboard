import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent / 'data'
V3_DIRS = {
    'A-Seq MP':     BASE / 'results' / 'sequential_message_passing',
    'B-Seq BB':     BASE / 'results' / 'sequential_blackboard',
    'C-Seq Hybrid': BASE / 'results' / 'sequential_hybrid',
}
V2_DIRS = {
    'A-Seq MP':     BASE / 'results_real_v2_backup' / 'sequential_message_passing',
    'B-Seq BB':     BASE / 'results_real_v2_backup' / 'sequential_blackboard',
    'C-Seq Hybrid': BASE / 'results_real_v2_backup' / 'sequential_hybrid',
}
OUTPUT_PATH = BASE / 'results' / '_sequential_comparison_v3.json'

def load_results(directory):
    results = {}
    for f in sorted(directory.glob('*.json')):
        if f.name.startswith('_'):
            continue
        with open(f, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        issue_id = data.get('issue_id', f.stem)
        results[issue_id] = data
    return results

def config_stats(results):
    total = len(results)
    resolved_ids = sorted([iid for iid, r in results.items() if r.get('resolved')])
    failed_ids = sorted([iid for iid, r in results.items() if not r.get('resolved')])
    tokens_list, latency_list, iterations_list = [], [], []
    for r in results.values():
        tokens_list.append(r.get('total_input_tokens', 0) + r.get('total_output_tokens', 0))
        latency_list.append(r.get('total_latency_ms', 0) / 1000.0)
        iterations_list.append(r.get('iterations', 0))
    avg_tokens = sum(tokens_list) / total if total else 0
    avg_latency = sum(latency_list) / total if total else 0
    avg_iterations = sum(iterations_list) / total if total else 0
    median_tokens = sorted(tokens_list)[total // 2] if total else 0
    median_latency = sorted(latency_list)[total // 2] if total else 0
    return {
        'total': total, 'resolved': len(resolved_ids), 'failed': len(failed_ids),
        'resolve_rate': round(len(resolved_ids) / total * 100, 1) if total else 0,
        'avg_tokens': round(avg_tokens), 'median_tokens': round(median_tokens),
        'avg_latency_s': round(avg_latency, 1), 'median_latency_s': round(median_latency, 1),
        'avg_iterations': round(avg_iterations, 2),
        'resolved_issues': resolved_ids, 'failed_issues': failed_ids,
    }

def repo_breakdown(results):
    repos = defaultdict(lambda: {'resolved': 0, 'total': 0})
    for iid, r in results.items():
        repo = '__'.join(iid.split('__')[:2]) if '__' in iid else iid.rsplit('-', 1)[0]
        repos[repo]['total'] += 1
        if r.get('resolved'):
            repos[repo]['resolved'] += 1
    return {k: v for k, v in sorted(repos.items(), key=lambda x: -x[1]['total'])}

def main():
    v3_data, v3_stats = {}, {}
    for cfg, d in V3_DIRS.items():
        v3_data[cfg] = load_results(d)
        v3_stats[cfg] = config_stats(v3_data[cfg])

    v2_data, v2_stats = {}, {}
    for cfg, d in V2_DIRS.items():
        if d.exists():
            v2_data[cfg] = load_results(d)
            v2_stats[cfg] = config_stats(v2_data[cfg])

    all_issues = sorted(set().union(*(v3_data[c].keys() for c in v3_data)))
    per_issue = {}
    for iid in all_issues:
        entry = {}
        for cfg in V3_DIRS:
            r = v3_data[cfg].get(iid)
            if r:
                entry[cfg] = {
                    'resolved': r.get('resolved', False),
                    'tokens': r.get('total_input_tokens', 0) + r.get('total_output_tokens', 0),
                    'latency_s': round(r.get('total_latency_ms', 0) / 1000.0, 1),
                    'iterations': r.get('iterations', 0),
                }
        per_issue[iid] = entry

    resolved_sets = {cfg: set(v3_stats[cfg]['resolved_issues']) for cfg in V3_DIRS}
    all_resolved = set().union(*resolved_sets.values())
    by_all_3 = sorted(resolved_sets['A-Seq MP'] & resolved_sets['B-Seq BB'] & resolved_sets['C-Seq Hybrid'])

    by_exactly_2 = {}
    for a2, b2 in [('A-Seq MP','B-Seq BB'),('A-Seq MP','C-Seq Hybrid'),('B-Seq BB','C-Seq Hybrid')]:
        third = [c for c in V3_DIRS if c not in (a2, b2)][0]
        exactly = sorted((resolved_sets[a2] & resolved_sets[b2]) - resolved_sets[third])
        if exactly:
            by_exactly_2[f"{a2} + {b2}"] = exactly

    unique = {}
    for cfg in V3_DIRS:
        others = set().union(*(resolved_sets[c] for c in V3_DIRS if c != cfg))
        u = sorted(resolved_sets[cfg] - others)
        if u:
            unique[cfg] = u

    never_resolved = sorted(set(all_issues) - all_resolved)
    overlap = {
        'resolved_by_all_3': by_all_3,
        'resolved_by_exactly_2': by_exactly_2,
        'resolved_uniquely_by_1': unique,
        'never_resolved': never_resolved,
        'total_unique_resolved': len(all_resolved),
        'total_never_resolved': len(never_resolved),
    }

    v2_v3_delta = {}
    for cfg in V3_DIRS:
        if cfg in v2_stats:
            v3s, v2s = v3_stats[cfg], v2_stats[cfg]
            v3r = set(v3s['resolved_issues'])
            v2r = set(v2s['resolved_issues'])
            v2_v3_delta[cfg] = {
                'v2_resolved': v2s['resolved'], 'v3_resolved': v3s['resolved'],
                'delta_resolved': v3s['resolved'] - v2s['resolved'],
                'v2_resolve_rate': v2s['resolve_rate'], 'v3_resolve_rate': v3s['resolve_rate'],
                'delta_rate_pp': round(v3s['resolve_rate'] - v2s['resolve_rate'], 1),
                'v2_avg_tokens': v2s['avg_tokens'], 'v3_avg_tokens': v3s['avg_tokens'],
                'delta_avg_tokens': v3s['avg_tokens'] - v2s['avg_tokens'],
                'v2_avg_latency_s': v2s['avg_latency_s'], 'v3_avg_latency_s': v3s['avg_latency_s'],
                'delta_avg_latency_s': round(v3s['avg_latency_s'] - v2s['avg_latency_s'], 1),
                'new_in_v3': sorted(v3r - v2r),
                'lost_in_v3': sorted(v2r - v3r),
                'stable_resolved': sorted(v3r & v2r),
            }

    repo_stats = {cfg: repo_breakdown(v3_data[cfg]) for cfg in V3_DIRS}

    report = {
        'generated': datetime.now().isoformat(),
        'experiment': 'v3_sequential_comparison',
        'configs': {cfg: v3_stats[cfg] for cfg in V3_DIRS},
        'per_issue': per_issue,
        'overlap_analysis': overlap,
        'v2_vs_v3_delta': v2_v3_delta,
        'repo_breakdown': repo_stats,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"Report saved to {OUTPUT_PATH}")
    print()

    # -- Print summary
    SEP = '=' * 90
    DASH = '-' * 90
    print(SEP)
    print('  V3 SEQUENTIAL COMPARISON REPORT')
    print(SEP)
    hdr = "{:<16} {:>8} {:>7} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
        'Config', 'Resolved', 'Rate', 'AvgTok', 'MedTok', 'AvgLat', 'MedLat', 'AvgIter')
    print(hdr)
    print(DASH)
    for cfg in V3_DIRS:
        st = v3_stats[cfg]
        line = "{:<16} {:>3}/{:<4} {:>6.1f}% {:>8,} {:>8,} {:>7.1f}s {:>7.1f}s {:>7.2f}".format(
            cfg, st['resolved'], st['total'], st['resolve_rate'],
            st['avg_tokens'], st['median_tokens'],
            st['avg_latency_s'], st['median_latency_s'],
            st['avg_iterations'])
        print(line)
    print()

    print('--- Overlap Analysis ---')
    print('  Resolved by ALL 3 configs ({}):'.format(len(by_all_3)))
    for iid in by_all_3:
        print('    - {}'.format(iid))
    for pair, issues in by_exactly_2.items():
        print('  Resolved by exactly 2 ({}) ({}):'.format(pair, len(issues)))
        for iid in issues:
            print('    - {}'.format(iid))
    for cfg2, issues in unique.items():
        print('  Resolved UNIQUELY by {} ({}):'.format(cfg2, len(issues)))
        for iid in issues:
            print('    - {}'.format(iid))
    print('  Total unique resolved across all configs: {}'.format(len(all_resolved)))
    print('  Never resolved by any config: {}'.format(len(never_resolved)))
    print()

    if v2_v3_delta:
        print('--- V2 vs V3 Delta ---')
        hdr2 = "{:<16} {:>7} {:>7} {:>6} {:>8} {:>8} {:>6} {:>8} {:>8} {:>8}".format(
            'Config', 'v2 Res', 'v3 Res', 'Delta', 'v2 Rate', 'v3 Rate', 'dRate', 'v2 Tok', 'v3 Tok', 'dTok')
        print(hdr2)
        print('-' * 105)
        for cfg in V3_DIRS:
            if cfg in v2_v3_delta:
                d = v2_v3_delta[cfg]
                s1 = '+' if d['delta_resolved'] >= 0 else ''
                s2 = '+' if d['delta_rate_pp'] >= 0 else ''
                s3 = '+' if d['delta_avg_tokens'] >= 0 else ''
                line = "{:<16} {:>7} {:>7} {}{:>5} {:>7.1f}% {:>7.1f}% {}{:>5.1f} {:>8,} {:>8,} {}{:>7,}".format(
                    cfg, d['v2_resolved'], d['v3_resolved'],
                    s1, d['delta_resolved'],
                    d['v2_resolve_rate'], d['v3_resolve_rate'],
                    s2, d['delta_rate_pp'],
                    d['v2_avg_tokens'], d['v3_avg_tokens'],
                    s3, d['delta_avg_tokens'])
                print(line)
        print()
        for cfg in V3_DIRS:
            if cfg in v2_v3_delta:
                d = v2_v3_delta[cfg]
                if d['new_in_v3']:
                    print('  {} -- NEW in v3 ({}):'.format(cfg, len(d['new_in_v3'])))
                    for iid in d['new_in_v3']:
                        print('    + {}'.format(iid))
                if d['lost_in_v3']:
                    print('  {} -- LOST in v3 ({}):'.format(cfg, len(d['lost_in_v3'])))
                    for iid in d['lost_in_v3']:
                        print('    - {}'.format(iid))
                if d['stable_resolved']:
                    stb = ', '.join(d['stable_resolved'])
                    print('  {} -- Stable ({}): {}'.format(cfg, len(d['stable_resolved']), stb))
                print()

    print('--- Repo Breakdown (v3) ---')
    all_repos = sorted(set().union(*(repo_stats[c].keys() for c in V3_DIRS)))
    line = "{:<30}".format('Repository')
    for cfg in V3_DIRS:
        short = cfg.split('-')[-1].strip()
        line += " {:>12}".format(short)
    print(line)
    print('-' * (30 + 13 * len(V3_DIRS)))
    for repo in all_repos:
        line = "{:<30}".format(repo)
        for cfg in V3_DIRS:
            rs = repo_stats[cfg].get(repo, {'resolved': 0, 'total': 0})
            cell = "{}/{}".format(rs['resolved'], rs['total'])
            line += " {:>12}".format(cell)
        print(line)
    print()
    print(SEP)
    print('Done.')

if __name__ == "__main__":
    main()
