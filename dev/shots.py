"""Screenshots of the survey and admin pages in installed Microsoft Edge (Playwright, no browser download).

    python dev/shots.py [base_url] [out_dir]

Defaults: http://localhost:8765 (dev/mock_server.py) and ./screenshots. Phone 390x844 and desktop 1440x900,
English and Arabic, light and dark: start screen, a question, the review list and the screen after sending.
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "screenshots")
OUT.mkdir(parents=True, exist_ok=True)
VIEWS = {"phone": dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True),
         "desktop": dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1)}
ANS = [-2, -1, 1, 0, -3, 2, 1, -1, 0, -2, 1, 3, 0, -1, 2]


def run(only=None):
    problems = []
    with sync_playwright() as p:
        br = p.chromium.launch(channel="msedge", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for vname, vopt in VIEWS.items():
            for lang in ("en", "ar"):
                for theme in ("light", "dark"):
                    tag = f"{vname}_{lang}_{theme}"
                    if only and only not in tag: continue
                    ctx = br.new_context(color_scheme=theme, **vopt)
                    pg = ctx.new_page()
                    errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                    pg.goto(f"{BASE}/index.html")
                    pg.evaluate("([l,t])=>{localStorage.clear();localStorage.setItem('ahp6-theme',JSON.stringify(t));localStorage.setItem('ahp6-draft',JSON.stringify({ans:Array(15).fill(null),e:null,lang:l}))}", [lang, theme])
                    pg.reload(); pg.wait_for_timeout(2500)
                    pg.screenshot(path=str(OUT / f"{tag}_1_start.png"))
                    pg.click("#exp button >> nth=2"); pg.click("#startBtn")
                    pg.wait_for_timeout(400)
                    pg.click(".meter button >> nth=2"); pg.wait_for_timeout(1800)
                    pg.screenshot(path=str(OUT / f"{tag}_2_question.png"))
                    pg.evaluate("([l,a])=>localStorage.setItem('ahp6-draft',JSON.stringify({ans:a,e:2,lang:l}))", [lang, ANS])
                    pg.reload(); pg.wait_for_timeout(1500)
                    pg.click("#startBtn"); pg.wait_for_timeout(1200)
                    pg.screenshot(path=str(OUT / f"{tag}_3_review.png"), full_page=True)
                    pg.click("#submitBtn"); pg.wait_for_selector(".check, .alert.err", timeout=30000); pg.wait_for_timeout(1500)
                    pg.screenshot(path=str(OUT / f"{tag}_4_sent.png"))
                    # horizontal overflow and font checks
                    ov = pg.evaluate("document.documentElement.scrollWidth-innerWidth")
                    font = pg.evaluate("document.fonts.check('800 16px Cairo')")
                    gl = pg.evaluate("!document.documentElement.classList.contains('nogl')")
                    if ov > 0: problems.append(f"{tag}: horizontal overflow {ov}px")
                    if not font: problems.append(f"{tag}: Cairo not loaded")
                    if not gl: problems.append(f"{tag}: WebGL scene not shown")
                    if errs: problems.append(f"{tag}: console errors {errs[:3]}")
                    ctx.close()
        br.close()
    print("\n".join(problems) or "no problems found")


if __name__ == "__main__":
    run(sys.argv[3] if len(sys.argv) > 3 else None)
