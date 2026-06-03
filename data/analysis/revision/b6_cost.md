# B6: Cost-Efficiency Detailed Analysis

## Summary by configuration
| Config | N | Resolved | Tokens/run | Tokens/resolved | Lat/run (s) |
|---|---:|---:|---:|---:|---:|
| MP | 50 | 6 | 25,317 | 210,973 | 106.5 |
| BB | 50 | 8 | 54,849 | 342,807 | 170.6 |
| Hybrid | 50 | 6 | 43,278 | 360,651 | 128.2 |

## Per-stage token consumption (mean per run)
| Config | Planner | Coder | Reviewer | Tester |
|---|---:|---:|---:|---:|
| MP | 1,513 | 19,746 | 3,456 | 601 |
| BB | 4,428 | 18,895 | 28,168 | 3,359 |
| Hybrid | 3,944 | 17,151 | 19,306 | 2,877 |

## Resolved vs unresolved cost
| Config | Resolved-run tokens | Unresolved-run tokens |
|---|---:|---:|
| MP | 13,374 | 26,945 |
| BB | 29,169 | 59,741 |
| Hybrid | 31,776 | 44,847 |