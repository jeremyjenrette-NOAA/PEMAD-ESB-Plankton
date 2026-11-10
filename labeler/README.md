# CPICS organism-group labeler

Labels likely organisms to a group (Crustacean, Gelatinous, Worm-like, Fish-like, Protozoan,
Phytoplankton/colonial, Other, Unsure, Not an organism), one visual cluster at a time, with batch labeling.
Group list: `docs/annotation_rules_v1.1.md`.

Files: `Index.html` (the page), `Code.gs` (Google Apps Script back end), this README.
Data: the `labeler_data/` folder made by `scripts/organisms_workstation.sh`
(`manifest.json` + `clusters/c0001.json` …, about 20 MB for the 8,619-object pool).

## How labeling works

- Each cluster shows ~45 similar-looking images. A white dot marks objects a person already called an organism.
- Click images to select them (Shift-click for a range), then press a group key **1–9**.
- With **nothing selected**, a group key labels **every unlabeled image** in the cluster. So: label the odd ones
  out first, then press the cluster's main group once.
- Finer group, species and note (bottom bar) are applied to whatever you label next, then cleared.
- Double-click an image to enlarge it. **A** select all, **U** select unlabeled, **Esc** clear, **N** next cluster.
- Relabeling is just labeling again; the newest label wins.

## Option A: Google Apps Script (shared, live; recommended for 3+ labelers)

One-time setup by Jeremy (~15 minutes):

1. Upload the `labeler_data` folder to Google Drive (keep the folder structure). Open it and copy the folder ID
   from the address bar (the part after `/folders/`).
2. Go to <https://script.google.com> → **New project**. Name it "CPICS organism groups".
3. Replace the contents of `Code.gs` with this repo's `labeler/Code.gs`, and paste the folder ID into
   `DATA_FOLDER_ID`.
4. **+ (Add a file) → HTML**, name it `Index` (no extension), and paste in `labeler/Index.html`.
5. **Deploy → New deployment → Web app.** *Execute as:* **Me**. *Who has access:* **Anyone within
   [your organisation]**, or **Anyone with a Google account** if a labeler is outside it. Authorise when asked
   (Drive read, Sheets).
6. Send the web-app URL to the labelers. Each person types their name once (top bar); it is stored in their
   browser and on every label row.

Labels go to a Google Sheet, "CPICS organism group labels", created in your Drive on first save (one row per
label; the newest row per labeler + object wins). Because the app runs as you, labelers do not need access to
the Drive folder or the sheet. If the sheet cannot be reached, labels wait in the labeler's browser and are sent
when it is back.

To update the page later: edit the `Index` file in the Apps Script project → **Deploy → Manage deployments →
Edit → New version**.

## Option B: offline (no accounts; fine for 1–2 labelers)

1. Copy `Index.html` into the `labeler_data` folder as `index.html`.
2. In that folder run `python3 -m http.server 8000` and open <http://localhost:8000> (opening the file directly
   does not work: browsers block it from reading the cluster files).
3. Labels are saved in that browser. When done, press **Export my labels (CSV)** and send the CSV to Jeremy.

## After labeling

Put the exported CSVs (or a CSV download of the sheet) in `labels/organism_groups/` and run the import /
agreement scripts (to be added: merge, agreement between labelers, and the first group classifier).
