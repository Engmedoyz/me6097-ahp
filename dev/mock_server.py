"""Local stand-in for the Apps Script web app, for testing index.html and admin.html offline.

    python dev/mock_server.py            -> http://localhost:8765/index.html and /admin.html

Serves the pages with SUBMIT_URL pointed at http://localhost:8765/api and answers /api like apps_script/Code.gs
(submit, duplicate, list, delete; admin key "devkey"). GET /__fail?on=1 makes /api fail (to test the WhatsApp
fallback), /__fail?on=0 restores it, GET /__rows shows the stored sheet rows as JSON.
"""
import base64, json, math, re, sys
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
ADMIN_KEY = "devkey"
PAIRS = [(0,1),(0,2),(0,3),(0,4),(0,5),(1,2),(1,3),(1,4),(1,5),(2,3),(2,4),(2,5),(3,4),(3,5),(4,5)]
STEPS = [-4,-3,-2,-1,0,1,2,3,4]
OPTS = ["A is extremely more important (9)","A is very strongly more important (7)","A is strongly more important (5)",
        "A is moderately more important (3)","A and B are equally important (1)","B is moderately more important (3)",
        "B is strongly more important (5)","B is very strongly more important (7)","B is extremely more important (9)"]
EXPS = ["Less than 5","5 to 10","11 to 15","16 to 20","More than 20"]
HEADER = (["Received","Submitted","Language","Job","Specialisation","Years of experience","CR"]
          + [f"w_C{c}" for c in range(1,7)] + [f"Q{q} answer" for q in range(1,16)] + [f"Q{q} a(A,B)" for q in range(1,16)] + ["Code"])
ROWS: list[list] = []
FAIL = {"on": False}


def intensity(k): return 2*abs(k)+1
def value_of(k): return intensity(k) if k < 0 else 1/intensity(k) if k > 0 else 1.0

def ahp(a):
    A = [[1.0]*6 for _ in range(6)]
    for q,(i,j) in enumerate(PAIRS):
        v = value_of(a[q]); A[i][j] = v; A[j][i] = 1/v
    cs = [sum(A[i][j] for i in range(6)) for j in range(6)]
    w = [1/6]*6
    for _ in range(40):
        den = sum(c*x for c,x in zip(cs,w))
        w = [sum(A[i][j]*w[j] for j in range(6))/den for i in range(6)]
    lam = sum(c*x for c,x in zip(cs,w))
    return w, ((lam-6)/5)/1.24

def sum4(s):
    h = 2166136261
    for ch in s:
        h ^= ord(ch); h = (h*16777619) & 0xFFFFFFFF
    return format(h, "x")[-4:].rjust(4, "0")

def decode(code):
    m = re.fullmatch(r"AHP6-([A-Za-z0-9_-]+)-([0-9a-f]{4})", code or "")
    if not m or sum4(m[1]) != m[2]: return None
    try:
        b = m[1] + "="*(-len(m[1]) % 4)
        o = json.loads(base64.urlsafe_b64decode(b).decode("utf-8"))
        if not isinstance(o.get("a"), list) or len(o["a"]) != 15 or any(k not in STEPS for k in o["a"]): return None
        if not (isinstance(o.get("e"), int) and 0 <= o["e"] <= 4): return None
        return o
    except Exception:
        return None

def row_for(o, code):
    w, cr = ahp(o["a"])
    return ([datetime.now(timezone.utc).isoformat(timespec="seconds"), o.get("t",""), o.get("l",""), "Maintenance officer",
             "Maintenance", EXPS[o["e"]], round(cr,4)] + [round(x,5) for x in w]
            + [OPTS[STEPS.index(k)] for k in o["a"]]
            + [str(int(value_of(k))) if value_of(k) >= 1 else f"1/{intensity(k)}" for k in o["a"]] + [code])

def handle(body):
    action = body.get("action", "submit")
    if action == "list":
        if body.get("key") != ADMIN_KEY: return {"ok": False, "error": "denied"}
        return {"ok": True, "rows": [dict(zip(HEADER, r)) for r in ROWS]}
    code = str(body.get("code","")).strip()
    if action == "delete":
        if body.get("key") != ADMIN_KEY: return {"ok": False, "error": "denied"}
        for n,r in enumerate(ROWS):
            if r[-1] == code: del ROWS[n]; return {"ok": True, "deleted": 1}
        return {"ok": False, "error": "not found"}
    o = decode(code)
    if not o: return {"ok": False, "error": "invalid code"}
    if any(r[-1] == code for r in ROWS): return {"ok": True, "duplicate": True}
    ROWS.append(row_for(o, code)); return {"ok": True}


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
    def log_message(self, fmt, *args): sys.stderr.write("[mock] " + fmt % args + "\n")
    def _json(self, obj, status=200):
        b = json.dumps(obj).encode()
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/__fail": FAIL["on"] = q.get("on",["1"])[0] == "1"; return self._json({"fail": FAIL["on"]})
        if u.path == "/__rows": return self._json({"header": HEADER, "rows": ROWS})
        if u.path == "/__reset": ROWS.clear(); FAIL["on"] = False; return self._json({"ok": True})
        if u.path == "/api":
            if FAIL["on"]: return self._json({"ok": False, "error": "down"}, 503)
            return self._json({"ok": True, "rows": [dict(zip(HEADER, r)) for r in ROWS]} if q.get("key",[""])[0] == ADMIN_KEY else {"ok": False})
        if u.path in ("/", "/index.html", "/admin.html"):
            name = "index.html" if u.path == "/" else u.path[1:]
            s = (ROOT/name).read_text(encoding="utf-8").replace('"PASTE_APPS_SCRIPT_WEB_APP_URL_HERE"', f'"http://localhost:{PORT}/api"', 1)
            s = re.sub(r'const SUBMIT_URL = "https://[^"]+";', f'const SUBMIT_URL = "http://localhost:{PORT}/api";', s, count=1)
            b = s.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n)
        if FAIL["on"]: return self._json({"ok": False, "error": "down"}, 503)
        try: body = json.loads(raw.decode("utf-8"))
        except Exception: return self._json({"ok": False, "error": "bad json"})
        return self._json(handle(body))


if __name__ == "__main__":
    print(f"mock Apps Script on http://localhost:{PORT}/  (admin key: {ADMIN_KEY})")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
