/**
 * CPICS organism-group labeler: Google Apps Script back end.
 * Serves Index.html, reads the image clusters from a Drive folder and appends labels to a Google Sheet.
 * Setup: see README.md (copy this file and Index.html into a new Apps Script project, set DATA_FOLDER_ID, deploy).
 */
const CONFIG = {
  DATA_FOLDER_ID: 'PASTE_THE_DRIVE_FOLDER_ID_OF_labeler_data_HERE',  // folder holding manifest.json and clusters/
  SHEET_ID: '',  // leave blank: a sheet "CPICS organism group labels" is created in your Drive on first use
};
const HEAD = ['saved_at', 'labeler', 'object_id', 'roi_id', 'cruise', 'cluster', 'group', 'group2', 'species',
              'note', 'expert_flag', 'labeled_at', 'account'];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
      .setTitle('CPICS organism groups')
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function folder_() { return DriveApp.getFolderById(CONFIG.DATA_FOLDER_ID); }

function readText_(folder, name) {
  const it = folder.getFilesByName(name);
  if (!it.hasNext()) throw new Error('Missing ' + name + ' in the data folder');
  return it.next().getBlob().getDataAsString();
}

/** manifest.json as text (the page parses it). */
function getManifest() { return readText_(folder_(), 'manifest.json'); }

/** One cluster file (e.g. c0001.json) as text. */
function getCluster(file) {
  if (!/^c\d{4}\.json$/.test(file)) throw new Error('Bad cluster file name');
  const sub = folder_().getFoldersByName('clusters');
  if (!sub.hasNext()) throw new Error('Missing clusters/ folder');
  return readText_(sub.next(), file);
}

/** Email of the signed-in person when Google shares it (same organisation); otherwise blank. */
function whoAmI() {
  try { return Session.getActiveUser().getEmail() || ''; } catch (e) { return ''; }
}

function sheet_() {
  const props = PropertiesService.getScriptProperties();
  const id = CONFIG.SHEET_ID || props.getProperty('SHEET_ID');
  let ss;
  if (id) {
    ss = SpreadsheetApp.openById(id);
  } else {
    ss = SpreadsheetApp.create('CPICS organism group labels');
    props.setProperty('SHEET_ID', ss.getId());
  }
  let sh = ss.getSheetByName('labels');
  if (!sh) {
    sh = ss.insertSheet('labels');
    sh.appendRow(HEAD);
    sh.setFrozenRows(1);
  }
  return sh;
}

/** Append label rows. Rows are never edited: the newest row per labeler + object wins. */
function saveLabels(rows) {
  if (!rows || !rows.length) return 0;
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sh = sheet_();
    const acct = whoAmI();
    const vals = rows.map(r => [new Date(), String(r.labeler || ''), String(r.id || ''), String(r.roi || ''),
      String(r.cruise || ''), Number(r.cluster) || '', String(r.group || ''), String(r.group2 || ''),
      String(r.species || ''), String(r.note || ''), !!r.flag, String(r.at || ''), acct]);
    sh.getRange(sh.getLastRow() + 1, 1, vals.length, HEAD.length).setValues(vals);
    return vals.length;
  } finally {
    lock.releaseLock();
  }
}

/** Latest label per object for one labeler (or everyone when labeler is blank), as JSON text. */
function getLabels(labeler) {
  const sh = sheet_();
  const n = sh.getLastRow();
  if (n < 2) return '[]';
  const v = sh.getRange(2, 1, n - 1, HEAD.length).getValues();
  const out = {};
  for (const r of v) {
    if (labeler && r[1] !== labeler) continue;
    out[r[1] + '|' + r[2]] = {labeler: r[1], id: r[2], roi: r[3], cruise: r[4], cluster: r[5], group: r[6],
      group2: r[7], species: r[8], note: r[9], flag: r[10], at: r[11]};
  }
  return JSON.stringify(Object.values(out));
}
