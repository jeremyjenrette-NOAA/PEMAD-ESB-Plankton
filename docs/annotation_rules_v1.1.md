# CPICS Annotation Rules: v1.1 amendments

Version 1.1 · November 10, 2026 · PEMAD-ESB Plankton project

v1.1 keeps everything in v1.0 (`docs/annotation_rules_v1.0.md`) except the points below. They come from the
calibration round (Jeremy vs Jordan, 100 objects, Oct 2026): class agreement 72%, kappa 0.64 (target 0.7);
organism vs not 88%, kappa 0.70; focus kappa 0.48; needs box kappa 0.23. The 44 disagreements were settled in
favour of Jordan's labels (`labels/calibration/adjudication.csv`, `labels/calibration/calibration_final.csv`).

## Clarified rules

| Rule | v1.1 wording | Why (calibration) |
|---|---|---|
| 1. Unidentifiable | Use it when you would be guessing between organism and non-organism, including blurry objects. Commit to a class only when you are fairly sure (roughly 2:1 odds). | Jordan used it for "too blurry to confirm"; Jeremy committed. 10 disagreements. Jeremy's 480-object blurry relabel used it 58% of the time, matching Jordan. |
| 3. Organism in marine snow | Organism only when you can point to a body part (segments, appendages, a regular chain or rod) that would be recognisable on its own. Otherwise Marine snow, with the note "possible organism". | 6 disagreements (Jeremy marine snow, Jordan organism). |
| 4. Ring vs artifact | Ring = round halos, bubbles, circular rings. Artifact = straight streaks, glare, lighting, instrument parts. Mixed: whichever covers more of the image. | 3 disagreements. |
| 5. Needs box | **Retired from triage.** Boxes are decided in the detection phase, not during class labeling. | Kappa 0.23; rarely agreed. |
| 6. Multiple | Only when two or more distinct objects would each get their own class. Ignore tiny specks. | Used 10 times by Jordan, never by Jeremy. |
| 8. Expert flag | Press F (do not only write "flag an expert" in the note). | Several notes asked for an expert without the flag set. |

## Organism groups (new)

Every object labeled Organism can also get a group. Level 1 is required in group labeling; Level 2 and species
are optional (fill them only when sure). Draft list, open to edits by Jordan and Harvey.

| Level 1 | Level 2 (optional) |
|---|---|
| Crustacean | copepod · nauplius · cladoceran · crustacean larva (zoea, cyprid) · other crustacean |
| Gelatinous | appendicularian (larvacean) · cnidarian (medusa, siphonophore) · ctenophore · salp/doliolid |
| Worm-like | chaetognath · polychaete · other worm-like |
| Fish-like | fish egg · fish larva |
| Protozoan | radiolarian/foraminiferan · ciliate · other protozoan |
| Phytoplankton / colonial | diatom chain · single diatom · dinoflagellate · other colony |
| Other organism | (note what it is) |
| Unsure organism | an organism, group unknown |
| Not an organism | sends the object back to triage |

## Change log

- v1.1 (Nov 10, 2026): calibration disagreements settled with Jordan's labels as priority; rules 1, 3, 4, 6, 8
  clarified; Needs box retired from triage; organism group list added.
- v1.0 (Oct 14, 2026): first agreed version.
