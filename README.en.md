# 心屿 SoulIsle (English)

> An AI emotional-companion web app: a scroll-driven **3D emotion narrative** (WebGL + GSAP) carrying a real empathy pipeline — emotion recognition → empathetic strategy → online LLM generation → emotion visualization (a particle "star mist" that changes color and lights up per sentence) → persistent memory. Not another chat-box wrapper.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) · [中文 README](README.md)

## Highlights

- **Dual-path emotion engine** — local lexicon fast path (zero latency, offline-capable) + LLM precise path; disagreements resolve to the LLM, LLM failure falls back to the lexicon. Reproducible on a 73-case eval set: **98.6% accuracy**, verified identically on both JS and Java engines.
- **Crisis-first interception** — crisis keywords take top priority, bypass the LLM entirely, and route to a helpline (recall 6/6). None of the benchmarked open-source companions (LobeChat / Open-LLM-VTuber / SillyTavern) ship this natively.
- **3D emotion star mist** — Three.js particle nebula; each message lights stars in its detected emotion color (primary n + secondary n/2), pixel-verified by regression scripts.
- **Graceful degradation, honestly labeled** — no WebGL → CSS gradient; no LLM → offline templates, always shown as such in the UI (never disguised as online AI).
- **Zero-build frontend + three backend shapes** — static hosting (Cloudflare Pages / Tencent CloudBase), a single Spring Boot fat jar (JDK 17), or Docker (build & restart-persistence tested). Secrets live only in environment variables / platform secret stores: **zero keys in frontend code, git history, or images**.
- **Memory (J4)** — localStorage by default; server-side persistence (H2 file / MySQL) optional per deployment.

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for toolchain specifics (JDK 17 required) and the four project red lines; [.env.example](.env.example) for all variables.

## Verification

18 always-on regression scripts under `_test/` (sync guard, dual-engine consistency, pixel-level two-color checks, offline-fallback browser suite, key-leak scan) + GitHub Actions CI (`ci.yml`).

## Disclaimer

For research and companionship purposes only; **not** medical diagnosis or psychotherapy. In emergencies contact local services or the 24h helpline **12356** (China).

## License

[MIT](LICENSE) © 2026 心屿 SoulIsle team. Entry for the 2026 iCAN AI Innovation Challenge (submission deadline 2026-09-30).
