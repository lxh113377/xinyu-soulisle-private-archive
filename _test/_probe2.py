import sys
sys.path.insert(0, '_test')
from playwright.sync_api import sync_playwright
from browser_engine import launch

with sync_playwright() as pw:
    b, face = launch(pw, args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'], label='probe2')
    for w, h in ((360, 640), (390, 844)):
        ctx = b.new_context(viewport={'width': w, 'height': h}, has_touch=True, is_mobile=True)
        p = ctx.new_page()
        p.goto('http://127.0.0.1:8123/', wait_until='load')
        p.wait_for_timeout(1500)
        p.evaluate("document.getElementById('face-hud').hidden = false")
        p.wait_for_timeout(300)
        r = p.evaluate("""() => {
            const b = document.getElementById('btn-face-close');
            const cs = getComputedStyle(b);
            const r = b.getBoundingClientRect();
            return {w: Math.round(r.width), h: Math.round(r.height), minH: cs.minHeight,
                    pad: cs.padding, fs: cs.fontSize, box: cs.boxSizing, disp: cs.display,
                    lh: cs.lineHeight, border: cs.borderTopWidth};
        }""")
        print(w, h, r)
        ctx.close()
    b.close()
