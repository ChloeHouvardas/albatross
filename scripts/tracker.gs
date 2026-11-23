/**
 * Intern Radar → Google Sheet tracker.
 *
 * Setup (once): in your Google Sheet → Extensions → Apps Script → paste this file → Save →
 * pick `setup` in the function dropdown → Run → allow access. It syncs now and then every hour.
 *
 * The script only writes the radar columns (A–J). Applied / Applied on / Notes (K–M) are yours
 * and are never overwritten, even when rows are re-sorted.
 */
const FEED = 'https://raw.githubusercontent.com/ChloeHouvardas/albatross/main/data/roles.json';
const SHEET = 'Roles';
const HEAD = ['ID', 'Status', 'Where', 'Company', 'Listed co.', 'Title', 'Location', 'Posted', 'First seen', 'Link',
              'Applied', 'Applied on', 'Notes'];
const RADAR_COLS = 10;
const APPLIED = 11;  // column K

function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('sync').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('onEditStamp').forSpreadsheet(SpreadsheetApp.getActive()).onEdit().create();
  sync();
}

function sheet_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.getRange(1, 1, 1, HEAD.length).setValues([HEAD]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.hideColumns(1);
    sh.setColumnWidth(3, 90); sh.setColumnWidth(4, 140); sh.setColumnWidth(5, 70); sh.setColumnWidth(6, 380);
    sh.setColumnWidth(7, 220); sh.setColumnWidth(10, 60); sh.setColumnWidth(13, 260);
    const rules = [
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$K2=TRUE')
        .setBackground('#d9f2d9').setRanges([sh.getRange('A2:M')]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$B2="closed"')
        .setFontColor('#999999').setRanges([sh.getRange('A2:M')]).build(),
    ];
    sh.setConditionalFormatRules(rules);
    sh.getRange('A1:M').createFilter();
  }
  return sh;
}

function sync() {
  const roles = JSON.parse(UrlFetchApp.fetch(FEED + '?t=' + Date.now()).getContentText());
  const sh = sheet_();
  const last = sh.getLastRow();
  const rowById = {};
  if (last > 1) sh.getRange(2, 1, last - 1, 1).getValues().forEach((r, i) => rowById[r[0]] = i + 2);

  const day = ts => ts ? new Date(ts * 1000) : '';
  const toRow = (id, r) => [id, r.status, r.label, r.company, r.listed ? '✓' : '', r.title, r.location, day(r.posted), day(r.first_seen),
                            `=HYPERLINK("${String(r.url).replace(/"/g, '%22')}","open")`];

  // Rewrite the radar columns (A–J) of existing rows in one batch; K–M are never touched.
  if (last > 1) {
    const block = sh.getRange(2, 1, last - 1, RADAR_COLS).getFormulas();
    const vals = sh.getRange(2, 1, last - 1, RADAR_COLS).getValues();
    const out = vals.map((row, i) => {
      const id = row[0];
      if (roles[id]) return toRow(id, roles[id]);
      // Roles pruned from the feed (closed > 45 days ago) stay, marked closed.
      return row.map((v, c) => block[i][c] || v).map((v, c) => c === 1 ? 'closed' : v);
    });
    sh.getRange(2, 1, out.length, RADAR_COLS).setValues(out);
  }
  const fresh = Object.keys(roles).filter(id => !rowById[id]).map(id => toRow(id, roles[id]));

  if (fresh.length) {
    const start = sh.getLastRow() + 1;
    sh.getRange(start, 1, fresh.length, RADAR_COLS).setValues(fresh);
    sh.getRange(start, APPLIED, fresh.length, 1).insertCheckboxes();
  }
  const n = sh.getLastRow() - 1;
  if (n > 0) {
    sh.getRange(2, 8, n, 2).setNumberFormat('mmm d, yyyy');
    sh.getRange(2, APPLIED + 1, n, 1).setNumberFormat('mmm d, yyyy');
    // open first, then newest first-seen; whole rows move so your columns stay with their role
    sh.getRange(2, 1, n, HEAD.length).sort([{column: 2, ascending: false}, {column: 9, ascending: false}]);
  }
}

/** Ticking "Applied" stamps today's date in "Applied on". */
function onEditStamp(e) {
  const r = e.range;
  if (r.getSheet().getName() !== SHEET || r.getColumn() !== APPLIED || r.getRow() < 2) return;
  const cell = r.offset(0, 1);
  if (r.getValue() === true && !cell.getValue()) cell.setValue(new Date());
}
