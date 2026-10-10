"""Admin page and the WhatsApp fallback screen (needs dev/mock_server.py running)."""
import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE="http://localhost:8765"; OUT=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parent.parent/"screenshots"); OUT.mkdir(exist_ok=True)
get=lambda p: urllib.request.urlopen(BASE+p).read()
SAMPLES=[[0,-1,-1,-1,-2,0,-1,-1,-1,0,-1,-1,0,-1,0],[-2,-1,1,0,-3,2,1,-1,0,-2,1,3,0,-1,2],[0]*15,[-1,-2,-1,-3,-2,-1,0,-2,-1,1,-1,0,-1,-1,0]]
with sync_playwright() as p:
    br=p.chromium.launch(channel="msedge",args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    get("/__reset")
    c=br.new_context(viewport={"width":1280,"height":800}); pg=c.new_page(); pg.goto(BASE+"/index.html")
    for n,a in enumerate(SAMPLES):
        pg.evaluate("([a,e])=>{localStorage.setItem('ahp6-draft',JSON.stringify({ans:a,e,lang:e%2?'ar':'en'}))}",[a,n]); pg.reload(); pg.click("#startBtn"); pg.click("#submitBtn"); pg.wait_for_selector(".check")
    c.close()
    for name,vp,theme,lang in [("desktop",{"width":1440,"height":900},"dark","ar"),("desktop",{"width":1440,"height":900},"light","en"),("phone",{"width":390,"height":844},"light","ar")]:
        c=br.new_context(viewport=vp,color_scheme=theme,device_scale_factor=2 if name=="phone" else 1); pg=c.new_page(); pg.goto(BASE+"/admin.html")
        pg.evaluate("([t,l])=>{localStorage.setItem('ahp6-theme',JSON.stringify(t));localStorage.setItem('ahp6-owner-lang',JSON.stringify(l));localStorage.setItem('ahp6-admin-key',JSON.stringify('devkey'))}",[theme,lang])
        pg.reload(); pg.wait_for_selector("table"); pg.click("tr.main >> nth=1"); pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT/f"admin_{name}_{lang}_{theme}.png"),full_page=True)
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); print(name,lang,theme,"overflow",ov)
        if name=="desktop" and theme=="dark":
            pg.evaluate("localStorage.removeItem('ahp6-admin-key')"); pg.reload(); pg.wait_for_selector("#keyIn"); pg.screenshot(path=str(OUT/"admin_signin.png"))
        c.close()
    get("/__fail?on=1")
    for lang,theme in [("ar","dark"),("en","light")]:
        c=br.new_context(viewport={"width":390,"height":844},color_scheme=theme,device_scale_factor=2,is_mobile=True,has_touch=True); pg=c.new_page(); pg.goto(BASE+"/index.html")
        pg.evaluate("([l])=>{localStorage.setItem('ahp6-draft',JSON.stringify({ans:[1,0,-1,2,0,1,0,-1,0,1,0,0,-2,0,1],e:1,lang:l}))}",[lang]); pg.reload(); pg.click("#startBtn"); pg.click("#submitBtn"); pg.wait_for_selector(".alert.err"); pg.wait_for_timeout(1200)
        pg.screenshot(path=str(OUT/f"phone_{lang}_{theme}_5_not_sent_fallback.png"),full_page=True); c.close()
    get("/__reset"); br.close()
