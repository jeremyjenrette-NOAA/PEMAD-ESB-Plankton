# Preliminary class shares: jan2026

Run 2026-11-03 17:35. Model: dinov2 embeddings + logistic regression (Phase 1 baseline, C=0.01, trained on 2,219 labeled May-June 2026 objects; no January images were labeled). **Preliminary.**

- ROIs classified: 27,380; distinct objects: 27,344 (repeat captures averaged)
- Marine snow : organism (objects) = 26% : 12% (about 2.2 marine-snow particles per organism)
- Objects above the high-recall organism threshold (an upper bound on organisms): 9,009 (33%)

| class | share of objects (model) | share of ROIs (model) | objects, corrected for known model confusions (90% range) |
|---|---|---|---|
| Organism | 11.7% | 11.7% | 0.0% (0%-0%) |
| Marine snow | 25.7% | 25.6% | 0.0% (0%-0%) |
| Ring | 1.2% | 1.2% | 0.0% (0%-0%) |
| Blurry | 61.2% | 61.2% | 100.0% (100%-100%) |
| Artifact | 0.3% | 0.3% | 0.0% (0%-0%) |

The corrected column inverts the confusion matrix the model showed on the eval_newdays set (413 objects from unlabeled May-June days, labeled by Jeremy: organism 28, marine snow 50, ring 116, blurry 183, artifact 36). It assumes January confuses classes the way those days did, which is untested; read the two columns as a range, not a precise value.

## By day (objects)

| day | objects | Organism | Marine snow | Ring | Blurry | Artifact |
|---|---|---|---|---|---|---|
| 20260110 | 2,794 | 15% | 64% | 0% | 21% | 0% |
| 20260113 | 24,371 | 11% | 21% | 1% | 66% | 0% |
| 20260121 | 179 | 23% | 60% | 5% | 11% | 1% |

## Median ROI size by predicted class (pixels, objects)

| class | objects | median width | median height |
|---|---|---|---|
| Organism | 3,193 | 144 | 144 |
| Marine snow | 7,017 | 108 | 104 |
| Ring | 323 | 140 | 128 |
| Blurry | 16,740 | 84 | 76 |
| Artifact | 71 | 72 | 128 |

## Caveats for presenting

- Trained on late-spring (May-June) imagery; January water, particle types and organisms differ. No January ROI has been checked by a person yet.
- On new May-June days the baseline found 93% of organisms but only ~1 in 7 of its organism calls were organisms, so the raw organism share is likely an overestimate.
- The training labels pre-date the v1.0 annotation rules (annotator agreement was moderate, kappa 0.34-0.57), and the 'blurry' class is now a focus flag rather than a class.
- Repeat captures are grouped approximately (no frame positions on this cruise).
