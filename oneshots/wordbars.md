# WordBars

**Difficulty:** easy  |  **Stack:** Node.js (stdlib only)  |  **Estimated time:** 20–45 min

## The Problem

Someone dumps a pile of raw text on you — interview transcripts, support-ticket exports, a chapter of a manuscript — and asks "so what keeps coming up?" Reading it all takes hours and scrolling tells you nothing. What you need is a tiny terminal tool that counts word frequencies and draws a scaled ASCII bar chart of the top words, so the shape of the text is visible at a glance. Build that tool as a single self-contained Node.js script that works out of the box on an embedded sample passage.

## Requirements

1. Produce a single file `wordbars.js`. Running `node wordbars.js` analyzes an embedded sample passage (the text from the Sample Data section, stored in the source as a template-literal constant `SAMPLE_TEXT`); running `node wordbars.js somefile.txt` reads that file as UTF-8 and analyzes it instead.
2. Print a report header first: a separator line of 60 `=` characters, then a title line `WORDBARS`, then a line with the source (`embedded sample` or the file name) and three counts: total tokens found, tokens kept after stop-word removal, and unique kept words.
3. Tokenization: lowercase the text, then extract words with the regular expression `/[a-z]+(?:'[a-z]+)?/g` (runs of ASCII letters, allowing internal apostrophes such as `don't`). Everything else — digits, punctuation, whitespace — is a separator.
4. Stop-word filtering: remove the following 43 words (store them in the source as a constant, e.g. a space-separated string converted to a `Set`): `the a an and or of to in on at by for with from as is was were are it its this that these those had has have be been not no so all they them their we you he she his her`
5. Count the frequency of every kept word, then sort by count descending; break ties alphabetically (ascending, `localeCompare`).
6. Render a chart titled `TOP 10 WORDS` showing the first 10 entries of the sorted list (fewer if fewer exist). Bar formatting: labels left-justified and padded with spaces to the width of the longest displayed label, followed by ` | `, then a bar of `#` characters, then a space and the count. The highest count gets a bar of exactly 30 `#` characters; every other bar's length is its count scaled proportionally and rounded to the nearest integer (any non-zero count gets at least 1 `#`).
7. After the chart, print a coverage line: how many of the kept words the displayed top-10 entries account for, both as `X of Y` and as a percentage rounded to 1 decimal place.
8. Robustness: if the file given on the command line cannot be read, print one clear error line (including the file name) to **stderr** and exit with code 1 — never a stack trace. If no words remain after filtering, print `No words to chart.` instead of an empty chart.
9. **Sign-off:** the report must end with a footer line showing the date and time the solution was produced and the model/author that produced it; also include the same information as a header comment in the source.

## Constraints

- Node.js 16+, standard library only (`fs` and `process` are enough). No npm packages, no `package.json`, no build step.
- No network access. Do not read or write any file other than the optional text file given as a command-line argument.
- Output must be plain ASCII text (use `#` for bars) and stay within 78 columns wide so it fits any terminal.
- The embedded sample text must live inside the source as a constant — the script must run with zero arguments and no external files present.
- All reported numbers must be computed from the input, never hardcoded.

## Sample Data / Inputs

Embedded sample — use exactly this as `SAMPLE_TEXT` (a harbor-town vignette):

```text
The rain came to the harbor before dawn, and the rain stayed. It drummed on the tin roofs of the fish sheds, it needled the gray water, it ran in cold threads down the windows of the cafe where the ferry crews drank their morning coffee. By noon the harbor was all sound: rain on water, rain on canvas, rain on the slick black stones of the pier. The gulls had given up on the sky and sat shoulder to shoulder along the roofline, watching the boats rock at their moorings. Old Mara, who kept the lighthouse on the point, liked to say that rain always brought the town together. Nobody argued with her. When the rain fell, the bakery stayed open late, the radios played quieter songs, and every window along the harbor glowed like a small warm lantern against the weather.
```

Expected shape of the report for the embedded sample (exact layout is up to you, but all values must be computed, never hardcoded):

```
============================================================
WORDBARS
Source: embedded sample | Tokens: 143 | Kept: 89 | Unique: 77

TOP 10 WORDS
rain     | ############################## 7
harbor   | ############# 3
along    | ######### 2
shoulder | ######### 2
stayed   | ######### 2
water    | ######### 2
against  | #### 1
always   | #### 1
argued   | #### 1
bakery   | #### 1

Top 10 covers 22 of 89 kept words (24.7%)

Generated 2026-10-29 12:00 by <model/author>
```

## Deliverable

- One file: `wordbars.js`
- Run commands:
  - `node wordbars.js` — renders the report for the embedded sample passage
  - `node wordbars.js yourtext.txt` — renders the report for any other text file

## Done When

- [ ] `node wordbars.js` runs with no arguments and prints the full report for the embedded sample without errors.
- [ ] The header reports source `embedded sample`, 143 tokens, 89 kept, 77 unique.
- [ ] `rain` is the top word with a count of 7 and a bar of exactly 30 `#` characters; `harbor` follows with 3 and a bar of exactly 13 `#`.
- [ ] The four words tied at count 2 appear in alphabetical order (`along`, `shoulder`, `stayed`, `water`), and all bar lines are aligned via padded labels and a ` | ` separator.
- [ ] The coverage line reads 22 of 89 kept words (24.7%).
- [ ] The script also works on a different text file passed as a command-line argument, and a missing/garbage file path produces one clean stderr error line with exit code 1 (no stack trace).
- [ ] A footer line shows the date/time the solution was produced and the model/author.

## Stretch Goals (optional)

- Add a `--top N` flag that changes how many words are charted (default 10).
- Append each word's share of all kept words to its bar line, e.g. `7 (7.9%)`.
- Compare mode: `node wordbars.js fileA.txt fileB.txt` prints the 10 words whose frequency rank rose or fell the most between the two files.
