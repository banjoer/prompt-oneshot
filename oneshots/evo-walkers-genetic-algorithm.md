# Evo Walkers — 2D Genetic Algorithm

**Difficulty:** Extreme  |  **Stack:** HTML/CSS/JS (vanilla, single file, canvas)  |  **Estimated time:** 8+ hours

## The Problem

Genetic algorithms are usually explained as abstract pseudocode — selection, crossover, mutation — while the intuition only lands when you watch blind, twitching machines learn to walk. Teachers demoing evolution, students grasping fitness landscapes, and curious hackers all want the same thing: a cinematic little world where twenty lumpy creatures flop, crawl, and eventually stride to the right, generation after generation, with the champion glowing green and the camera chasing it. Build that world: a self-contained 2D physics-plus-evolution simulation on canvas that runs at 60 fps, needs no server, and makes natural selection visible.

## Requirements

1. Deliver a single self-contained `evocreatures.html` file with all markup, styles, and logic embedded. It must work when opened directly from disk (`file://`) in a modern browser; no server, no build step, no libraries.
2. Render the scene on an HTML5 Canvas with a dark neon theme: page/sky background `#0d1117`, faint grid lines, and glowing elements (use `shadowBlur`/`shadowColor` sparingly for the leader only, to protect frame rate). The layout overlays a minimal glassmorphism HUD panel on top of the canvas.
3. **Creatures:** each creature is a system of 4–6 point-mass nodes connected by spring-like muscles rendered as line segments. The current generation leader is highlighted in vibrant neon green/gold with a glow; all other creatures render semi-transparent white/blue. Nodes render as small circles; muscles as lines whose width or brightness reflects current contraction.
4. **Environment:** a flat ground line with distance markers labelled `10m`, `20m`, `50m`, `100m` (and further as needed), plus two or three small hills/obstacles the creatures must flop over or around. Ground contact uses friction; airborne nodes fall under gravity.
5. **Camera:** a smooth X-axis auto-camera that follows the current leader's X position (lerped each frame, never snapping), with the Y axis fixed. Distance markers and hills must scroll correctly past as the leader advances.
6. **Physics:** custom per-frame particle physics — gravity pulling nodes down, ground collision with friction, and muscles modelled as springs whose rest length pulses along a sine wave each frame. Integration uses a fixed timestep accumulator so simulation speed is frame-rate independent.
7. **Genome:** each muscle carries genes for sine-pulse `phase`, `frequency`, and `amplitude` (plus base rest length and spring stiffness). The genome is a plain data structure that fully determines a creature's motion; identical genomes on identical terrain must behave identically.
8. **Evolution loop:** simulate a population of exactly 20 creatures simultaneously for 12 seconds per generation, with early transition to the next generation if every creature's forward velocity stays near zero for a sustained stall window (e.g. ~2 s). Fitness is each creature's maximum X distance reached. The top 20% (4 creatures) become parents: children inherit averaged/copied parental genes with slight random mutations to phase, frequency, and amplitude, plus occasional structural mutation; the single best genome is preserved verbatim (elitism) so best distance never regresses by construction.
9. **HUD dashboard:** a glassmorphism overlay panel showing live `Generation #`, `Best Distance` (all-time record), a countdown timer for the current generation, the current leader's distance, and a micro progress chart (small canvas or SVG in the corner) plotting best-distance-per-generation over time.
10. **Viewer controls:** a time-acceleration control with steps `1x`, `2x`, `5x`, `10x` that scales simulated physics time without breaking the fixed timestep, plus three buttons: `Reset` (restart evolution from fresh random creatures, clearing records), `Generate New Creatures` (randomize the current population in place without clearing the all-time record), and `Next Generation` (immediately end the current generation and breed from current fitness).
11. **Performance:** the simulation must sustain ~60 fps at 1x on a typical laptop for 20 creatures; keep per-frame allocations low, avoid layout thrash, and pause the loop (via `requestAnimationFrame` gating or `visibilitychange`) when the tab is hidden.
12. **Robustness:** creatures that fall through, get stuck inside a hill, or produce `NaN` positions must be detected and respawned/clamped rather than freezing the run; the generation timer must always advance to the next generation even if the physics misbehaves.
13. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer or HUD corner), the date and time the solution was produced and the model/author that produced it (e.g. `Evolved 2026-10-29 14:32 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `evocreatures.html`. No external CSS/JS files, no CDNs, no frameworks, no images, no web fonts, no build step.
- Vanilla browser APIs only: Canvas 2D, `requestAnimationFrame`, DOM. No network calls of any kind.
- No persistence required; if any state is stored, use in-memory variables only (localStorage is allowed but must degrade gracefully under `file://`).
- Physics and evolution parameters (population 20, generation 12 s, top-20% selection, speed steps 1/2/5/10x) are constants in code, easily adjustable at the top of the script.
- Must run by double-clicking the file (`file://`) in current Chrome/Firefox/Edge/Safari.

## Sample Data / Inputs

No input files. Example genome JSON (one creature with 4 nodes, 5 muscles — implementation may vary but every muscle must carry phase/frequency/amplitude):

```json
{
  "nodes": [
    { "x": 0, "y": 12, "mass": 1.0 },
    { "x": 14, "y": 12, "mass": 1.0 },
    { "x": 7, "y": 26, "mass": 1.2 },
    { "x": 20, "y": 24, "mass": 0.9 }
  ],
  "muscles": [
    { "a": 0, "b": 1, "restLength": 14, "stiffness": 0.32, "phase": 0.0, "frequency": 1.6, "amplitude": 4.5 },
    { "a": 0, "b": 2, "restLength": 16, "stiffness": 0.30, "phase": 1.1, "frequency": 1.6, "amplitude": 5.0 },
    { "a": 1, "b": 2, "restLength": 15, "stiffness": 0.30, "phase": 2.4, "frequency": 2.1, "amplitude": 4.0 },
    { "a": 1, "b": 3, "restLength": 12, "stiffness": 0.34, "frequency": 1.9, "phase": 0.6, "amplitude": 3.5 },
    { "a": 2, "b": 3, "restLength": 13, "stiffness": 0.30, "frequency": 1.6, "phase": 3.6, "amplitude": 4.2 }
  ]
}
```

Mutation rule of thumb: on breeding, perturb each inherited `phase` by ±0.3 rad, `frequency` by ±10%, and `amplitude` by ±15%, clamped to sane ranges so motion stays bounded.

## Deliverable

- One file: `evocreatures.html`
- Run: open `evocreatures.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` with the dark `#0d1117` scene, grid, ground with 10/20/50/100m markers, hills, and 20 visible creatures moving without console errors.
- [ ] The leader glows green/gold while the rest render translucent white/blue, and the camera smoothly tracks the leader along X.
- [ ] Creatures locomote via visibly pulsing muscles (gravity + friction + springs evident: they flop, grip, and push rather than sliding rigidly).
- [ ] Generations advance every 12 s (or earlier on a genuine full-population stall), the generation counter increments, and the new population visibly inherits traits from the previous leaders.
- [ ] Fitness equals max X: the recorded best distance never decreases across generations, and the mini progress chart grows generation by generation.
- [ ] The HUD shows generation number, best distance, live countdown, and the progress chart simultaneously and updates every frame/second as appropriate.
- [ ] Speed steps 1x/2x/5x/10x each visibly accelerate evolution, and `Reset`, `Generate New Creatures`, and `Next Generation` each perform their described action.
- [ ] Animation stays smooth (~60 fps at 1x) with no tab-freeze; hiding the tab pauses work and returning resumes cleanly.
- [ ] Leaving the sim running for 5+ generations produces creatures that travel farther on average than generation 1 (visible learning trend, not guaranteed speed).
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Click a creature to pin/follow it instead of the leader, with its genome shown read-only in the HUD.
- Export/import the champion genome as JSON via a textarea or file download.
- Toggleable terrain presets (flat sprint vs. hilly scramble) selectable from the HUD.
