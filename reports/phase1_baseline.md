# Phase 1 baseline: logistic regression on frozen embeddings

Run 2026-09-28 21:57. Train 2,219 objects (organism 915, marine_snow 642, ring 506, blurry 145, artifact 11). Val 386, test 455, eval_newdays 413 objects.

Organism threshold set on val for 95% organism recall, then applied unchanged. 'Noise removed' = share of non-organisms below the threshold (what annotators no longer see). eval_newdays was labeled by a different annotator than the training data.

| features | C | val macro-F1 | test macro-F1 | newdays macro-F1 | test org. recall | test org. precision | test noise removed | newdays org. recall (95% CI) | newdays org. precision | newdays noise removed |
|---|---|---|---|---|---|---|---|---|---|---|
| dinov2 | 0.01 | 0.57 | 0.64 | 0.47 | 0.93 | 0.71 | 72% | 0.93 (0.77-0.98, n=28) | 0.14 | 60% |
| bioclip | 0.01 | 0.51 | 0.58 | 0.43 | 0.94 | 0.57 | 47% | 1.00 (0.88-1.00, n=28) | 0.11 | 38% |
| dinov2+bioclip | 0.01 | 0.57 | 0.65 | 0.46 | 0.93 | 0.72 | 73% | 0.93 (0.77-0.98, n=28) | 0.14 | 59% |
| size | 1.0 | 0.22 | 0.24 | 0.24 | 0.94 | 0.43 | 8% | 0.96 (0.82-0.99, n=28) | 0.07 | 8% |

## dinov2

C = 0.01; organism threshold 0.122.

test confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 157 | 19 | 3 | 11 | 4 |
| marine_snow | 7 | 86 | 0 | 13 | 0 |
| ring | 1 | 2 | 105 | 4 | 4 |
| blurry | 8 | 4 | 1 | 17 | 4 |
| artifact | 1 | 0 | 2 | 0 | 2 |

eval_newdays confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 26 | 0 | 1 | 1 | 0 |
| marine_snow | 15 | 33 | 0 | 2 | 0 |
| ring | 1 | 0 | 113 | 2 | 0 |
| blurry | 49 | 60 | 4 | 57 | 13 |
| artifact | 13 | 1 | 17 | 1 | 4 |

## bioclip

C = 0.01; organism threshold 0.072.

test confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 128 | 31 | 7 | 25 | 3 |
| marine_snow | 15 | 84 | 0 | 7 | 0 |
| ring | 6 | 1 | 104 | 4 | 1 |
| blurry | 8 | 7 | 0 | 16 | 3 |
| artifact | 0 | 0 | 4 | 0 | 1 |

eval_newdays confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 25 | 0 | 2 | 1 | 0 |
| marine_snow | 13 | 37 | 0 | 0 | 0 |
| ring | 5 | 0 | 98 | 12 | 1 |
| blurry | 50 | 68 | 6 | 52 | 7 |
| artifact | 9 | 0 | 24 | 1 | 2 |

## dinov2+bioclip

C = 0.01; organism threshold 0.108.

test confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 156 | 18 | 2 | 12 | 6 |
| marine_snow | 6 | 89 | 0 | 11 | 0 |
| ring | 3 | 0 | 106 | 4 | 3 |
| blurry | 8 | 4 | 1 | 17 | 4 |
| artifact | 0 | 0 | 3 | 0 | 2 |

eval_newdays confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 26 | 0 | 1 | 1 | 0 |
| marine_snow | 13 | 35 | 0 | 2 | 0 |
| ring | 2 | 0 | 109 | 5 | 0 |
| blurry | 51 | 66 | 4 | 51 | 11 |
| artifact | 12 | 1 | 19 | 0 | 4 |

## size

C = 1.0; organism threshold 0.107.

test confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 39 | 53 | 31 | 44 | 27 |
| marine_snow | 23 | 18 | 6 | 36 | 23 |
| ring | 24 | 10 | 53 | 26 | 3 |
| blurry | 2 | 6 | 1 | 15 | 10 |
| artifact | 0 | 1 | 3 | 0 | 1 |

eval_newdays confusion (rows true, columns predicted):

| true \ pred | organism | marine_snow | ring | blurry | artifact |
|---|---|---|---|---|---|
| organism | 6 | 8 | 7 | 3 | 4 |
| marine_snow | 16 | 8 | 7 | 10 | 9 |
| ring | 24 | 11 | 48 | 30 | 3 |
| blurry | 28 | 51 | 5 | 70 | 29 |
| artifact | 1 | 2 | 32 | 0 | 1 |

