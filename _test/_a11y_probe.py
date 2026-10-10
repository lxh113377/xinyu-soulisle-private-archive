import sys, threading, json, mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path('.').resolve()
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('application/wasm', '.wasm')


class H(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split('?', 1)[0]
        if p.startswith('/_test/') or p.startswith('/src/'):
            return super().translate_path(path)
        rel = p.lstrip('/')
        base = ROOT / 'deploy' / 'xinyu'
        return str(base / rel) if rel else str(base / 'index.html')

    def log_message(self, *a, **k):
        pass


srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
sys.path.insert(0, '_test')
from playwright.sync_api import sync_playwright
from browser_engine import launch

AXE = (ROOT / '_test' / 'vendor' / 'axe-core-4.10.2.min.js').read_text('utf-8')
with sync_playwright() as pw:
    b, face = launch(pw, args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'], label='a11yprobe')
    ctx = b.new_context(permissions=['camera'], viewport={'width': 1280, 'height': 900})
    p = ctx.new_page()
    p.goto('http://127.0.0.1:%d/index.html' % port, wait_until='load')
    p.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state!=='boot'", timeout=60000)
    p.evaluate("document.getElementById('face-hud').hidden = false")
    p.wait_for_timeout(500)
    p.add_script_tag(content=AXE)
    res = p.evaluate("""async () => {
        const r = await axe.run(document, {resultTypes:['violations']});
        const out = [];
        for (const v of r.violations) {
            for (const n of v.nodes) {
                out.push(v.id + ' | ' + n.target.join(' ') + ' | ' + String(n.failureSummary || '').replace(/\\s+/g, ' ').slice(0, 160));
            }
        }
        return out;
    }""")
    for v in res:
        print(v)

    b.close()
srv.shutdown()
