**CPICS Annotation Rules**

Version 1.0 · agreed October 14, 2026 · PEMAD-ESB Plankton project

Agreed by Jeremy Jenrette, Jordan K. and the annotation team. These
rules apply to all labeling from the calibration round onward. Changes
go into a new version with a dated change note; decisions from the
October meeting are marked “Decided”.

1\. Why we need written rules

In a blind check, Jeremy relabeled 199 of Jordan’s objects without
seeing her labels, and Jordan relabeled 99 of Jeremy’s. We agreed on 45%
and 66% of objects respectively. The biggest gap was not between days or
between images; it was where each of us draws the lines between blurry,
marine snow and organism.

| **Share of objects called organism** | **Labeled by Jordan** | **Labeled by Jeremy** |
|--------------------------------------|-----------------------|-----------------------|
| Jordan’s 13 days                     | 40%                   | 17%                   |
| The 17 new days                      | 18%                   | 7%                    |

On the same images, Jordan finds about 2.5 times as many organisms as
Jeremy. The new survey days also hold about 2.5 times fewer organisms
than Jordan’s days. Both effects are real and about the same size. The
model learns whatever the labels say, so until we label the same way, it
cannot be judged fairly or improved reliably.

| **Blind check**           | **Objects** | **All classes agree (kappa)** | **Organism vs. not (kappa)** |
|---------------------------|-------------|-------------------------------|------------------------------|
| A: Jeremy relabels Jordan | 199         | 45% (0.34)                    | 73% (0.40)                   |
| B: Jordan relabels Jeremy | 99          | 66% (0.57)                    | 84% (0.62)                   |

Kappa corrects for chance agreement: below 0.4 is weak, 0.4–0.6
moderate, above 0.6 substantial. **Target after these rules: kappa ≥ 0.7
on a fresh calibration set before anyone labels at scale.**

2\. What each object gets

Every ROI receives one class and a few independent flags. Separating
class from image quality is the main change from V3, where “blurry” was
used both as a class and as a description of focus.

| **Field**   | **Values**                                                | **Meaning**                                                                                       |
|-------------|-----------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| Class       | Organism · Marine snow · Ring · Artifact · Unidentifiable | What the main object is. Exactly one per ROI.                                                     |
| Focus       | Sharp · Blurry                                            | Image quality, recorded separately from class. A blurry organism is class Organism, focus Blurry. |
| Needs box   | Yes · No                                                  | The crop is not usable as is (see Rule 5). Independent of class.                                  |
| Multiple    | Yes · No, plus count                                      | More than one object of interest in the ROI (see Rule 6).                                         |
| Expert flag | Yes · No, plus note                                       | You want Harvey (or another expert) to check it. Use freely; do not guess.                        |
| Note        | Free text                                                 | Anything useful: morphotype (“stick-like”, “diatom chain”), why you were unsure.                  |

3\. Class definitions

| **Class**      | **Use when**                                                                                                                                                                                                  | **Do not use when**                                                                                                                |
|----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| Organism       | You can point to a specific living structure: a cell or chain of cells, a segmented or tubular body, appendages, a recognizable shape (diatom, copepod, larvacean, worm-like). Partial or soft-focus is fine. | The object is an aggregate of particles with no distinct body you can point to (Marine snow), or you cannot tell (Unidentifiable). |
| Marine snow    | Detritus or aggregates: irregular, fluffy, flocculent, often with mixed colors and embedded particles, no body plan.                                                                                          | A distinct organism is visible inside or beside the aggregate (see Rule 3).                                                        |
| Ring           | The image is visually dominated by one or more rings: optical halos, bubbles, circular camera rings.                                                                                                          | Streaks, glare or lighting dominate (Artifact).                                                                                    |
| Artifact       | The image is dominated by camera or instrument effects that do not resemble a ring: streaks, glare, intense lighting, lens edges, parts of the instrument.                                                    | One or more rings dominate (Ring).                                                                                                 |
| Unidentifiable | You genuinely cannot tell whether it is an organism or not, usually because it is too out of focus or too small. Last resort.                                                                                 | You can make a reasonable call. Choose that class and set Focus to Blurry instead.                                                 |

4\. Decision rules

Rule 1. Class first, focus second

Decide what the object most likely is, then record focus separately.
“Unidentifiable” is only for objects where you cannot tell organism from
non-organism. This replaces the old “blurry” class.

In the blind check, Jeremy labeled 42 of Jordan’s 45 marine snow objects
and 22 of her 50 organisms as blurry. Under this rule most of those
become Marine snow or Organism with Focus = Blurry.

<img src="media/c1f0e7e0786d95e09cc995547a4d28e52c05c085.png"
title="Figure 1. Jordan: marine snow; Jeremy: blurry. Under Rule 1 these are Marine snow (Focus: Blurry) unless no call is possible. Images are enlarged to the same size; the original ROI size is shown in brackets."
style="width:6.5in;height:1.88542in"
alt="Figure 1. Jordan: marine snow; Jeremy: blurry. Under Rule 1 these are Marine snow (Focus: Blurry) unless no call is possible. Images are enlarged to the same size; the original ROI size is shown in brackets." />

*Figure 1. Jordan: marine snow; Jeremy: blurry. Under Rule 1 these are
Marine snow (Focus: Blurry) unless no call is possible. Images are
enlarged to the same size; the original ROI size is shown in brackets.*

<img src="media/ab1596cbcc46687d994803eb8366aeba95a035a4.png"
title="Figure 2. Jordan: organism; Jeremy: blurry. Under Rule 1, Organism (Focus: Blurry) if a body plan is visible; otherwise Unidentifiable."
style="width:6.5in;height:1.88542in"
alt="Figure 2. Jordan: organism; Jeremy: blurry. Under Rule 1, Organism (Focus: Blurry) if a body plan is visible; otherwise Unidentifiable." />

*Figure 2. Jordan: organism; Jeremy: blurry. Under Rule 1, Organism
(Focus: Blurry) if a body plan is visible; otherwise Unidentifiable.*

<img src="media/d63b874d836bb72419f38f093127089b464dffc6.png"
title="Figure 3. The reverse case from the new days: Jeremy: blurry; Jordan: organism."
style="width:6.5in;height:1.88542in"
alt="Figure 3. The reverse case from the new days: Jeremy: blurry; Jordan: organism." />

*Figure 3. The reverse case from the new days: Jeremy: blurry; Jordan:
organism.*

**Decided:** “Unidentifiable” is kept as a class, for objects where you
cannot tell organism from non-organism. Use the expert flag with it when
an expert might be able to tell.

Rule 2. Organism needs something you can point to

Call it Organism when you can point to a specific structure that belongs
to a living thing. Shape alone (“shape of interest”) is not enough
unless it matches a known form. When you cannot point to anything, it is
Marine snow or Unidentifiable, and you can add the expert flag.

Rule 3. Organisms inside or beside marine snow

Several of Jordan’s “organism, needs box” objects are aggregates with
something embedded in them. Jeremy labeled most of these marine snow and
reports he cannot see an organism in several of them. We need one shared
answer.

<img src="media/61e40fcd97f3ede4e718af45fc20ba400b51a634.png"
title="Figure 4. Jordan: organism, needs box; Jeremy: marine snow. Is there an organism to box in each of these?"
style="width:6.5in;height:1.88542in"
alt="Figure 4. Jordan: organism, needs box; Jeremy: marine snow. Is there an organism to box in each of these?" />

*Figure 4. Jordan: organism, needs box; Jeremy: marine snow. Is there an
organism to box in each of these?*

<img src="media/32b763b6a2ed190f37193ccff213402dd6628d99.png"
title="Figure 5. Jordan: organism, needs box; Jeremy: blurry."
style="width:6.5in;height:1.88542in"
alt="Figure 5. Jordan: organism, needs box; Jeremy: blurry." />

*Figure 5. Jordan: organism, needs box; Jeremy: blurry.*

**Decided:** If a distinct organism is clearly identifiable on its own
inside or beside an aggregate, the ROI is Organism with Needs box = Yes.
Otherwise it is Marine snow (add a note if something looks
organism-like).

Rule 4. Ring vs. artifact: whichever dominates

If the image is visually dominated by one or more rings, it is Ring. If
it is clearly a camera artifact dominated by streaks, glare or intense
lighting that does not resemble a ring, it is Artifact. When both are
present, choose the one that takes up more of the image.

<img src="media/a572e9cc57ec81ed0bc7b3a4f4e08054937a183e.png"
title="Figure 6. Jeremy: ring; Jordan: artifact."
style="width:6.5in;height:1.88542in"
alt="Figure 6. Jeremy: ring; Jordan: artifact." />

*Figure 6. Jeremy: ring; Jordan: artifact.*

<img src="media/96ae8c491f20757fde36e88a09639fd947a4f6c3.png"
title="Figure 7. Jordan: ring; Jeremy: artifact."
style="width:6.5in;height:1.88542in"
alt="Figure 7. Jordan: ring; Jeremy: artifact." />

*Figure 7. Jordan: ring; Jeremy: artifact.*

<img src="media/c0028b8583bf14ab489463f32976c412d1ee3467.png"
title="Figure 8. Jeremy: blurry; Jordan: artifact. Under Rules 1 and 4, likely Artifact (Focus: Blurry)."
style="width:6.5in;height:1.88542in"
alt="Figure 8. Jeremy: blurry; Jordan: artifact. Under Rules 1 and 4, likely Artifact (Focus: Blurry)." />

*Figure 8. Jeremy: blurry; Jordan: artifact. Under Rules 1 and 4, likely
Artifact (Focus: Blurry).*

Rule 5. Needs box only when the crop is not usable as is

Most CPICS ROIs are already a tight crop. Boxing a small organism that
already fills its ROI adds nothing and can make the crop worse. Set
Needs box = Yes only when the organism takes up a small part of a large
ROI, or other objects (rings, snow, a second organism) share the frame
and would confuse a classifier.

**Decided:** Needs box stays a flag, independent of class. Guideline:
set it when the organism spans less than about half of the ROI’s longer
side, or when other objects share the frame.

Rule 6. Several objects in one ROI

Give the ROI one class, for the most relevant object (an organism takes
priority over snow, rings or artifacts). Set Multiple = Yes and record
how many objects of interest there are. If there are several different
organisms, note what they are.

Rule 7. Objects captured many times

Some objects rest in the camera’s view and are saved hundreds of times
(May 21: 7,125 ROIs of only 33 objects). The pipeline groups these
automatically, so label the object as usual; the repeat count is
recorded separately. Several of the May 21 objects appear to be diatom
chains resting on the window; they will be relabeled Organism once
Harvey confirms which ones.

<img src="media/384eb0859cdead8b3a636d6fb92ffbfb4d92cad7.png"
title="Figure 9. Objects resting in view on May 21. The pennate diatom-like objects (middle two) were labeled artifact; the aggregate (left) likely stays marine snow. Harvey to confirm."
style="width:6.5in;height:1.88542in"
alt="Figure 9. Objects resting in view on May 21. The pennate diatom-like objects (middle two) were labeled artifact; the aggregate (left) likely stays marine snow. Harvey to confirm." />

*Figure 9. Objects resting in view on May 21. The pennate diatom-like
objects (middle two) were labeled artifact; the aggregate (left) likely
stays marine snow. Harvey to confirm.*

Rule 8. When unsure, flag; do not guess

Use the expert flag and a short note rather than forcing a label you do
not believe. Flagged objects are reviewed by Harvey in batches, and his
answers become worked examples in this document.

5\. Applying the rules to the labels we already have

- **Labels that are not “blurry”** (organism, marine snow, ring,
  artifact) keep their class. Focus is left blank until someone views
  them again.

- **Labels that are “blurry”** (about 590 objects) are relabeled in one
  pass: choose a class and set Focus = Blurry. The model pre-selects its
  best guess to speed this up.

- **“Organism, needs box”** (359 of Jordan’s objects) is split into
  Class = Organism and Needs box = Yes, then reviewed under Rules 3 and
  5.

- **Ring/artifact splits** are reviewed under Rule 4.

- **May 21 resting objects** confirmed as diatom chains are corrected to
  Organism, with the change recorded (who, when, why) rather than
  overwriting the original label.

Every change is kept in the label history, so earlier versions can be
rebuilt and compared.

6\. After the rules are agreed

1.  **Freeze v1.0** of this document (done). A copy is stored with the
    code, and the class definitions are shown inside the labeling page.

2.  **Update the label table and labeling page** with the new fields
    (class, focus, needs box, multiple, expert flag).

3.  **Calibration round.** Jordan and Jeremy each label the same ~100
    new objects under v1.0. Target kappa ≥ 0.7; if not met, refine the
    rules and repeat.

4.  **Relabel the disputed groups** listed in section 5, producing
    labels v4.

5.  **Expert review.** Harvey reviews flagged objects and the May 21
    objects.

6.  **Re-run the baseline model on v4** to measure how much consistent
    labels improve it.

7.  **Targeted labeling** (~250 objects chosen by the model), then
    fine-tuning the classifier and starting box labels for the detector.

7\. Decisions from the October meeting

| **Question**                                     | **Decision**                                                                                                                         |
|--------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| Keep “Unidentifiable” as a class? (Rule 1)       | Yes. Last resort, for objects where you cannot tell organism from non-organism.                                                      |
| Organism embedded in marine snow (Rule 3)        | Organism + Needs box when the organism is clearly identifiable on its own; otherwise Marine snow.                                    |
| Size guideline for Needs box (Rule 5)            | Needs box is a flag. Set it when the organism spans less than about half of the ROI’s longer side, or other objects share the frame. |
| Third Focus level?                               | No. Focus is Sharp or Blurry.                                                                                                        |
| Morphotype names in the Note field               | Use these where they fit: stick-like, diatom chain, worm-like, golden worm-like, blob, ribbon. Other descriptions are fine.          |
| Which May 21 objects are diatom chains? (Rule 7) | Pending Harvey’s review. Until then they keep their current labels.                                                                  |

Keys in the labeling page

| **Key** | **Action**                                                                                                  |
|---------|-------------------------------------------------------------------------------------------------------------|
| 1 – 5   | Class: 1 Organism, 2 Marine snow, 3 Ring, 4 Artifact, 5 Unidentifiable. Saves and moves to the next object. |
| B       | Focus: toggles Blurry (default Sharp).                                                                      |
| X       | Needs box: toggles Yes/No.                                                                                  |
| M       | Multiple: toggles Yes/No; type the count in the box.                                                        |
| F       | Expert flag: toggles Yes/No; add a note.                                                                    |
| ← →     | Previous / next object.                                                                                     |

Set B, X, M or F first, then press the class key: it saves everything
and moves on.

Change log

- v1.0 (October 14, 2026): first agreed version. Decisions above;
  replaces the V3 “Blurry” class and the “Organism, needs box” class
  with separate Focus and Needs box fields.

*Interactive versions of every figure, with all examples and the
similarity map, are in the CPICS ROI Atlas page.*
