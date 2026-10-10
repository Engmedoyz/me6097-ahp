"""End-to-end checks of index.html + admin.html against a collector (dev/mock_server.py by default).

    python dev/flow_test.py [base_url] [admin_key] [reference_responses_html]

1. three responses sent through the survey page (consistent, all equal, inconsistent) -> three sheet rows with the
   right answer texts and a(A,B) values; 2. a repeated code is ignored; 3. with the collector down the WhatsApp
   fallback appears and the draft survives a reload, and the retry sends the same code; 4. admin.html shows the same
   CR and weights as the original ahp_responses.html for the same codes; 5. paste box and delete.
Mock-only steps (sheet rows, outage) are skipped when base_url is not localhost.
"""
import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
KEY = sys.argv[2] if len(sys.argv) > 2 else "devkey"
REF = Path(sys.argv[3] if len(sys.argv) > 3 else Path(__file__).resolve().parents[2] / "outputs/report_v3.9_20261009/AHP/web/ahp_responses.html")
MOCK = BASE.startswith("http://localhost")
CASES = {"consistent": [0,-1,-1,-1,-2,0,-1,-1,-1,0,-1,-1,0,-1,0], "equal": [0]*15,
         "inconsistent": [-4,4,-3,3,-4,4,-2,4,-4,3,-4,4,-3,4,-4]}
OPTS = ["A is extremely more important (9)","A is very strongly more important (7)","A is strongly more important (5)",
        "A is moderately more important (3)","A and B are equally important (1)","B is moderately more important (3)",
        "B is strongly more important (5)","B is very strongly more important (7)","B is extremely more important (9)"]
AV = ["9","7","5","3","1","1/3","1/5","1/7","1/9"]
fails = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)
def get(path): return json.loads(urllib.request.urlopen(BASE + path).read())


def send(pg, lang, ans, e=1):
    pg.goto(f"{BASE}/index.html")
    pg.evaluate("([l,a,e])=>{localStorage.removeItem('ahp6-draft');localStorage.setItem('ahp6-draft',JSON.stringify({ans:a,e,lang:l}))}", [lang, ans, e])
    pg.reload(); pg.click("#startBtn"); pg.click("#submitBtn")
    pg.wait_for_selector(".check, .alert.err", timeout=40000)
    return pg.evaluate("localStorage.getItem('ahp6-last')").strip('"'), pg.locator(".check").count() == 1


with sync_playwright() as p:
    br = p.chromium.launch(channel="msedge", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = br.new_context(viewport={"width": 1280, "height": 860}); pg = ctx.new_page()
    if MOCK: get("/__reset")
    codes = {}
    for n, (name, ans) in enumerate(CASES.items()):
        code, ok = send(pg, "ar" if n == 1 else "en", ans, e=n)
        codes[name] = code
        check(ok, f"{name}: survey shows 'received'")
        check(pg.evaluate("localStorage.getItem('ahp6-draft')") is None, f"{name}: draft cleared after success")
    if MOCK:
        rows = get("/__rows")["rows"]
        check(len(rows) == 3, f"sheet has 3 rows (got {len(rows)})")
        for row, (name, ans) in zip(rows, CASES.items()):
            check(row[13:28] == [OPTS[k+4] for k in ans], f"{name}: Q1..Q15 answer texts")
            check(row[28:43] == [AV[k+4] for k in ans], f"{name}: Q1..Q15 a(A,B) values")
            check(row[43] == codes[name] and row[3] == "Maintenance officer" and row[4] == "Maintenance", f"{name}: code, job, specialisation")
    # duplicate
    dup = pg.evaluate("async([u,c])=>{const r=await fetch(u,{method:'POST',headers:{'Content-Type':'text/plain'},body:JSON.stringify({code:c})});return r.json()}",
                      [pg.evaluate("document.querySelector('script:not([src])').textContent.match(/SUBMIT_URL = \"([^\"]+)\"/)[1]"), codes["consistent"]])
    check(dup.get("ok") and dup.get("duplicate"), "repeated code is ignored (duplicate:true)")
    if MOCK: check(len(get("/__rows")["rows"]) == 3, "still 3 rows after the repeat")

    # outage -> fallback, draft survives reload, retry sends the same code
    if MOCK:
        get("/__fail?on=1")
        ans = [1,0,-1,2,0,1,0,-1,0,1,0,0,-2,0,1]
        code1, ok = send(pg, "en", ans, e=3)
        check(not ok and pg.locator(".alert.err").count() == 1 and pg.locator("#waBtn").count() == 1, "outage: WhatsApp fallback shown")
        pg.reload(); pg.wait_for_timeout(500)
        d = json.loads(pg.evaluate("localStorage.getItem('ahp6-draft')") or "null")
        check(d is not None and d["ans"] == ans and d["pend"]["code"] == code1, "outage: draft (and its code) survive a reload")
        get("/__fail?on=0")
        pg.click("#startBtn"); pg.click("#submitBtn"); pg.wait_for_selector(".check, .alert.err", timeout=40000)
        check(pg.locator(".check").count() == 1, "retry after outage succeeds")
        check(get("/__rows")["rows"][-1][43] == code1, "retry sent the same code")
        codes["retry"] = code1

    # admin vs reference page
    pg.goto(f"{BASE}/admin.html"); pg.evaluate("localStorage.clear()"); pg.reload()
    pg.fill("#keyIn", "wrong-key"); pg.click("#keyBtn"); pg.wait_for_selector(".msg.bad", timeout=40000)
    check(pg.locator("#keyIn").count() == 1, "admin: wrong key refused")
    pg.fill("#keyIn", KEY); pg.click("#keyBtn"); pg.wait_for_selector("table", timeout=40000)
    n_rows = pg.locator("tr.main").count()
    check(n_rows == len(codes), f"admin: {n_rows} rows shown")
    grab = "()=>[...document.querySelectorAll('tr.main')].map(tr=>[...tr.querySelectorAll('td')].slice(4,11).map(td=>td.textContent.trim()).join(' '))"
    grp = "()=>[...document.querySelectorAll('.bar')].map(b=>b.textContent.trim()).join(' | ')"
    adm_rows, adm_grp = pg.evaluate(grab), pg.evaluate(grp)
    ref = ctx.new_page(); ref.goto(REF.resolve().as_uri()); ref.wait_for_selector("#paste")
    ref.fill("#paste", "\n".join(codes.values())); ref.click("#addBtn"); ref.wait_for_selector("table")
    check(sorted(ref.evaluate(grab)) == sorted(adm_rows), "admin CR and weights equal ahp_responses.html for the same codes")
    check(ref.evaluate(grp) == adm_grp, "admin group weights equal ahp_responses.html")
    print("  e.g.", adm_rows[0], "\n  group:", adm_grp)

    # paste box adds a WhatsApp code; delete removes rows
    msg_code = codes.pop("consistent")
    pg.click("tr.main >> nth=0 >> button.danger"); pg.click("tr.main >> nth=0 >> button.armed")
    pg.wait_for_function(f"document.querySelectorAll('tr.main').length=={n_rows-1}", timeout=40000)
    check(True, "admin: delete with in-page confirmation")
    pg.fill("#paste", f"ME6097 AHP survey response\n{msg_code}"); pg.click("#addBtn")
    pg.wait_for_function(f"document.querySelectorAll('tr.main').length=={n_rows}", timeout=40000)
    check(True, "admin: pasted WhatsApp code added to the sheet")
    codes["consistent"] = msg_code
    # clean up: delete every test row
    while pg.locator("tr.main").count():
        k = pg.locator("tr.main").count()
        pg.click("tr.main >> nth=0 >> button.danger"); pg.click("tr.main >> nth=0 >> button.armed")
        pg.wait_for_function(f"document.querySelectorAll('tr.main').length=={k-1}", timeout=40000)
    check(pg.locator("tr.main").count() == 0, "test rows deleted")
    br.close()
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED")
