# RepoLens — Mobile-First GitHub Repository Explorer

Single-file web app. **Launch: open `index.html` in a modern browser.** No Node, no server, no build, no login.

## Supported browsers

Current Chrome, Edge, Firefox, Safari — including mobile Safari and Chrome for Android.
Requires `fetch`, `async/await`, and (for persistence) `localStorage`.

## `file://` restrictions

- The app runs directly from `file://`. CDN libraries (marked, DOMPurify,
  highlight.js via cdnjs) require internet on first load. If they fail to load,
  Markdown falls back to raw source and code renders without highlighting.
- `localStorage` can be blocked in private-browsing modes or strict `file://`
  contexts (notably some mobile-Safari configurations). The app detects this,
  falls back to in-memory history/theme/bookmarks for the session, and shows a
  toast explaining persistence is unavailable. History persistence is most
  reliable over `http(s)`.
- GitHub API access (`api.github.com`, `raw.githubusercontent.com`) needs
  internet. Anonymous rate limit is 60 req/hr; the app surfaces reset times.

## Implementation overview

- **GitHub API:** `GET /repos/{owner}/{repo}` for metadata (discovers
  `default_branch` — never assumed). `GET /.../contents/{path}?ref={branch}`
  for listings; `download_url` (with contents-API base64 fallback) for file
  text; `GET /.../git/trees/{branch}?recursive=1` for quick-open search.
  Branch-with-slashes resolved by longest-prefix match against `/branches`;
  paths are segment-wise `encodeURIComponent`-encoded. In-memory caches for
  repos, dirs, branches, trees; monotonic request-id guard drops stale async
  responses; 15 s `AbortController` timeouts; `X-RateLimit-*` headers produce
  human-readable rate-limit errors.
- **Markdown renderer:** marked (GFM) → DOMPurify sanitize → styled article.
  Rendered/Raw toggle. Relative images rewritten to
  `raw.githubusercontent.com`; relative links resolved against repo context —
  code/markdown targets open inside the app, same-repo GitHub blob URLs are
  intercepted, everything external gets `target="_blank" rel="noopener"`.
- **Syntax highlighter:** highlight.js with extension→language map
  (JS/TS/Python/Java/HTML/CSS/JSON/YAML/SQL/shell/…), chunked line-numbered
  rendering (200 lines/frame) so large files stay responsive, plaintext
  fallback, copy-to-clipboard, font-size + wrap controls, 512 KB truncation
  notice, binary detection (extension + NUL-byte sniff) with image preview.
- **Persistence:** `localStorage` (memory fallback) — history
  (`owner/repo/url/branch/timestamp/desc/lang`, deduped, max 50, ordered by
  last visit), per-repo file bookmarks, theme, reader prefs, and a small
  (<100 KB, 60-entry, 24 h) offline file cache marked stale when served.
  Hash routing (`#/owner/repo/tree/branch/path?f=file`) keeps browser
  back/forward working.

## Stretch goals included

Quick-open file search (`/`), per-repo reading bookmarks, branch badge +
filter + GitHub deep link, font-size/wrap reading controls, offline reading
cache with stale indicator.

## Sign-off

Built 2026-10-31 · Muse Spark 1.3 Contributor (Meta MSL) via OpenCode.
