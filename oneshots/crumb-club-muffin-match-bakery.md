# Crumb Club — Muffin Match Bakery

**Difficulty:** medium  |  **Stack:** HTML/CSS/JavaScript (single file, Canvas 2D)  |  **Estimated time:** 2–3 h

## The Problem

A waiting-room tablet with no Wi-Fi needs a game a five-year-old can start
alone and a ten-year-old will still replay. Most kid games fail that test in
predictable ways: tiny targets, reading-heavy rules, a timer that ends the fun,
or a lost round that feels like punishment. Crumb Club is a picture-only bakery
puzzle: a customer's order card shows the toppings the muffin needs, and the
child drags big fruit pieces onto the muffin until it matches. Wrong pieces
bounce back with a giggle instead of a penalty, and a gentle hint appears only
when the child is stuck. It has to fill the whole screen, survive rotation, and
store progress locally so a closed tab never costs a child her stickers.

## Requirements

1. **One-file deliverable:** the complete game — markup, CSS, and JavaScript —
   lives in a single `.html` file that runs by double-clicking it (`file://`)
   in a current mobile or desktop browser, with no server, build, install, or
   console errors.
2. **True full-viewport canvas:** exactly one `<canvas>` fills the visual
   viewport (`position: fixed; inset: 0; width: 100%; height: 100%`; no page
   scrolling, no fixed game box, no letterboxed strip). Size the backing store
   with `devicePixelRatio` (capped at 3), and recompute on `resize`,
   `orientationchange`, and `visualViewport` changes so the canvas never looks
   stretched; the game must be fully usable at 320 × 480 CSS px and in both
   portrait and landscape.
3. **Responsive composition:** portrait and landscape are genuinely different
   layouts, not the same scene squeezed. In portrait the order card sits above
   the muffin and the topping tray runs along the bottom; in landscape the
   order card sits on the left, the muffin in the middle, and the tray on the
   right. Every interactive control stays at least 16 CSS px inside the
   viewport edges (and inside safe-area insets where the browser exposes them).
4. **Canvas-drawn menus only:** title, level select, how-to-play, pause,
   level-complete, and an about line are all rendered inside the canvas and
   driven by the same game state machine. There are no HTML buttons, links, or
   static page chrome; the visible page is only the canvas. Every menu button
   has a hit area of at least 64 × 64 CSS px and supports tap, click, and the
   same pointer path used for play.
5. **Touch-first dragging:** toppings move from the tray to the muffin through
   Pointer Events with `setPointerCapture`, working identically for finger,
   stylus, and mouse. Only one topping may be dragged at a time; a second
   pointer is ignored until the first drag ends. Dragging must not scroll or
   zoom the page (`touch-action: none`, `user-select: none`, no overscroll).
   Tapping a topping then tapping an empty muffin slot is an equivalent
   fallback that performs the same placement.
6. **Four toppings, always available:** the tray offers strawberry, blueberry,
   banana slice, and star sprinkle (Sample Data gives their shapes and
   colours). Supply is infinite, the tray is visible at all times during play,
   and each topping's touch target is at least 64 CSS px even on the smallest
   supported screen.
7. **Forgiving placement:** dropping a topping that the current order still
   needs snaps it into any empty slot with a soft pop. Dropping a topping the
   order no longer needs (or dropping outside the muffin) animates it back to
   its tray with a wobble and a gentle "boop" — progress, slots, and the
   customer's expression are unchanged. Tapping a filled slot returns that
   topping to the tray. Wrong drops are never penalized and never block
   progress.
8. **Order matching:** a level defines a slot count; the slots are drawn around
   the muffin's frosting arc. The order card shows the required toppings as
   pictures with numeric counts (for example, two strawberry icons and one
   blueberry icon), never sentences. The order is satisfied only when the
   multiset of placed toppings exactly equals the recipe and all slots are
   filled. A Serve button activates only at that moment; tapping it early
   makes the muffin wiggle and is otherwise harmless.
9. **Level flow:** five levels, each with four authored orders from the Sample
   Data table, all served in the listed order. Levels 1–2 display faint ghost
   silhouettes of the required topping in each empty slot; levels 3–5 show no
   ghosts and rely on the order card alone. Serving an order triggers a short
   confetti burst and slides in the next order. Serving a level's fourth order
   shows a level-complete screen with a large collectible sticker, then unlocks
   the next level. Level select shows every level, a lock on unavailable ones,
   and the sticker earned on completed ones.
10. **No fail state:** there is no timer, no lives, no score loss, and no way
    for a customer to leave. If no correct placement has happened for 6
    seconds, pulse the tray topping that the current order still needs most
    (once per idle period) as a hint. Pause is reachable at any time through a
    persistent canvas pause button, and the pause overlay offers Resume,
    Restart level, Home, and a sound toggle. Restart level returns to that
    level's first order with an empty muffin; Home keeps saved progress.
11. **Durable progress:** persist the highest unlocked level, the earned
    sticker for each completed level, the current level and order index, and
    the sound preference in `localStorage` under versioned keys (for example,
    `crumbclub.progress.v1` and `crumbclub.sound.v1`). Saving happens after
    each served order, so reloading mid-level resumes that level at the same
    order with an empty muffin. If storage is unavailable (private mode), the
    game still runs and falls back to in-memory progress without crashing.
12. **Optional synthesized audio:** any sound is generated at runtime with the
    Web Audio API — no audio files. The audio context is created or resumed
    only after the first user gesture, a speaker button on the title screen and
    in the pause overlay mutes/unmutes it, the choice persists, and the game is
    fully playable with sound off. Muting produces complete silence.
13. **Kid-facing visual quality:** the bakery scene (wall, counter, plate,
    muffin, customer faces) is drawn with vector canvas primitives and fills
    the screen. Toppings are distinguishable by both shape and colour. All
    animation is delta-time based so it looks the same at 60, 90, or 120 Hz,
    and the game should stay smooth on a mid-range phone. No images, emoji,
    icon fonts, external fonts, or downloaded assets are used anywhere.
14. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it —
    a small visible footer on the title screen and an about line on the pause
    overlay, plus a header comment in the source.

## Constraints

- One `.html` file. All CSS in `<style>`, all JavaScript in `<script>`. No
  frameworks, libraries, bundlers, CDNs, or build step.
- Standard browser APIs only: Canvas 2D, Pointer Events, Web Audio,
  `localStorage`, `requestAnimationFrame`. No network calls of any kind.
- No external assets: no images, audio files, fonts, sprites, or emoji. All
  graphics are canvas paths, arcs, gradients, and text drawn with a system
  font stack; all audio is synthesized.
- The game must run from `file://` with a clean console. Do not request device
  motion, camera, microphone, or notification permissions.
- Menus are canvas content, not DOM overlays. A single visually hidden
  `aria-live` region or canvas `aria-label` for screen readers is allowed.
- The canvas must handle DPR correctly: pointer coordinates converted from CSS
  px to the game's coordinate space, no half-pixel blur, no touch offset when
  the page is zoomed.
- Persist only small JSON values in `localStorage`; never store images or
  unbounded logs.
- Designed for ages 5–10: big targets, forgiving interactions, no reading-heavy
  instructions, no ads, no scary content, no failure that ends the session.

## Sample Data / Inputs

### Toppings

| id | Name | Shape | Main colour | Detail |
|---|---|---|---|---|
| `strawberry` | Strawberry | rounded berry with a leaf | `#E8455F` | pale seed dots |
| `blueberry` | Blueberry | circle with a tiny star crown | `#5B6CE0` | lighter highlight |
| `banana` | Banana slice | ring with a pale centre | `#F5C542` | three seed dots |
| `star` | Star sprinkle | five-point star | `#9B5DE5` | lighter centre |

Draw all four at any size from canvas paths so they stay crisp when scaled.

### Levels and orders

Each row is one order, served in this exact sequence. Counts always sum to the
level's slot count.

| Level | Slots | Ghost hints | Orders |
|:---:|:---:|:---:|---|
| 1 | 2 | yes | `2 strawberry` · `1 blueberry + 1 strawberry` · `2 blueberry` · `1 strawberry + 1 blueberry` |
| 2 | 3 | yes | `2 strawberry + 1 blueberry` · `1 banana + 2 blueberry` · `2 banana + 1 strawberry` · `1 strawberry + 1 blueberry + 1 banana` |
| 3 | 3 | no | `2 star + 1 blueberry` · `1 strawberry + 1 banana + 1 star` · `2 strawberry + 1 banana` · `1 blueberry + 2 star` |
| 4 | 4 | no | `2 strawberry + 2 blueberry` · `1 strawberry + 1 blueberry + 1 banana + 1 star` · `2 banana + 1 strawberry + 1 star` · `2 star + 2 blueberry` |
| 5 | 5 | no | `2 strawberry + 2 banana + 1 star` · `2 blueberry + 2 star + 1 strawberry` · `2 banana + 1 strawberry + 1 blueberry + 1 star` · `2 strawberry + 1 blueberry + 1 banana + 1 star` |

### Slot layout

Slots sit on the frosting arc, spread symmetrically by fraction of the muffin
width: 2 slots at `-0.22, +0.22`; 3 at `-0.28, 0, +0.28`; 4 at
`-0.33, -0.11, +0.11, +0.33`; 5 at `-0.36, -0.18, 0, +0.18, +0.36`. Shuffle
nothing: the recipe is order-independent, so any needed topping fits any empty
slot.

### Tuning

| Constant | Value |
|---|---|
| Idle hint delay | 6 s |
| Wrong-drop return animation | 220–280 ms ease-out |
| Order transition | 500 ms slide |
| Confetti burst | 1.2 s |
| Maximum backing-store scale | 3× DPR |
| Minimum touch target | 64 CSS px |

## Deliverable

- Exactly one file: `crumb-club-muffin-match-bakery.html`
- Run it by opening the file directly in a browser:
  - macOS: `open crumb-club-muffin-match-bakery.html`
  - Linux: `xdg-open crumb-club-muffin-match-bakery.html`
  - Windows: `start crumb-club-muffin-match-bakery.html`
- No other command, server, or dependency is required.

## Done When

- [ ] Opening the file shows a full-screen title screen with a big Play button,
      How-to-play, a speaker toggle, and the sign-off footer — no console
      errors, no scrollbars, no HTML buttons.
- [ ] Rotating a phone or resizing the window re-lays out the bakery, order
      card, muffin, and tray with no stretch, clipping, or lost touch accuracy.
- [ ] Dragging a correct topping with a finger or mouse snaps it into an empty
      slot; the same placement also works by tapping the topping and then the
      slot.
- [ ] Dragging an unneeded topping or dropping outside the muffin returns it
      with a wobble, changes nothing, and can be repeated indefinitely.
- [ ] Tapping a filled slot removes that topping and Serve becomes inactive
      again if the order is no longer complete.
- [ ] Level 1 shows ghost silhouettes in empty slots; level 3 shows none, yet
      the order card alone is enough to finish it.
- [ ] Completing four orders shows the sticker screen, unlocks the next level,
      and level select displays the earned sticker and the correct locks.
- [ ] Serving an order, quitting, and reloading resumes the same level at the
      next order with an empty muffin; unlocked levels and stickers survive.
- [ ] Pause opens from play, Resume returns exactly where the game was,
      Restart level begins that level's first order, and Home returns to the
      title without losing saved progress.
- [ ] No sound plays before the first tap; the speaker toggle silences
      everything immediately and the choice survives a reload.
- [ ] Leaving the game idle for six seconds pulses a helpful topping, then does
      not nag again until the child interacts.
- [ ] The title screen shows the production date/time and model/author, and the
      same information appears in the source header comment.

## Stretch Goals (optional)

- Add a sticker book screen that shows every earned sticker at a large size,
  reachable from the title screen.
- Add a Free Bake mode where the child decorates a muffin with no order, with a
  "clear plate" button and no persistence beyond the session.
- Add an optional colour-blind aid that draws a small shape badge on each
  topping's tray label.
