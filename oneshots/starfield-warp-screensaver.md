# Starfield Warp — Hyperspace Screensaver

**Difficulty:** easy  |  **Stack:** Java (Swing, JDK only)  |  **Estimated time:** 30–60 min

## The Problem

The starfield warp effect — hundreds of stars streaming outward from the
center of the screen as if the viewer were punching into hyperspace — is one
of the most iconic screensavers of the early PC era, and it's really just one
elegant idea: give each star a 3D position `(x, y, z)`, move it toward the
camera every frame, and project it onto the 2D screen with perspective
division. Stars near the camera appear large, bright, and fast; distant stars
are dim pinpricks. This challenge recreates that classic effect as a
standalone Swing application: a black window full of streaming stars with a
speed slider and a pause key, screensaver-style. It's a compact introduction
to game-loop timing with `javax.swing.Timer`, custom `paintComponent`
rendering, and basic 3D projection — with a genuinely satisfying visual
payoff.

## Requirements

1. The application is a single Swing window, **800×600** by default, titled
   `Starfield Warp`, with a solid black rendering area. Closing the window
   exits the program.
2. The simulation maintains **at least 300 stars**. Each star has a random
   3D position: `x` and `y` spread across a wide field around the center,
   and a depth `z` between a near plane and a far plane (e.g. `0.1` to `1.0`
   after normalization — see Sample Data / Inputs).
3. Every animation frame, each star's `z` decreases by the current speed
   value. The star is drawn at its **perspective projection** from the
   window's center:
   `screenX = centerX + x / z * FOCAL`, `screenY = centerY + y / z * FOCAL`
   (with `FOCAL` a constant such as 256).
4. Stars are drawn as **short streaks**: a line from the star's projected
   position last frame to its projected position this frame. Near stars
   (small `z`) must be drawn **brighter and/or thicker** than far stars, so
   streaks visibly lengthen and brighten as stars approach — the "warp"
   look.
5. When a star passes the camera (`z` at or below the near plane) or its
   projection flies off the screen, it is **respawned** at the far plane
   with fresh random `x`/`y`. The field must stay dense indefinitely — no
   thinning out over time.
6. Animation is driven by a `javax.swing.Timer` firing roughly every **16 ms**
   (~60 FPS). Motion must be smooth and continuous while the window is
   visible.
7. A **`JSlider` speed control** sits at the bottom of the window (labels or
   tick marks showing slow → fast). Dragging it changes the warp speed
   **live**, from a gentle crawl to a fast streak-fest, without restarting
   the animation.
8. Pressing **Spacebar** toggles pause: when paused, all stars freeze in
   place and a clearly visible `PAUSED` indicator is drawn on the screen;
   pressing Spacebar again resumes from exactly where it stopped.
9. **Sign-off:** the finished solution must display, somewhere easy to spot
   (e.g. a header comment at the top of the source file), the date and time
   it was produced and the model/author that produced it.

## Constraints

- **JDK only** — one `.java` file using `java.awt` / `javax.swing`. No
  external libraries, no build tools (no Maven/Gradle), no assets.
- Must compile and run on any JDK 8+ with:
  `javac WarpStarfield.java && java WarpStarfield`
- No network access, no file I/O, no threads beyond the Swing event
  dispatch thread — the `Timer` callbacks are the whole game loop.
- All rendering happens inside `paintComponent(Graphics)` of a `JPanel`
  (call `super.paintComponent` first, then draw). Do not use
  `getGraphics()` or draw outside the paint cycle; Swing's default double
  buffering is enough.
- Keep everything in one public class (`WarpStarfield`); small private
  helper/inner classes (e.g. a `Star` record-like class) are fine.

## Sample Data / Inputs

No external data. Suggested defaults and ranges:

| Setting            | Suggested value                     |
|--------------------|-------------------------------------|
| Star count         | 400                                 |
| Window size        | 800 × 600                           |
| Focal length       | 256                                 |
| Spawn range x, y   | uniform in [−1024, +1024]           |
| z range            | [0.1, 1.0] (respawn at z = 1.0)     |
| Speed range        | 0.001 (crawl) → 0.02 (fast warp)    |
| Default speed      | 0.005                               |
| Frame delay        | 16 ms                               |

Controls:

| Input          | Action                          |
|----------------|---------------------------------|
| Speed slider   | Change warp speed live          |
| Spacebar       | Toggle pause / resume           |

A typical run: window opens on a dense, dim field of points; within a second
they begin drifting outward from the center; dragging the slider right turns
the drift into bright, radiating streaks; Spacebar freezes everything with
`PAUSED` overlaid.

## Deliverable

- `WarpStarfield.java` — the complete application in a single file.
- Compile: `javac WarpStarfield.java`
- Run: `java WarpStarfield`

## Done When

- [ ] `javac WarpStarfield.java && java WarpStarfield` opens an 800×600
      black window titled `Starfield Warp`.
- [ ] At least 300 stars continuously stream outward from the window's
      center; the field never visibly thins or empties over a 60-second run.
- [ ] Stars are dim/small near the center and become brighter, longer
      streaks as they approach the edges — the effect clearly reads as
      "flying through space".
- [ ] Dragging the speed slider changes the motion live from a slow crawl
      to a fast warp, with no stutter or restart.
- [ ] Spacebar freezes all motion and shows a `PAUSED` indicator; pressing
      it again resumes seamlessly.
- [ ] The source file's header comment shows the date/time produced and the
      model/author that produced it.

## Stretch Goals (optional)

- **Hyperspace burst:** pressing `B` (or clicking the rendering area) ramps
  the speed to maximum for a moment, then eases back to the slider's value.
- **Depth tinting:** color stars by depth — cool blue-white when far, warm
  white/yellow when near — instead of plain grayscale.
- **Steerable vanishing point:** the projection center smoothly follows the
  mouse cursor, so moving the mouse "steers" the ship.
