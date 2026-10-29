# Marksite — Mini Static Site Generator

**Difficulty:** medium  |  **Stack:** Python 3 (stdlib only)  |  **Estimated time:** 1–3 h

## The Problem

Every side project eventually grows a `docs/` folder full of Markdown that nobody reads, because `.md` files are awkward to browse outside an editor. Hosted docs platforms are overkill for a handful of pages, and pulling in a full framework like Hugo or MkDocs means installs, config files, and themes to learn. What you actually want is a single Python file that swallows a folder of Markdown and spits out a small, styled, interlinked HTML site you can open straight from disk. Build that generator: a defined Markdown subset in, a linked site with an index page out.

## Requirements

1. Produce a single file `marksite.py`. Running `python3 marksite.py` (or `python3 marksite.py --demo`) builds an **embedded demo site** — the three Markdown files from the Sample Data section, stored in the source as a dict constant `DEMO_PAGES` mapping file names to content — into a `site/` folder. Running `python3 marksite.py build SRCDIR OUTDIR` converts every `.md` file in `SRCDIR` (scanned non-recursively, sorted by file name) into `OUTDIR`.
2. Parse this Markdown subset with your own parser (no third-party Markdown libraries):
   - Headings: `# `, `## `, `### ` → `<h1>`, `<h2>`, `<h3>` (the space after the hashes is required; four or more `#` is an ordinary paragraph).
   - Paragraphs: blocks of text separated by blank lines → `<p>`; single newlines inside a paragraph join with a space.
   - Bold `**text**` → `<strong>` and italic `*text*` → `<em>`, working everywhere inline: paragraphs, headings, list items, and link text.
   - Unordered lists: consecutive lines starting with `- ` grouped into one `<ul>`; ordered lists: consecutive lines matching `N. ` grouped into one `<ol>`. A blank line or any other line ends the list. No nesting required.
   - Links `[text](url)` → `<a href="url">text</a>`.
   - Fenced code blocks delimited by lines of three backticks (optionally followed by a language word, e.g. ` ```bash `) → `<pre><code>` with the content rendered **verbatim**: no inline formatting inside, and an unclosed fence at end of file still closes the block.
3. Emphasis follows the *hugging rule*: a delimiter only counts when it directly touches a non-space character on the inside (`*ok*` is italic, but `2 * 3` and `a * b` stay literal). Process bold before italic.
4. Escape all literal text — there is no raw-HTML passthrough in this subset. `&`, `<`, `>` in ordinary text and in code blocks must come out as entities (so `<div>` in the source shows as readable `<div>` text in the browser, never as a rendered element).
5. Rewrite cross-page links: an `[text](page.md)` link whose target ends in `.md` becomes `page.html`; `http://`, `https://`, and `#anchor` links are left untouched. If a `.md` link points to a file that is not part of the build, print a `warning: broken link ...` line in the build report but finish the build anyway.
6. Wrap every page in a shared HTML template embedded in the script: a full `<!doctype html>` document with an inline `<style>` block (a max-width ~44rem content column, a system font stack, a styled nav bar, and `pre` blocks with a background and horizontal scrolling), a `<header>` showing the site name (`Marksite Demo` for the demo, the source folder name for real builds) and a `<nav>` linking to every page in file-name order, then `<main>` with the rendered content.
7. Page titles: the first `# ` heading in a file becomes its `<title>` and its nav label; files without an H1 fall back to their file-name stem.
8. Always generate `index.html`. If the source set contains `index.md`, render its content followed by an auto-generated **Pages** section; otherwise `index.html` is just the Pages section. The Pages section lists every *other* page as a link with its title plus a plain-text excerpt — the first paragraph with all Markdown markers stripped, truncated to 120 characters and ending in `…` if longer.
9. Print a build report to the console: header lines naming the source and output folder, one indented line per page showing `source.md -> output.html` and its detected title in quotes, and a final `done: N pages` summary line. All values must be computed, never hardcoded.
10. **Sign-off:** every generated page must carry a footer showing the date and time the *solution* was produced and the model/author that produced it (a static string baked into the template, e.g. `Built by marksite.py — solution produced 2026-10-29 14:30 by <model/author>`); include the same information as a header comment in the source.

## Constraints

- Python 3.8+, standard library only (`re`, `html`, `pathlib`, `sys`, `time` are enough). No third-party packages, no pip, no build step.
- No network access. The only file writes allowed are the generated `.html` files inside the output folder (create it if missing).
- Source folders are scanned non-recursively; only files ending in `.md` are considered.
- The demo Markdown must live inside `marksite.py` as `DEMO_PAGES` — the script must run with zero arguments and no external files present.
- Generated pages must be fully self-contained (inline CSS only) and must work when opened via `file://` in a browser.

## Sample Data / Inputs

Embedded demo — use exactly this as `DEMO_PAGES`:

`index.md`:

````markdown
# PocketDocs

A **tiny** documentation site built with *Marksite*, the smallest static site generator that still earns the name.

## Why it exists

- Write docs in plain Markdown
- Get a linked HTML site in seconds
- Zero dependencies, zero excuses

Start with the [quickstart guide](guide.md) or jump to the [command reference](commands.md).
````

`guide.md`:

````markdown
# Quickstart Guide

Marksite turns a folder of `.md` files into a website in **three** steps:

1. Create a folder and drop in some Markdown files
2. Run the build command shown below
3. Open the generated `index.html` in your browser

## Links just work

Links to other `.md` files are *rewritten* automatically, so [the command reference](commands.md) keeps working after the build. External links such as [Python](https://www.python.org) are left alone.

```bash
python3 marksite.py build docs site
# 2 pages converted
```
````

`commands.md`:

````markdown
# Command Reference

## marksite build

Converts every `.md` file in the source folder to HTML.

- The source folder is scanned **non-recursively**
- Output keeps the *same file names* with an `.html` extension
- Multiplication like 2 * 3 and tags like <div> in plain text stay exactly as written

```html
<div class="note">Fish & chips</div>
```

Back to the [home page](index.md).
````

Expected shape of the build report for the demo (exact layout is up to you, but all values must be computed, never hardcoded):

```
marksite — building site
source : embedded demo (3 pages)
output : site/
  commands.md -> commands.html "Command Reference"
  guide.md    -> guide.html    "Quickstart Guide"
  index.md    -> index.html    "PocketDocs"
done   : 3 pages
```

## Deliverable

- One file: `marksite.py`
- Run commands:
  - `python3 marksite.py` — builds the embedded demo site into `./site/`
  - `python3 marksite.py build SRCDIR OUTDIR` — builds any folder of `.md` files
- Open `site/index.html` (demo) or `OUTDIR/index.html` in a browser to view the result.

## Done When

- [ ] `python3 marksite.py` runs with no arguments, creates `site/`, and prints a build report listing all three demo pages with their detected titles.
- [ ] Opening `site/index.html` in a browser shows a styled page (not raw HTML): a nav bar linking to all three pages, the PocketDocs content, and a Pages section linking to the guide and command reference with excerpts.
- [ ] The `[quickstart guide](guide.md)` link on the index page points to `guide.html`, and the external link on the guide page still points to `https://www.python.org`.
- [ ] The ordered list on the guide page renders as a real numbered list, and the bash block appears verbatim in a scrollable `<pre>` block.
- [ ] On the command reference page, `2 * 3` shows literal asterisks, `<div>` appears as readable text, and the HTML code block shows `<div class="note">Fish & chips</div>` verbatim and escaped.
- [ ] `python3 marksite.py build somedir outdir` converts a real folder of Markdown files the same way, and a `[x](missing.md)` link produces a `warning:` line while the build still completes.
- [ ] Every generated page has a footer showing when the solution was produced and by which model/author.

## Stretch Goals (optional)

- Inline code: `` `text` `` → `<code>`, with the same verbatim/escaping rules as fenced blocks.
- `--watch` mode: poll source file mtimes once per second and rebuild on change, printing a one-line log per rebuild.
- Add `id` slugs to headings (e.g. `<h2 id="links-just-work">`) and rewrite combined targets like `[x](guide.md#links-just-work)` to `guide.html#links-just-work`.
