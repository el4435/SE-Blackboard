# B4: Reviewer Accept/Reject Dynamics

## Iteration distribution (terminates on first accept or max=3)
| Config | N | Mean iters | iters=1 | iters=2 | iters=3 |
|---|---:|---:|---:|---:|---:|
| MP | 50 | 2.78 | 5 | 1 | 44 |
| BB | 50 | 2.7 | 7 | 1 | 42 |
| Hybrid | 50 | 2.8 | 5 | 0 | 45 |

## Explicit Reviewer verdicts (BB and Hybrid only)
| Config | Runs w/ verdicts | Accepts | Rejects | First-accept @1 | @2 | @3 | Never |
|---|---:|---:|---:|---:|---:|---:|---:|
| MP | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BB | 50 | 55 | 80 | 21 | 4 | 8 | 17 |
| Hybrid | 50 | 37 | 103 | 13 | 5 | 3 | 29 |