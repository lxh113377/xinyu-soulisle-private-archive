# 心屿 SoulIsle (English)

> An AI emotional-companion web app: a scroll-driven **3D emotion narrative** (WebGL + GSAP) carrying a real empathy pipeline — emotion recognition → empathetic strategy → online LLM generation → emotion visualization (a particle "star mist" that changes color and lights up per sentence) → persistent memory. Not another chat-box wrapper.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) · [中文 README](README.md)

## Highlights

- **Dual-path emotion engine** — local lexicon fast path (zero latency, offline-capable) + LLM precise path; disagreements resolve to the LLM, LLM failure falls back to the lexicon. Reproducible on a 73-case eval set: **98.6% accuracy**, verified identically on both JS and Java engines.
- **Crisis-first interception** — crisis keywords take top priority, bypass the LLM entirely, and route to a helpline (recall 6/6). None of the benchmarked open-source companions (LobeChat / Open-LLM-VTuber / SillyTavern) ship this natively.
- **Backend-optional emotion classification (r20)** — with `cfg.emotionRemote === true` the empathy pipeline takes the server-side `/api/emotion` result (Java lexicon + LLM, item-for-item identical to the JS engine), which removes the "two sources of truth" left over from J3. Crisis keywords always short-circuit locally and never wait for the network; 404 / timeout / malformed response trips a circuit breaker and falls back to the local engine, and the UI labels the actual source (`情绪:后端`) instead of pretending to be online. Off by default on the public site on purpose — the Pages Function implements only `/api/chat`.
- **3D emotion star mist** — Three.js particle nebula; each message lights stars in its detected emotion color (primary n + secondary n/2), pixel-verified by regression scripts.
- **Graceful degradation, honestly labeled** — no WebGL → CSS gradient; no LLM → offline templates, always shown as such in the UI (never disguised as online AI).
- **Zero-build frontend + three backend shapes** — static hosting (Cloudflare Pages / Tencent CloudBase), a single Spring Boot fat jar (JDK 17), or Docker (build & restart-persistence tested). Secrets live only in environment variables / platform secret stores: **zero keys in frontend code, git history, or images**.
- **Memory (J4)** — localStorage by default; server-side persistence (H2 file / MySQL) optional per deployment.
- **Token-by-token streaming (SSE)** — `/api/chat` accepts an optional `stream:true`; the Pages Function and the Java service pass the upstream event stream straight through, and the UI renders as it arrives. Requests **without** the field are byte-for-byte the v1 contract. If a proxy can't stream (CloudBase), the client detects the content type and falls back to whole-response rendering — no half-written bubbles, no pretending.
- **Configurable empathy strategy** — personas, rules, classifier prompt, crisis script and per-emotion templates live in `src/data/emotion-strategy.js` as a pure JSON literal (single source of truth, alongside the lexicon SSOT). Adding an emotion = edit two data files, zero code changes; `strategy_check.py` fails if the pair drifts.
- **Provider-agnostic upstream** — `LLM_BASE / LLM_MODEL / LLM_KEY` (with `DEEPSEEK_*` kept as compatibility aliases) plus five one-click presets in the settings dialog.
- **Voice output** — replies can be read aloud via `speechSynthesis` (zh-CN, zero dependencies), alongside the existing voice input.
- **Long-session and mobile hygiene** — chat log is windowed (60 DOM nodes, expandable in batches), three responsive breakpoints, particle count scales down on small viewports (2600 desktop / 1800 tablet / 900 phone).

## Architecture

```
Browser (src/ or deploy/xinyu/)  —— same-origin HTTP ——▶
Spring Boot (server/): /api/health · /api/chat (v1-compatible contract)
                       /api/emotion (+/eval, dual-engine parity) · /api/memory/**
Serverless fallbacks: Cloudflare Pages Function / CloudBase cloud function (DeepSeek, OpenAI-compatible)
```

Design constraints: static pages are served **directly from `src/`** (zero-copy policy); the eval dataset is read from `_test/` (never duplicated into the jar).

## Quick start

```bash
python -m http.server 8123 --directory src     # frontend only
# or full stack (workdir = repo root):
java -jar server/target/soulisle-server.jar --server.port=8123
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for toolchain specifics (JDK 17 required) and the five project red lines; [.env.example](.env.example) for all variables; [ROADMAP.md](ROADMAP.md) for what we plan — and what we deliberately won't build.

## Verification

21 always-on regression scripts under `_test/` (sync guard, dual-engine parity, strategy/lexicon pairing, pixel-level two-color checks, offline-fallback browser suite, streaming contract, TTS / windowing / responsive guards, key-leak scan) + GitHub Actions CI: three jobs covering sync + eval + strategy + secret scan, Java build + lexicon-parity red line, and browser regression.

## Disclaimer

For research and companionship purposes only; **not** medical diagnosis or psychotherapy. In emergencies contact local services or the 24h helpline **12356** (China).

## License

[MIT](LICENSE) © 2026 心屿 SoulIsle team. Entry for the 2026 iCAN AI Innovation Challenge (submission deadline 2026-09-30).
