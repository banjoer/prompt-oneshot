# Typefall — Falling Words Typing Arcade

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (single file)  |  **Estimated time:** 30–60 min

## The Problem

Touch-typing drills are dull, which is why most people never practice. The
classic arcade answer — games like ZType — turns raw typing speed into
survival: words rain down the screen and the only weapon is your keyboard.
This challenge is to build that game as a single, double-clickable HTML file:
words spawn at the top and drift toward a danger line at the bottom, the
player types them away before they land, and a live HUD tracks WPM and
accuracy so every run doubles as a measurable typing workout. With lives,
steadily escalating fall speed, and a personal best WPM that survives browser
restarts via `localStorage`, it is a small game-loop exercise with a genuinely
replayable payoff.

## Requirements

1. The entire game lives in **one self-contained `.html` file** (inline CSS
   and JS, no build step, no external assets) and must be fully playable by
   double-clicking it — i.e. opened directly from disk via a `file://` URL
   in a current Chrome, Firefox, or Safari.
2. **Screens:** the game has at least three clearly distinct states — a start
   screen (title + "press Enter or click to start"), the playfield, and a
   game-over screen showing final stats. Restarting after game over must work
   without reloading the page.
3. **Falling words:** during play, words spawn one at a time at random
   horizontal positions along the top of the playfield and fall downward at a
   constant speed. Multiple words (up to a sensible cap, e.g. 6) may be on
   screen at once. Words are drawn as large, legible text against a
   contrasting background, with a clearly visible **danger line** near the
   bottom of the playfield.
4. **Typing mechanic (deterministic):** the player types on the physical
   keyboard into a visible current-input display. The first character typed
   targets the falling word **closest to the danger line** whose text starts
   with that character; each subsequent correct character extends the match,
   and the matched portion of the target word is visibly highlighted (e.g. a
   different color). A character that does not continue the target word's
   prefix is a **typo**: it counts against accuracy and the target word
   flashes (or the input shakes) as feedback. Backspace deletes the last
   input character and un-highlights it. When the input exactly equals the
   target word, the word is **destroyed** with a small visual effect (pop,
   fade, or particles), the score increases by one, and the input clears.
5. **Lives:** the player starts with **3 lives**, shown in the HUD (hearts or
   icons). Any word that reaches the danger line is removed and costs 1 life.
   At 0 lives the run ends and the game-over screen appears.
6. **HUD:** always visible during play, showing at minimum: score (words
   destroyed), **live WPM**, **accuracy %**, lives remaining, and the saved
   best WPM. Use the standard definitions:
   `WPM = (correct characters typed / 5) / minutes elapsed since the run
   started` and `accuracy = correct keystrokes / total keystrokes × 100`
   (show 100% before any keystroke).
7. **Escalation:** the longer a run lasts, the harder it gets — fall speed
   must increase over time (e.g. a step up every 15–20 seconds or every N
   words destroyed) and the spawn interval must shrink, so that a skilled
   player is eventually overwhelmed. The difficulty ramp must be perceptible
   within the first minute of play.
8. **Best WPM persistence:** the best (highest) final-run WPM is stored in
   `localStorage` under the key `typefall.bestWPM`. It is loaded and shown on
   the start screen and HUD, survives closing and reopening the file, and is
   only overwritten when a finished run beats it — the game-over screen then
   displays a clear `NEW BEST!` callout.
9. **Sign-off:** the finished page must display, somewhere easy to spot
   (e.g. a small footer on the start/game-over screen, plus optionally a
   header comment in the source), the date and time it was produced and the
   model/author that produced it.

## Constraints

- One `.html` file only — all CSS in a `<style>` block, all JS in a
  `<script>` block, the word list embedded as a JS array in the file.
- Vanilla HTML/CSS/JS is entirely sufficient and preferred. Third-party
  libraries ARE permitted for this challenge, but only via CDN `<script>`
  tags or by inlining their source; if any are used, they must be declared
  in a comment at the top of the file.
- No external assets: no image, font, or audio files. Any styling is pure
  CSS; any sound must be synthesized with the Web Audio API (optional, not
  required).
- Storage is local only: `localStorage` for the best WPM, nothing else. No
  network calls at runtime beyond any declared CDN tags, no servers.
- Use `requestAnimationFrame` (or a `setInterval` game loop) with delta-time
  movement so fall speed is frame-rate independent; position words in
  pixels per second, not pixels per frame.
- The embedded word list must contain at least the 120 words from Sample
  Data / Inputs (more may be added); all lowercase, no punctuation.

## Sample Data / Inputs

Embed this exact starter word list as a JS array (120 common words, 3–8
letters each):

```js
const WORDS = [
  "apple","arrow","anchor","acorn","beach","bridge","breeze","birch",
  "candle","castle","canyon","clover","cloud","crystal","dancer","dragon",
  "dream","desert","dune","eagle","ember","engine","elm","falcon",
  "feather","fern","flame","forest","frost","galaxy","garden","glacier",
  "goblin","grove","hammer","harbor","hawk","helium","honey","horizon",
  "igloo","insect","iris","island","ivory","jacket","jade","jewel",
  "jigsaw","jungle","kayak","kettle","kitten","kelp","koala","ladder",
  "lagoon","lantern","lemon","light","lily","magic","marble","meadow",
  "meteor","mirror","moss","music","nebula","nectar","needle","noodle",
  "nova","oak","ocean","onyx","orbit","orange","owl","paper",
  "parrot","pencil","piano","pine","prairie","quartz","queen","quiver",
  "rabbit","rainbow","reed","riddle","river","rocket","saddle","sage",
  "shadow","silver","stone","storm","summit","sunset","thunder","tiger",
  "timber","tower","tulip","umber","umbrella","unicorn","vapor","velvet",
  "violet","volcano","walnut","whale","willow","window","yarn","yellow",
  "zebra","zipper"
];
```

Suggested tuning constants (tweak freely, but the ramp must be perceptible):

| Setting                | Suggested value                          |
|------------------------|------------------------------------------|
| Playfield height       | fills most of the viewport               |
| Lives                  | 3                                        |
| Starting fall speed    | 40 px/s                                  |
| Speed escalation       | +15 px/s every 15 s (cap ~200 px/s)      |
| Starting spawn interval| 2000 ms                                  |
| Spawn escalation       | −150 ms per escalation step (min 700 ms) |
| Max words on screen    | 6                                        |
| WPM formula            | (correct chars / 5) / minutes elapsed    |
| localStorage key       | `typefall.bestWPM`                       |

## Deliverable

- `typefall.html` — the complete game in a single file.
- Run: double-click `typefall.html` (or open it in any modern browser via
  `file://`). No server, no install, no build step.

## Done When

- [ ] Opening `typefall.html` from disk shows a start screen with the saved
      best WPM (or a sensible placeholder on first run); Enter or a click
      starts the game.
- [ ] Words spawn at the top, fall smoothly toward a visible danger line,
      and never exceed the on-screen cap.
- [ ] Typing letters highlights the matched prefix of the targeted word;
      completing a word destroys it with a visible effect and increments the
      score; a wrong key registers as a typo with visible feedback;
      Backspace edits the input.
- [ ] The HUD shows score, live WPM, accuracy %, lives, and best WPM, and
      all of them update during play.
- [ ] A word reaching the danger line costs 1 life; losing all 3 ends the
      run on a game-over screen showing final WPM, accuracy, and score, and
      restarting works without a page reload.
- [ ] Fall speed visibly increases and spawns visibly accelerate within the
      first minute of a run.
- [ ] A run that beats the stored best WPM saves it, shows a `NEW BEST!`
      callout, and the value persists after the browser is closed and the
      file reopened.
- [ ] The page displays the date/time produced and the model/author in an
      easy-to-spot footer or header comment.

## Stretch Goals (optional)

- **Combo meter:** consecutive words destroyed with zero typos build a
  multiplier that boosts the score; any typo resets it.
- **Juice:** particle bursts on word destruction and short Web Audio blips
  whose pitch rises with the combo — all synthesized, no audio files.
- **Shockwave key:** once per run, pressing Spacebar clears every word
  currently on screen (no score), for clutch saves at high speed.
