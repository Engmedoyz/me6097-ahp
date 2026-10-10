/**
 * ME6097 AHP survey: response collector.
 *
 * Bound to the Google Sheet "ME6097 AHP Responses" (Extensions > Apps Script), deployed as a web app
 * (Execute as: Me, Who has access: Anyone). The survey page (index.html) posts each answer code here;
 * the researcher page (admin.html) lists and deletes rows with the admin key.
 *
 * The admin key lives only in Script Properties (ADMIN_KEY). Run setup() once from the editor: it creates
 * the header row and, if no key exists yet, generates one and prints it in the execution log.
 * No names and no IP addresses are stored (Apps Script does not expose the sender's IP).
 */

var SHEET_NAME = 'Responses';

/* Same lists as the Excel questionnaire (sheet Lists) and the HTML pages. */
var PAIRS = [[0,1],[0,2],[0,3],[0,4],[0,5],[1,2],[1,3],[1,4],[1,5],[2,3],[2,4],[2,5],[3,4],[3,5],[4,5]];
var STEPS = [-4,-3,-2,-1,0,1,2,3,4];
var OPTS = ['A is extremely more important (9)','A is very strongly more important (7)','A is strongly more important (5)',
  'A is moderately more important (3)','A and B are equally important (1)','B is moderately more important (3)',
  'B is strongly more important (5)','B is very strongly more important (7)','B is extremely more important (9)'];
var EXPS = ['Less than 5','5 to 10','11 to 15','16 to 20','More than 20'];
var SPECS = ['Maintenance','Supply','Electrical engineering','Mechanical engineering','Command','Other'];
var JOB = 'Maintenance officer';

function header_() {
  var h = ['Received','Submitted','Language','Job','Specialisation','Years of experience','CR'];
  for (var c = 1; c <= 6; c++) h.push('w_C' + c);
  for (var q = 1; q <= 15; q++) h.push('Q' + q + ' answer');
  for (q = 1; q <= 15; q++) h.push('Q' + q + ' a(A,B)');
  h.push('Code');
  return h;
}
var NCOL = 7 + 6 + 15 + 15 + 1;   // 44
var CODE_COL = NCOL;              // last column

/* ---------------------------------------------------------------- AHP (same algorithm as the HTML pages and the Excel Calc sheet) */
function intensity_(k) { return 2 * Math.abs(k) + 1; }
function valueOf_(k) { return k < 0 ? intensity_(k) : k > 0 ? 1 / intensity_(k) : 1; }
function eig_(A) {
  var n = 6, cs = [], w = [], i, j, it;
  for (j = 0; j < n; j++) { var s = 0; for (i = 0; i < n; i++) s += A[i][j]; cs.push(s); }
  for (i = 0; i < n; i++) w.push(1 / n);
  for (it = 0; it < 40; it++) {
    var den = 0; for (j = 0; j < n; j++) den += cs[j] * w[j];
    var nw = []; for (i = 0; i < n; i++) { var r = 0; for (j = 0; j < n; j++) r += A[i][j] * w[j]; nw.push(r / den); }
    w = nw;
  }
  var lam = 0; for (j = 0; j < n; j++) lam += cs[j] * w[j];
  return { w: w, lam: lam, CR: ((lam - n) / (n - 1)) / 1.24 };
}
function ahp_(a) {
  var A = [], i;
  for (i = 0; i < 6; i++) A.push([1,1,1,1,1,1]);
  PAIRS.forEach(function (p, q) { var v = valueOf_(a[q]); A[p[0]][p[1]] = v; A[p[1]][p[0]] = 1 / v; });
  return eig_(A);
}

/* ---------------------------------------------------------------- answer code AHP6-<base64url JSON>-<fnv4> */
function sum4_(s) {
  var h = 2166136261;
  for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  var x = (h >>> 0).toString(16); x = x.slice(-4); while (x.length < 4) x = '0' + x; return x;
}
function decode_(code) {
  var m = /^AHP6-([A-Za-z0-9_-]+)-([0-9a-f]{4})$/.exec(String(code || ''));
  if (!m || m[1].length > 2000 || sum4_(m[1]) !== m[2]) return null;
  try {
    var b = m[1]; while (b.length % 4) b += '=';
    var o = JSON.parse(Utilities.newBlob(Utilities.base64DecodeWebSafe(b)).getDataAsString('UTF-8'));
    if (!Array.isArray(o.a) || o.a.length !== 15) return null;
    for (var q = 0; q < 15; q++) if (STEPS.indexOf(o.a[q]) < 0) return null;
    if (!(o.e >= 0 && o.e <= 4) || o.e !== Math.floor(o.e)) return null;
    return o;
  } catch (err) { return null; }
}

/* ---------------------------------------------------------------- sheet helpers */
function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, NCOL).setValues([header_()]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}
function findCode_(sh, code) {
  if (sh.getLastRow() < 2) return 0;
  var hit = sh.getRange(2, CODE_COL, sh.getLastRow() - 1, 1).createTextFinder(code).matchEntireCell(true).findNext();
  return hit ? hit.getRow() : 0;
}
function rowFor_(o, code) {
  var x = ahp_(o.a);
  var t = typeof o.t === 'string' && /^\d{4}-\d\d-\d\dT[\d:.]+Z$/.test(o.t) ? o.t : '';
  var lang = o.l === 'ar' || o.l === 'en' ? o.l : '';
  var spec = SPECS[o.s] || SPECS[0];
  var row = [new Date(), t, lang, JOB, spec, EXPS[o.e], Math.round(x.CR * 1e4) / 1e4];
  x.w.forEach(function (v) { row.push(Math.round(v * 1e5) / 1e5); });
  o.a.forEach(function (k) { row.push(OPTS[STEPS.indexOf(k)]); });
  o.a.forEach(function (k) { var v = valueOf_(k); row.push(v >= 1 ? String(v) : '1/' + intensity_(k)); });
  row.push(code);
  return row;
}
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
function isAdmin_(key) {
  var k = PropertiesService.getScriptProperties().getProperty('ADMIN_KEY');
  return !!k && typeof key === 'string' && key === k;
}
function listRows_() {
  var sh = sheet_(), n = sh.getLastRow() - 1;
  if (n < 1) return [];
  var h = header_(), vals = sh.getRange(2, 1, n, NCOL).getValues();
  return vals.map(function (r) {
    var o = {}; h.forEach(function (name, c) { o[name] = r[c] instanceof Date ? r[c].toISOString() : r[c]; }); return o;
  });
}

/* ---------------------------------------------------------------- web app */
function doPost(e) {
  var body;
  try {
    var raw = e && e.postData && e.postData.contents || '';
    if (raw.length > 20000) return json_({ ok: false, error: 'too large' });
    body = JSON.parse(raw);
  } catch (err) { return json_({ ok: false, error: 'bad json' }); }
  var action = body.action || 'submit';

  if (action === 'list') {
    if (!isAdmin_(body.key)) return json_({ ok: false, error: 'denied' });
    return json_({ ok: true, rows: listRows_() });
  }

  var lock = LockService.getScriptLock();
  try { lock.waitLock(20000); } catch (err) { return json_({ ok: false, error: 'busy' }); }
  try {
    var sh = sheet_(), code = String(body.code || '').trim();
    if (action === 'delete') {
      if (!isAdmin_(body.key)) return json_({ ok: false, error: 'denied' });
      var r = findCode_(sh, code);
      if (!r) return json_({ ok: false, error: 'not found' });
      sh.deleteRow(r);
      return json_({ ok: true, deleted: 1 });
    }
    if (action !== 'submit') return json_({ ok: false, error: 'unknown action' });
    var o = decode_(code);
    if (!o) return json_({ ok: false, error: 'invalid code' });
    if (findCode_(sh, code)) return json_({ ok: true, duplicate: true });
    var row = rowFor_(o, code), at = sh.getLastRow() + 1;
    var rg = sh.getRange(at, 1, 1, NCOL);
    // keep ISO times, ratios such as 1/3 and the code as plain text (Sheets would turn 1/3 into a date)
    sh.getRange(at, 2).setNumberFormat('@');
    sh.getRange(at, 7 + 6 + 15 + 1, 1, 15 + 1).setNumberFormat('@');
    sh.getRange(at, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
    rg.setValues([row]);
    return json_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  var key = e && e.parameter && e.parameter.key;
  if (!isAdmin_(key)) return json_({ ok: false });
  return json_({ ok: true, rows: listRows_() });
}

/* ---------------------------------------------------------------- run once from the editor */
function setup() {
  sheet_();
  var props = PropertiesService.getScriptProperties();
  var k = props.getProperty('ADMIN_KEY');
  if (!k) {
    k = Utilities.getUuid().replace(/-/g, '').slice(0, 12) + Utilities.getUuid().replace(/-/g, '').slice(0, 12);
    props.setProperty('ADMIN_KEY', k);
  }
  Logger.log('Sheet ready. ADMIN_KEY = ' + k + '  (Project Settings > Script Properties). Keep it private.');
}
