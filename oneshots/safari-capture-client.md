# Capture the Domain — Safari Read-Later Capture Client

**Difficulty:** hard  |  **Stack:** Swift + Safari Web Extension (JS)  |  **Estimated time:** 5–8 h

## The Problem

Read-later tools save a URL and hope the page still exists when you come back to it. Paywalls, redesigns, dead media and tracking scripts turn yesterday's article into a 404 or a cookie wall. What you actually want is the *text you already read*, captured at the moment you read it, as plain Markdown with its images embedded, so it stays readable offline forever.

Build the capture half of that system: a native Safari Web Extension for iOS and iPadOS. It arms like a camera's record button, watches everything you navigate to inside the current site for ten minutes, converts each page's main content into Markdown with base64 images, and uploads it to a read-later endpoint you configure. It never syncs anything while disarmed, and it never decides what the archive means — it just delivers clean, self-contained page snapshots.

## Requirements

1. Produce an Xcode project with an iOS/iPadOS app target (SwiftUI) plus a Safari Web Extension target, targeting iOS 17+ and iPadOS 17+. It must build and run in the iOS Simulator without third-party packages, Swift packages, or npm dependencies.
2. The extension popup contains: an Arm/Disarm control, a live countdown while armed, an "Extend 10 min" action, an endpoint URL field, a bearer-token field, a "Flush queue" button and a capture log.
3. Arming stores an absolute deadline (`armedUntil = Date.now() + 10 * 60 * 1000`) in shared extension storage; the popup renders the remaining time from that value every second. The countdown survives tab switches and Safari backgrounding, and expires on its own with no background timer required. Disarming clears the deadline immediately.
4. A content script runs in every top-level page and, on `document.readyState === "complete"`, captures the page only if all of these hold: the deadline is in the future, `window.top === window` , the page's host equals the host that was armed, and the document content type is HTML.
5. SPA navigation is captured: `history.pushState`, `history.replaceState` and `popstate` are observed, the capture waits until the DOM has been mutation-quiet for 500 ms, and the resulting URL is captured under the same rules as a full load.
6. Content extraction produces article Markdown using a readability-style heuristic (largest text-dense subtree, stripping `nav`, `header`, `footer`, `aside`, `script`, `style`, `form`, `noscript`), falling back to `document.body` when no candidate reaches 200 characters of text. Headings, paragraphs, ordered/unordered lists, blockquotes, fenced code blocks and tables survive the conversion.
7. Every capture produces YAML frontmatter with exactly these keys: `url`, `title`, `host`, `captured_at` (ISO 8601, UTC, second precision), `content_hash` (SHA-256 hex of the Markdown body that follows the frontmatter, excluding the frontmatter block itself), and `captured_by` (the sign-off string from requirement 16).
8. Images referenced by `<img>` inside the extracted content are fetched and inlined as `![alt](data:<mime>;base64,<data>)`; when a fetch fails (CORS, 404, non-image), the original absolute URL is kept and the popup log entry records an `images_failed` count greater than zero.
9. Links inside the Markdown stay absolute and unmodified. A separate `links` array containing every distinct same-host URL found in the extracted content (including query strings, excluding fragment-only and `mailto:`/`javascript:` targets) is sent with the upload.
10. Upload is `POST <endpoint>` with `Authorization: Bearer <token>` and `multipart/form-data`, containing the parts `url`, `captured_at`, `content_hash`, `links` (a JSON array serialised into a text part) and `markdown` (a file part named `page-<content_hash>.md`). Any 2xx response counts as success; any other status, timeout or network error queues the capture.
11. A failed upload is persisted in IndexedDB and retried automatically on the next successful capture, when the popup opens, and on "Flush queue". Successful retries are removed from the queue; the queue count is visible in the popup at all times.
12. Within one armed window, a capture whose `url` and `content_hash` both match an earlier successful upload is skipped without a request and logged as `skipped: duplicate`. Re-arming the extension clears that in-memory dedupe state, so a manual re-arm always re-sends.
13. The capture log keeps the 20 most recent entries, each showing: time, URL (truncated), status (`uploaded` | `queued` | `skipped` | `failed`), payload size in bytes, and a reason. Entries survive a popup close and reopen.
14. Nothing is uploaded while disarmed or after the deadline passes, including queued items — the queue only drains while armed and inside the window.
15. A dependency-free Node stub receiver is included: it serves two demo pages, accepts the multipart upload, writes each successful capture to `captures/<host>/<content_hash>.md` with the original multipart parts stored alongside in `captures/<host>/<content_hash>.json`, and prints one line per request (`201 <host> <bytes>` or `401`). It must reject requests with a wrong or missing bearer token using status 401.
16. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it. Put it in the popup footer (visible without scrolling) and repeat it as the `captured_by` value in every uploaded snapshot's frontmatter.

## Constraints

- Standard library only on the extension side: no npm, no Swift packages, no CocoaPods; the Xcode project and its generated scaffolding are the only allowed "framework".
- The only network destination for the extension is the configured endpoint; page images may be fetched from their own origins. No analytics, no telemetry, no remote script loading.
- The bearer token lives in extension storage and is entered through the popup. It must never appear in source, in a committed file, in the capture log, or in the uploaded Markdown.
- No login or paywall bypass, no cookie access beyond what the rendered page already shows, and no transmission of cookies or credentials.
- Capture only what the page currently renders. No headless rendering, no server-side fetch, no scraping of URLs the user did not visit.
- A 200 KB article must be extracted, inlined and handed to the uploader within 10 seconds of the triggering event; otherwise log `failed: timeout` and continue watching.
- The stub must start with one command and must not require an internet connection.

## Sample Data / Inputs

The stub serves the demo pages below. Page A links to page B, so a single armed window can exercise both a full navigation and an internal link:

`GET /demo` returns:

```html
<!doctype html>
<html><head><title>The Quiet Web</title></head>
<body>
<header><nav><a href="/">Home</a><a href="/demo/chapter-2">Chapter 2</a></nav></header>
<article>
  <h1>The Quiet Web</h1>
  <p class="byline">Posted 3 March 2021 · 6 min read</p>
  <p>Reading on the web used to mean reading. Then pages grew sidebars,
  autoplay videos, newsletter modals and three consent banners before the
  first sentence.</p>
  <p>This article is deliberately boring. It exists so a capture client can
  prove it extracts <em>prose</em> and not chrome.</p>
  <figure>
    <img src="/hero.png" alt="A small placeholder image">
    <figcaption>Figure 1. A 1×1 placeholder stands in for a real hero.</figcaption>
  </figure>
  <h2>Why snapshot instead of bookmark</h2>
  <ul>
    <li>A bookmark keeps a promise the web does not keep.</li>
    <li>A snapshot keeps the words you actually read.</li>
    <li>A snapshot survives the redesign.</li>
  </ul>
  <pre><code>curl -X POST http://localhost:8787/api/capture \
  -H "Authorization: Bearer demo" \
  -F "url=https://example.com/x"</code></pre>
  <table><thead><tr><th>Format</th><th>Keeps</th></tr></thead>
  <tbody><tr><td>URL</td><td>nothing</td></tr>
  <tr><td>Snapshot</td><td>text and images</td></tr></tbody></table>
  <p>Continue with <a href="/demo/chapter-2">Chapter 2</a>, or read the
  <a href="/demo/chapter-2?ref=footer">same chapter from the footer</a>.</p>
  <p>An <a href="https://example.invalid/elsewhere">external link</a> must not
  appear in the links array.</p>
</article>
<footer><p>© 2021 The Quiet Web</p></footer>
</body></html>
```

`GET /demo/chapter-2` returns a shorter article with an `<h1>`, two paragraphs, one `<img src="/hero.png">` and a link back to `/demo`. `GET /hero.png` returns this 1×1 PNG:

```
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==
```

`POST /api/capture` requires `Authorization: Bearer demo`. The endpoint is configured in the popup as `http://localhost:8787/api/capture`; the demo token is `demo`.

## Deliverable

- `SafariCapture/` — the Xcode project (app target + Safari Web Extension target, manifests included).
- `stub/server.js` — the Node stub receiver (stdlib only, no `npm install`).
- `README.md` — build, signing, install and verification steps, with the sign-off line at the top.

Run commands:

```bash
node stub/server.js 8787
open SafariCapture/SafariCapture.xcodeproj    # select an iOS 17 simulator, Run
```

On device or simulator, enable the extension once: Settings → Safari → Extensions → Capture the Domain → Allow. Then open `http://localhost:8787/demo` in Safari, arm the extension, and navigate.

## Done When

- [ ] The project builds and runs for an iOS 17 simulator with zero package managers involved.
- [ ] Arming shows a 10:00 countdown that ticks down while the popup is closed and reopened, and disarming stops all uploads immediately.
- [ ] Loading `/demo` while armed produces one `201` line in the stub and one `captures/localhost/<hash>.md`.
- [ ] That file opens as readable Markdown: frontmatter with all six keys, headings, the list, the fenced code block and the table intact, and an inline `data:image/png;base64,` image.
- [ ] Its JSON sidecar contains a `links` array with two `/demo/chapter-2` URLs and no `example.invalid` entry.
- [ ] Clicking the in-article link to `/demo/chapter-2` captures a second page without a manual reload, proving SPA/history observation.
- [ ] Re-opening the same page inside the same armed window produces a `skipped: duplicate` log entry and no second upload.
- [ ] Navigating to a different host while armed stops uploads but the countdown keeps running; returning to the armed host before expiry resumes capture.
- [ ] Stopping the stub, capturing a page, restarting the stub and pressing "Flush queue" delivers the queued capture and empties the queue counter.
- [ ] A wrong token in the popup yields `401` at the stub, a `queued` log entry in the popup, and no token text visible anywhere in the UI or in `captures/`.
- [ ] Letting the deadline expire prevents any further upload even with the page still open and the queue non-empty.
- [ ] The popup footer shows the sign-off line.

## Stretch Goals (optional)

- Persist the dedupe state per host so re-arming a minute later does not re-send unchanged pages, while a changed `content_hash` still uploads.
- Add a "capture selection only" mode that snapshots the current text selection instead of the article.
- Emit a per-page `image_report` in the JSON sidecar listing inlined and failed image URLs, so the server can re-fetch only what is missing.
