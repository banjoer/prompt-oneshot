# LLM Speedometer — Synthetic Streaming Benchmark Lab

**Difficulty:** Extreme  |  **Stack:** HTML/CSS/JS (single file)  |  **Estimated time:** 8+ h

## The Problem

Teams choosing between local inference setups — different engines, quantizations, or prompt designs — argue from vibes: "it feels faster" without numbers for time-to-first-token, per-token latency, or throughput, and without seeing stutters as they happen. Real benchmarking harnesses demand GPU boxes, model servers, and network plumbing just to learn the methodology. Build a self-contained lab that teaches and practices the real measurement discipline with zero backend: a deterministic synthetic streaming engine (configurable throughput, latency, jitter, stutters, prompt-size effects) plus a genuine measurement harness that times what actually renders, charts live speed on hand-rolled canvas, and saves comparison profiles locally — so anyone can run, compare, and export benchmark runs from a double-clicked file.

## Requirements

1. Deliver a single self-contained `speedometer.html` file using only vanilla HTML/CSS/JS. It must run when opened directly from disk (`file://`) in a modern browser; no server, no network calls of any kind (`fetch`, XHR, WebSocket, beacons), no CDN, no libraries.
2. Implement a **deterministic synthetic streaming engine**: given a config `{ baseTps, ttftMs, jitterMs, stutterEveryN, stutterMs, promptSizeEffectMsPerToken, seed }`, it emits a scripted token stream (pseudo-word tokens from a seeded PRNG — state the PRNG, e.g. mulberry32, in a comment) where the first token arrives after `ttftMs + promptTokens × promptSizeEffectMsPerToken`, subsequent tokens arrive at `1000 / baseTps` ± uniform jitter, and every Nth token stalls an extra `stutterMs`. Same seed + same config must reproduce the identical timing sequence.
3. Implement a **real measurement harness** around the engine: drive the stream with `performance.now()` timestamps captured per emitted token, and compute from observed times only (never echo the config back as results) — **TTFT** (start → first token, ms), **TPOT** (mean ms per completion token excluding the first), **TPS** (completion tokens ÷ decoding seconds), plus **prompt / completion / total token counts** using an inline-defined whitespace tokenizer (`text.split(/\s+/).filter(Boolean)` or equivalent, stated in a comment and applied consistently to the prompt box and the generated stream).
4. Provide a prompt input (textarea with a default sample prompt), a token-budget control (e.g. 32–512 completion tokens), a Run button, a live **streaming output pane** that appends tokens as they arrive, and a Cancel button that aborts mid-run cleanly (timers cleared, partial run marked cancelled and excluded from history, UI re-armed for the next run).
5. Render a **live speed graph** on a hand-rolled `<canvas>` 2D chart (your own axis/scale/plot code — no chart library): instantaneous tokens/sec sampled per 250 ms window, updating during the run, plus a marker line or annotation for TTFT. Axes are labelled, the chart rescales to the run's peak, and resizing the window repaints without losing the current run's data.
6. Show a **results panel** per finished run with TTFT, TPOT, TPS, token counts, wall-clock duration, and engine/preset name; append each finished run to a **run-history table** (newest first: time, preset, prompt tokens, completion tokens, TTFT, TPOT, TPS) backed by `localStorage`. History persists across reloads; corrupt stored values fall back to empty history without crashing.
7. Provide an **engine preset switcher** with at least three built-in simulated profiles that produce visibly different latency curves (e.g. `llama-sim-Q4` high TPS / moderate TTFT, `ollama-sim-Q8` lower TPS / low jitter, `vllm-sim` bursty high TPS with periodic stutters) plus a custom-config editor exposing all engine parameters with numeric validation (reject non-positive TPS/budget, negative latencies, with inline messages keeping old values).
8. Provide a **comparison view**: the user can pin/save up to N runs as named profiles, and a comparison table shows their metrics side by side with the best TPS highlighted and deltas (Δ%) versus the baseline (first pinned) profile. Saved profiles persist in `localStorage` and survive reloads.
9. Provide **export/import of profiles** as a JSON file (download via `Blob` + `<a download>`, restore via `<input type="file">` + `FileReader`); importing malformed JSON or a wrong schema is rejected with an inline error and never wipes existing profiles. Include a corrupt-state recovery path: a "Reset lab data" control (with native `confirm()`) that clears stored runs/profiles and restores the built-in presets.
10. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 09:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `speedometer.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts, no images, no build step, no chart libraries — all charts hand-drawn on `<canvas>`.
- Standard browser APIs only: DOM, `<canvas>` 2D, `performance.now()`, `setTimeout`/`requestAnimationFrame`, `localStorage`, `JSON`, `Blob`/`FileReader` for export/import. No network of any kind; must run fully offline from `file://`.
- All reported metrics must be measured from observed timestamps, never copied from engine config. Tokenizer must be defined inline and used consistently everywhere.
- Storage is `localStorage` (runs + saved profiles) plus JSON-file export/import — no IndexedDB, no cookies, no backend.
- Must stay responsive during a 512-token run: streaming pane and live chart update without freezing the controls; Cancel always re-arms the UI within one tick.

## Sample Data / Inputs

Built-in preset profiles (ship these defaults in code):

```json
[
  { "name": "llama-sim-Q4", "baseTps": 42, "ttftMs": 320, "jitterMs": 6, "stutterEveryN": 0, "stutterMs": 0, "promptSizeEffectMsPerToken": 1.2 },
  { "name": "ollama-sim-Q8", "baseTps": 24, "ttftMs": 480, "jitterMs": 3, "stutterEveryN": 0, "stutterMs": 0, "promptSizeEffectMsPerToken": 2.0 }
]
```

Example measurement table the harness should be able to reproduce in shape (illustrative — real numbers are measured, not copied):

```
preset          prompt_tok  compl_tok  TTFT(ms)  TPOT(ms)  TPS
llama-sim-Q4    18          128        ~340      ~24       ~41
ollama-sim-Q8   18          128        ~516      ~42       ~23
```

Default sample prompt (pre-filled in the textarea):

```
Explain why time-to-first-token matters for interactive chat, in exactly three short sentences.
```

Deterministic check: running the same preset + same seed + same prompt twice must report TTFT within ±15% and identical token counts both times.

## Deliverable

- One file: `speedometer.html`
- Run: open `speedometer.html` in any modern browser (double-click it, or `File → Open`). No install, no server. Disconnect from the network to verify self-containment.

## Done When

- [ ] The page opens from `file://` fully offline with zero network requests and no console errors, showing prompt box, preset switcher, Run/Cancel, streaming pane, canvas chart, results, history, and comparison sections.
- [ ] Pressing Run streams visible tokens into the output pane while the canvas speed graph plots live tokens/sec with labelled axes and a TTFT marker; results show TTFT, TPOT, TPS, and prompt/completion/total counts.
- [ ] Reported TPS ≈ completion tokens ÷ measured decoding seconds (spot-check with a stopwatch within 20%); TTFT grows visibly when the prompt is made 10× longer (prompt-size effect).
- [ ] Switching presets produces visibly different curves/numbers (fast smooth vs. slow steady vs. bursty with stutters); custom-config edits with invalid values are rejected inline and keep old values.
- [ ] Same preset + seed run twice gives identical token counts and TTFT within ±15%; Cancel mid-run stops all timers, marks the run cancelled, and excludes it from history.
- [ ] Reloading restores run history and saved comparison profiles; pinning two runs shows a side-by-side table with best-TPS highlight and Δ% vs baseline.
- [ ] Export downloads a JSON file of profiles; importing it back (or a hand-edited copy) restores them; importing garbage shows an inline error and keeps existing data intact.
- [ ] Hand-corrupting the `localStorage` keys to `garbage` and reloading yields an empty-but-working lab (presets intact), and "Reset lab data" restores defaults after confirmation.
- [ ] A 512-token run keeps controls responsive and Cancel re-arms the UI; the sign-off (date/time + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Per-token latency histogram (p50/p95/max) drawn on a second hand-rolled canvas from the same measured timestamps.
- Prompt-length sweep: run the same preset over 4 prompt sizes automatically and plot TTFT vs prompt tokens.
- A "challenge mode" that hides the config and asks the user to identify which preset ran from the live curve alone.
