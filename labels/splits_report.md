# Split report

- val days: 20260605, 20260606
- test days: 20260607, 20260615
- eval_newdays: 413 ROIs, one per distinct object, on 17 unlabeled days. Every repeat capture of those objects, and the 10 s (1 s on burst days) block around each, is eval_reserved.

| split | ROIs | labeled | organism | ring | marine_snow | blurry | needs_box |
|---|---|---|---|---|---|---|---|
| train | 24,795 | 2,221 | 916 | 506 | 642 | 146 | 258 |
| val | 451 | 386 | 164 | 55 | 141 | 25 | 43 |
| test | 455 | 455 | 194 | 116 | 106 | 34 | 58 |
| eval_newdays | 413 | 69 | 8 | 17 | 3 | 29 | 1 |
| eval_reserved | 5,418 | 26 | 1 | 0 | 0 | 0 | 0 |

## eval_newdays sample by day

| day | ROIs on day | distinct objects | sampled |
|---|---|---|---|
| 20260515 | 155 | 155 | 5 |
| 20260516 | 698 | 696 | 21 |
| 20260517 | 2,059 | 2,027 | 61 |
| 20260521 | 7,125 | 33 | 12 |
| 20260522 | 2,609 | 2,598 | 78 |
| 20260524 | 244 | 244 | 7 |
| 20260525 | 792 | 791 | 24 |
| 20260528 | 2,909 | 2,886 | 87 |
| 20260529 | 619 | 619 | 19 |
| 20260602 | 1,653 | 1,652 | 50 |
| 20260603 | 240 | 240 | 7 |
| 20260604 | 96 | 96 | 4 |
| 20260608 | 120 | 118 | 4 |
| 20260609 | 333 | 332 | 10 |
| 20260610 | 312 | 312 | 9 |
| 20260611 | 307 | 307 | 9 |
| 20260612 | 205 | 205 | 6 |
