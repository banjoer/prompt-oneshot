# Rigsmith — SVG Character Factory

A single-file, browser-only character factory: a parametric SVG rig drives three archetypes, nine body clips, six expression clips, a live 15-tile animation rail, and a transparent PNG + TexturePacker "JSON Array" atlas export.

## Run

Double-click `index.html` (no server, build step, package manager, or network access). For a phone on the same LAN, optionally serve this folder:

```bash
python3 -m http.server 8000
```

and open `http://<computer-lan-ip>:8000/index.html`. The app itself makes no network requests.

## What is inside

- One `index.html` with embedded CSS and vanilla JS.
- SVG stage and 15 SVG gallery tiles; Canvas 2D is used only to rasterize the exported atlas and preview it.
- Seeded mulberry32 decorations, deterministic pose/keyframe library, two-bone leg/foreleg IK, deterministic tail/ear spring-damper follow-through.
- Full / Body / Face camera presets, wheel/drag/pinch zoom-pan, bone overlay, ground + contact-shadow overlay.
- Export at 64/128/256 px cells, 4–16 body frames, fixed 4 expression frames, transparent background, optional ground shadow, safe-canvas-limit detection, progress, preview, PNG/JSON downloads and mobile open-in-tab fallbacks.
- localStorage persistence for spec, seed, selected clip, and zoom preset.

## Sign-off

Produced **2026-11-15 22:46 UTC** by **DeepSeek V4.1 Flash**.

The same sign-off is repeated in the header comment and always-visible footer of `index.html`, and stamped into exported JSON as `meta.generator` + `meta.generatedAt`.
