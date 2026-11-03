# Calibration round: Jeremy vs Jordan

100 objects labeled by both. Target: class kappa ≥ 0.7. **Target not met.**

| measure | agreement | kappa |
|---|---|---|
| Class (5 classes) | 72% | 0.64 |
| Organism vs. not | 88% | 0.70 |
| Focus (sharp / blurry) | 87% | 0.48 |
| Needs box (objects both called organism, n=22) | 73% | 0.23 |
| Multiple | 90% | 0.00 |

## Class confusion (Jeremy rows, Jordan columns)

| | organism | marine_snow | ring | artifact | unidentifiable |
|---|---|---|---|---|---|
| organism | 22 | 0 | 1 | 2 | 1 |
| marine_snow | 6 | 25 | 0 | 0 | 3 |
| ring | 0 | 0 | 7 | 3 | 0 |
| artifact | 2 | 0 | 0 | 8 | 3 |
| unidentifiable | 0 | 3 | 0 | 4 | 10 |

## Agreement by sampling stratum

| stratum | objects | class agreement |
|---|---|---|
| artifact | 10 | 50% |
| blurry | 15 | 80% |
| marine_snow | 20 | 80% |
| organism | 30 | 73% |
| random | 10 | 80% |
| ring | 15 | 60% |

44 objects need adjudication: see adjudication.csv (fill agreed_class / agreed_focus / agreed_needs_box and the rule that settled it).
