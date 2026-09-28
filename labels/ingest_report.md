# Ingest report

- Annotation file: `V3_Annotations_full_ROI_list_20260729.xlsb.csv` (sha1 af2ade6070d1)
- ROI images found: 31,532 across 30 days
- Annotation rows: 31,532 (duplicate filenames dropped: 0)
- Labeled ROIs (triage set): 3,475 (11.0%)
- Manual corrections applied (`corrections.csv`): 2
- Unresolved conflicts (`conflicts.csv`): 0
- Eval-labeler labels applied (`eval_newdays_labels.csv`): 413
- Annotation rows with no image on disk: 0
- Images with no annotation row: 0
- Images with no ROICoord entry: 798 (duplicate ROICoord lines ignored: 0; malformed CTD strings: 52)
- ROICoord lines with an empty CTD string: 16,380 (CTD can be joined later from aux_00 by time)

## Fixes applied

- `Oganism -> organism`: 8
- Classification casing normalized (e.g. `Marine Snow` -> `marine_snow`)
- Notes containing 'camera part' (with Organism != 1) -> `artifact`

## Triage counts

| class | ROIs | needs_box=true | median width x height (px) |
|---|---|---|---|
| organism | 1,302 | 360 | 120 x 122 |
| marine_snow | 939 | 0 | 100 x 100 |
| ring | 793 | 0 | 284 x 268 |
| blurry | 388 | 0 | 88 x 78 |
| artifact | 50 | 0 | 424 x 504 |
| other | 3 | 0 | 176 x 128 |

## Labeled ROIs by day

| day | ROIs | labeled | organism | ring | marine_snow | blurry | artifact |
|---|---|---|---|---|---|---|---|
| 20260515 | 155 | 5 | 0 | 0 | 1 | 4 | 0 |
| 20260516 | 698 | 21 | 1 | 3 | 1 | 12 | 4 |
| 20260517 | 2,059 | 61 | 6 | 32 | 3 | 18 | 2 |
| 20260521 | 7,125 | 12 | 0 | 0 | 0 | 2 | 10 |
| 20260522 | 2,609 | 78 | 1 | 1 | 31 | 45 | 0 |
| 20260523 | 1,194 | 61 | 48 | 3 | 8 | 2 | 0 |
| 20260524 | 244 | 7 | 0 | 0 | 3 | 4 | 0 |
| 20260525 | 792 | 24 | 5 | 6 | 3 | 9 | 1 |
| 20260526 | 1,044 | 160 | 109 | 0 | 25 | 26 | 0 |
| 20260527 | 1,146 | 556 | 344 | 14 | 163 | 35 | 0 |
| 20260528 | 2,909 | 87 | 2 | 42 | 2 | 32 | 8 |
| 20260529 | 619 | 19 | 1 | 2 | 2 | 13 | 1 |
| 20260531 | 208 | 208 | 58 | 23 | 107 | 16 | 4 |
| 20260601 | 4,903 | 36 | 5 | 28 | 0 | 3 | 0 |
| 20260602 | 1,653 | 50 | 1 | 28 | 1 | 12 | 8 |
| 20260603 | 240 | 7 | 2 | 0 | 2 | 3 | 0 |
| 20260604 | 96 | 4 | 0 | 0 | 0 | 4 | 0 |
| 20260605 | 231 | 231 | 94 | 40 | 82 | 15 | 0 |
| 20260606 | 220 | 155 | 70 | 15 | 59 | 10 | 1 |
| 20260607 | 142 | 142 | 103 | 3 | 28 | 8 | 0 |
| 20260608 | 120 | 4 | 2 | 1 | 0 | 1 | 0 |
| 20260609 | 333 | 10 | 4 | 0 | 0 | 6 | 0 |
| 20260610 | 312 | 9 | 1 | 0 | 1 | 7 | 0 |
| 20260611 | 307 | 9 | 1 | 1 | 0 | 6 | 0 |
| 20260612 | 205 | 6 | 1 | 0 | 0 | 5 | 0 |
| 20260613 | 322 | 322 | 141 | 5 | 149 | 27 | 0 |
| 20260614 | 145 | 145 | 63 | 6 | 62 | 14 | 0 |
| 20260615 | 313 | 313 | 91 | 113 | 78 | 26 | 5 |
| 20260616 | 231 | 231 | 82 | 9 | 122 | 17 | 0 |
| 20260617 | 957 | 502 | 66 | 418 | 6 | 6 | 6 |

## Notes

- CTD column order in ROICoord is inferred from values: conductivity, pressure, temperature, **unknown (ctd_unk4, possibly a voltage)**, salinity, density, sound speed.
