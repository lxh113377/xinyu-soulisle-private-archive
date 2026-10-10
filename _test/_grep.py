import re, io
t = io.open('src/vendor/mediapipe/vision_bundle.js', encoding='utf-8', errors='replace').read()
pats = ['createObjectURL', 'Blob(', 'script', 'import(', '.wasm', 'locateFile', 'text/javascript']
for pat in pats:
    idx = [m.start() for m in re.finditer(re.escape(pat), t)]
    print(pat, len(idx))
    if idx:
        print('   ', t[max(0, idx[0] - 160):idx[0] + 200].replace('\n', ' ')[:320])
