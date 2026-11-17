# Capture the Domain — Safari Read-Later Capture Client

**Sign-off:** Produced 2026-11-17T01:40Z by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash)

A native iOS/iPadOS 17+ SwiftUI app with a Safari Web Extension that acts like a camera record button. Arm it on a site for ten minutes; every page you navigate to inside that host is converted to self-contained Markdown (YAML frontmatter, inline images, same-host link list) and `POST`ed to the read-later endpoint you type into the popup. It never syncs while disarmed or after the deadline, and it never hardcodes a host, port, path or scheme.

No Swift packages, no CocoaPods, no npm packages, no remote scripts, no telemetry.

---

## What is in the box

```
SafariCapture/
  SafariCapture.xcodeproj/          Xcode project (app + Safari Web Extension)
  SafariCapture/                    SwiftUI iOS app shell
  SafariCaptureExtension/
    Info.plist                      com.apple.Safari.web-extension
    SafariWebExtensionHandler.swift native message stub
    Resources/
      manifest.json                 MV3 Safari Web Extension manifest
      background.js                 armed window, images, SHA-256, upload, IndexedDB queue
      content.js                    readiness, history observation, readability + Markdown
      shared.js                     constants (including the sign-off) and helpers
      popup.html / popup.css / popup.js
.github/workflows/ios-build.yml     unsigned simulator + device builds, IPA artifact
stub/server.js                      dependency-free demo pages + multipart receiver
SIDELOADING.md                      Ubuntu-only install path for a real iPhone/iPad
README.md                           this file
```

The only "framework" is the Xcode project and its generated scaffolding. Everything in the extension is plain JavaScript and WebExtension APIs.

---

## Quick start

All commands are run from this directory (the solution root).

### 1. Start the demo receiver

```bash
node stub/server.js 8787
```

- `8787` is just the demo port; any port works.
- The second argument overrides the token: `node stub/server.js 8787 mytoken`.
- `CAPTURE_TOKEN` is also read if the second argument is omitted.
- The default token is the challenge's `demo`.
- Successful uploads are written to `captures/<hostname>/<content_hash>.md` and `.json` in the current working directory.
- The stub prints exactly one line per upload: `201 <host> <bytes>` or `401`.

### 2. Build and run

**With a Mac:**

```bash
open SafariCapture/SafariCapture.xcodeproj
# scheme: SafariCapture, destination: an iOS 17 iPhone 15 simulator, Run
```

No signing identity is needed for the simulator. The app opens the setup screen; the actual extension work happens in Safari.

**Without a Mac (the intended path):**

Push the branch, let the `iOS build` workflow run, then download the artifact:

```bash
gh workflow run ios-build.yml
gh run download --name SafariCapture-unsigned -D dist
# dist/SafariCapture-unsigned.ipa is now on disk
```

Follow [SIDELOADING.md](SIDELOADING.md) to install that unsigned IPA with Sideloadly/AltStore on a real iPhone or iPad from an Ubuntu machine.

### 3. Enable the extension once

On the simulator or device:

1. Open **Settings → Safari → Extensions → Capture the Domain** (on some iOS 17 builds: **Settings → Apps → Safari → Extensions**).
2. Turn it on and allow it on the sites you want to watch.
3. In Safari, tap the extensions button in the address bar (the puzzle-piece/Aa menu) and open **Capture the Domain**.

### 4. Configure and arm

Open `http://localhost:8787/demo` in Safari, then open the extension popup:

| Field | Demo value |
|---|---|
| Sync endpoint | `http://localhost:8787/api/capture` |
| Bearer token | `demo` |

The endpoint and token are entered **through the popup** and persisted in Safari extension storage. They are not in any Swift/JavaScript source. Press **Save**, then **Arm 10 min**. The countdown is computed from the absolute `armedUntil` deadline, so closing the popup, switching tabs or backgrounding Safari does not stop or reset it.

Now navigate inside `localhost` (reload `/demo`, or click **Chapter 2**). Each capture appears in the popup log and produces one `201` line plus one Markdown file.

---

## How it works

### Armed window and host lock

- `Arm` stores `armedUntil = Date.now() + 10 * 60 * 1000`, the active tab's hostname, and a window start timestamp in `browser.storage.local`.
- The popup renders `armedUntil - Date.now()` every 250 ms. There is no background timer to die or drift; expiry is a comparison, not a scheduled event.
- `Deactivate`/`Disarm` writes `armedUntil = 0` immediately and aborts in-flight uploads and image fetches.
- `Extend 10 min` adds ten minutes to `max(now, armedUntil)` and keeps the same window/dedupe state.
- Content scripts require all of: top frame, future deadline, page hostname equal to the armed host, HTML content type, and `http(s)`. Sub-frames return immediately.

### Capture triggers

- The content script is injected at `document_start` in every frame.
- A load capture runs once `document.readyState === "complete"` (plus a short layout settle).
- `history.pushState`, `history.replaceState`, `popstate` and `hashchange` are observed. After a history change the script watches DOM mutations and waits for 500 ms of quiet (forced after 4 s) before converting the new URL.
- A 10-second budget starts at the trigger. Image inlining gets 9.5 seconds; if extraction/inlining is not handed to the uploader inside 10 s, the popup logs `failed: timeout`.

### Readability-style extraction

The content script:

1. Clones and strips `nav`, `header`, `footer`, `aside`, `script`, `style`, `form`, `noscript`.
2. Scores `article`, `main`, `[role=main]`, common article containers, top-level sections/divs and `body` by text length, link density, paragraph count and heading count. `article` gets a bonus; `body` a penalty.
3. Uses the best candidate that reaches 200 characters of text; otherwise falls back to `document.body` as required.
4. Converts headings, paragraphs, ordered/unordered lists (including nesting), blockquotes, fenced code blocks with language hints, GFM tables, figures/captions, emphasis, code and absolute links to Markdown.
5. Replaces images with unique placeholders and records their absolute URLs. The background worker fetches them with extension host permissions, inlines `data:<mime>;base64,...`, and keeps the original absolute URL + increments `images_failed` if the fetch fails (CORS, 404, non-image, deadline).
6. Collects every distinct same-host `http(s)` link inside the extracted content, strips fragments, preserves query strings, and ignores `mailto:`, `javascript:`, fragment-only and external targets.

### Snapshot and upload

Each snapshot has exactly these YAML frontmatter keys:

```yaml
---
url: "http://localhost:8787/demo"
title: "The Quiet Web"
host: "localhost"
captured_at: "2026-11-17T01:40:35Z"
content_hash: "<sha256 of the Markdown body after the frontmatter>"
captured_by: "Produced 2026-11-17T01:40Z by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash)"
---
```

`content_hash` is the SHA-256 hex of the UTF-8 Markdown body (the text after the closing `---\n\n`), excluding the frontmatter itself. The stub recomputes it and records `content_hash_valid` in the sidecar for easy checking.

Upload is a hand-built `multipart/form-data` POST so the exact payload byte count is known:

- `Authorization: Bearer <token>`
- text parts: `url`, `captured_at`, `content_hash`, `links` (JSON array)
- file part: `markdown` named `page-<content_hash>.md` (`text/markdown; charset=utf-8`)
- any 2xx response is success; non-2xx, network error, upload timeout and unconfigured endpoint queue the capture

The endpoint and token are read from storage inside the request path, every time. A queued retry therefore uses the endpoint currently in the popup, not the one that was present when the capture failed.

### Duplicate suppression

Within one armed window, the background keeps a key of `<url>\n<content_hash>` after a successful upload. It mirrors the set into extension storage scoped to the window start so a service-worker restart does not defeat it:

- same URL + same hash → `skipped: duplicate`, no network request
- different hash → uploads (content changed)
- re-arm → dedupe set is cleared, so the same page is sent again

### Queue, log and window rules

- Failed captures live in IndexedDB (`SafariCaptureQueue` / `queue`), keyed by URL + hash so a retry does not duplicate a queue row.
- Retries happen automatically after the next successful capture, when the popup opens, and on **Flush queue**.
- The queue drains only while armed and inside the deadline. Disarm/deadline expiry aborts in-flight work and holds the queue.
- The queue count is always visible in the popup; queued rows survive endpoint changes and popup close/reopen.
- The log is a 20-entry rolling array in extension storage, so it survives popup close/reopen. Each entry records time, URL, status (`uploaded` / `queued` / `skipped` / `failed`), payload size, reason and `images_failed` when non-zero.

### Sign-off

The extension's sign-off string is defined once in `shared.js` (`CAPTURED_BY`), rendered in the popup footer (the footer is a non-scrolling flex child and is visible immediately), and written as `captured_by` into every snapshot. The native app shell repeats the same literal on its main screen and in the message handler.

---

## Verification walkthrough

Start from a clean `captures/` directory.

```bash
node stub/server.js 8787
```

1. **Build**: CI runs the simulator build with `-destination 'platform=iOS Simulator,name=iPhone 15'` and the unsigned device build with `-destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO`, then packages `Payload/` into `SafariCapture-unsigned.ipa` and uploads the `SafariCapture-unsigned` artifact.
2. **Enable**: install/open the app once, then Settings → Safari → Extensions → Capture the Domain → Allow.
3. **Arm**: open `http://localhost:8787/demo`, open the popup, set endpoint `http://localhost:8787/api/capture` + token `demo`, Save, Arm. The countdown shows 10:00 and keeps ticking after closing/reopening the popup.
4. **Full-load capture**: reload `/demo`. Stub prints `201 localhost <bytes>`; `captures/localhost/<hash>.md` contains the six-key frontmatter, headings, the list, the fenced `curl` block, the table and a `data:image/png;base64,` hero. `captures/localhost/<hash>.json` has a `links` array with both chapter-2 URLs (with and without `?ref=footer`) and no `example.invalid` entry.
5. **Second page**: click the in-article **Chapter 2** link. You get a second `201` and a second pair of files, with the chapter-2 link back to `/demo`.
6. **SPA observation**: on a simulator with Web Inspector, run this in the page console, then wait ~500 ms:
   ```js
   history.pushState({}, "", location.pathname + "?spa=1");
   document.querySelector("article").insertAdjacentHTML("beforeend", "<p>SPA section captured after mutation quiet.</p>");
   ```
   A new URL snapshot uploads. The same path works with `replaceState` and `popstate`.
7. **Duplicate**: reload `/demo` again inside the same armed window. The log shows `skipped` / `duplicate`; the stub does not print another `201`.
8. **Different host**: navigate to any other host while armed. No upload; the countdown keeps running. Return to `localhost` before expiry and the next navigation captures again.
9. **Queue**: stop the stub (`Ctrl+C`), reload `/demo/chapter-2` → log shows `queued`, queue count is 1. Restart `node stub/server.js 8787`, open the popup or press **Flush queue** → the queued file uploads and the counter returns to 0.
10. **Endpoint change**: start a second instance on another port:
    ```bash
    node stub/server.js 8788
    ```
    Change the popup endpoint to `http://localhost:8788/api/capture`, Save, then capture or flush. The next upload and any queued retry go to 8788 with no rebuild and no source edit; the queue survives the change.
11. **Disarm**: press **Disarm**. Any further page loads do not upload; the queue is held until you arm again.
12. **Expiry**: let the countdown reach 00:00 (or shorten `armedUntil` with Web Inspector). Further navigation, popup opens and Flush queue do not upload, even with a non-empty queue.
13. **Sign-off**: the popup footer shows the production line without scrolling, and every `.md` contains the same value as `captured_by`.

### Notes for a real device

- `localhost` on an iPhone means the phone, not the Ubuntu workstation. Use the workstation's LAN address, e.g. `http://192.168.1.20:8787/api/capture`, and allow the Local Network prompt. The stub binds `0.0.0.0`, but the firewall must allow the port.
- For anything beyond LAN testing, put the receiver behind HTTPS. The extension itself has no hardcoded destination and accepts any http(s) URL you enter.
- Image fetches that fail (CORS, auth, 404) are deliberately non-fatal: the original absolute image URL stays in the Markdown and the log records `images_failed`.

---

## Security and privacy boundaries

- The bearer token is stored only in Safari extension storage and sent only as the `Authorization` header. It is never written to the log, the Markdown, the queue sidecar or source.
- The stub never logs the Authorization header.
- Uploads use `credentials: "omit"`; page cookies are never forwarded. Image fetches also omit credentials.
- Only the rendered page is read. No headless rendering, server-side fetch, paywall bypass, cookie jar inspection or crawling of unvisited URLs.
- No analytics, telemetry, remote script loading or network access beyond the folder's own demo pages, page images and the configured endpoint.
- No sync host, port or path is compiled into the Swift or extension sources. Demo values appear only in the stub, this README and SIDELOADING; every real destination is typed into the popup.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Extension missing in Settings | Open the containing app once after installing; then Settings → Safari → Extensions. On iOS 17 also check Settings → Apps → Safari → Extensions. |
| Arm says "Open an http(s) page" | Open a normal web page in the active tab first; Safari internal pages have no usable URL. |
| No upload while armed | Popup log reason. `host not armed` means you navigated away; `expired` means the window ended; `queued` means the receiver was unreachable or rejected the token. |
| `401` in the stub | Popup token differs from the stub token (default `demo`). The token is not printed by the stub. |
| Queue never drains | The extension must be armed and inside the window; then open the popup or press Flush queue. |
| Images show as URLs | That image's origin refused the fetch, returned a non-image, or exceeded the deadline. The snapshot is still valid; the log shows `images_failed`. |
| CI cannot find iPhone 15 | The workflow intentionally uses the challenge's required destination. On a local Mac you may pick any installed iOS 17 simulator; CI runners include the iPhone 15 simulator. |
| Artifact install fails | Follow [SIDELOADING.md](SIDELOADING.md); free Apple ID signatures expire after 7 days and must be re-applied. |

---

## Requirement map (short)

| Requirement | Where |
|---|---|
| 1 Xcode app + extension, no third-party deps | `SafariCapture/SafariCapture.xcodeproj`, Swift + plain JS |
| 2 popup controls | `Resources/popup.html`, `popup.js` |
| 3 absolute deadline, extend, disarm | `popup.js` + `background.js` arming handlers |
| 4 eligibility rules | `content.js` `isEligible()`, top-frame return |
| 5 SPA observation + 500 ms quiet | `content.js` history hooks / `scheduleSpaCapture()` |
| 6 readability heuristic + Markdown | `content.js` `pickRoot()` / renderer |
| 7 frontmatter + SHA-256 | `background.js` `buildDocument()`, `sha256Hex()` |
| 8 image inlining / failures | `background.js` `inlineImages()` |
| 9 absolute links + same-host array | `content.js` renderer + `collectLinks()` |
| 10 runtime endpoint + multipart | `background.js` `postCapture()` / `buildMultipart()` |
| 11 IndexedDB queue + retries | `background.js` queue helpers / `drainQueue()` |
| 12 duplicate suppression | `background.js` dedupe helpers |
| 13 20-entry persistent log | `background.js` `appendLog()` |
| 14 armed-window gate | `isArmed()` checks before every upload, abort on disarm |
| 15 Node stub | `stub/server.js` |
| 16 CI + unsigned IPA | `.github/workflows/ios-build.yml` |
| 17 sign-off | `shared.js` `CAPTURED_BY`, popup footer, frontmatter |
