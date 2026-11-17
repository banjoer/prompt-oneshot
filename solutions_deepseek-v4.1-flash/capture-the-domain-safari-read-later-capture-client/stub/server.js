#!/usr/bin/env node
/*
 * Capture the Domain - dependency-free demo receiver.
 *
 *   node stub/server.js [port] [token]
 *
 * The port defaults to 8787 and the token to the demo token "demo".
 * CAPTURE_TOKEN overrides the default token (the CLI argument wins).
 * Every successful multipart capture is written to:
 *
 *   captures/<host>/<content_hash>.md
 *   captures/<host>/<content_hash>.json
 *
 * Only Node's standard library is used.  It works offline.
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const argv = process.argv.slice(2);
const parsedPort = Number(argv[0]);
const PORT = Number.isFinite(parsedPort) ? parsedPort : 8787;
const TOKEN = String(argv[1] || process.env.CAPTURE_TOKEN || "demo");
const CAPTURE_ROOT = path.join(process.cwd(), "captures");
const MAX_BODY_BYTES = 64 * 1024 * 1024;

const HERO_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const DEMO_HTML = String.raw`<!doctype html>
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
`;

const CHAPTER_TWO_HTML = String.raw`<!doctype html>
<html><head><title>Chapter 2 · The Quiet Web</title></head>
<body>
<header><nav><a href="/">Home</a><a href="/demo">Chapter 1</a></nav></header>
<article>
  <h1>Chapter 2: The Archive Keeps Its Word</h1>
  <p>The first chapter made a promise: the words you read would still be
  there tomorrow. This chapter is the smaller, quieter proof. It has a
  heading, two paragraphs, one image and a link back to the beginning.</p>
  <p>When the capture client is armed, following the link from the first
  chapter should produce a second snapshot without anyone pressing reload.
  That is the whole trick: watch the history, wait for the page to settle,
  and keep the prose.</p>
  <figure>
    <img src="/hero.png" alt="The same small placeholder image">
    <figcaption>Figure 2. The same one-pixel hero, still standing in.</figcaption>
  </figure>
  <p>Return to <a href="/demo">The Quiet Web</a> when you are ready to
  test duplicate suppression.</p>
</article>
<footer><p>© 2021 The Quiet Web</p></footer>
</body></html>
`;

const INDEX_HTML = String.raw`<!doctype html>
<html><head><title>Capture the Domain · Demo</title>
<style>
  body{font:16px/1.55 -apple-system,system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1.25rem;color:#172033}
  h1{font-size:1.7rem}
  code{background:#f2efe8;padding:.12rem .3rem;border-radius:4px}
  li{margin:.35rem 0}
</style></head>
<body>
<h1>Capture the Domain · demo receiver</h1>
<p>Two pages with article chrome, an image, lists, a code block, a table and
same-host links. Arm the Safari extension, then open <a href="/demo">the first
chapter</a>.</p>
<ul>
  <li><a href="/demo">/demo</a> — the long article</li>
  <li><a href="/demo/chapter-2">/demo/chapter-2</a> — the short article</li>
  <li><a href="/hero.png">/hero.png</a> — the one-pixel image</li>
  <li><code>POST /api/capture</code> — multipart receiver</li>
</ul>
<p>Uploads are written under <code>captures/&lt;host&gt;/</code> in the
directory where the stub was started.</p>
</body></html>
`;

function log(line) {
  process.stdout.write(line + "\n");
}

function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

function send(res, status, body, contentType) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(String(body), "utf8");
  res.writeHead(status, {
    "Content-Type": contentType || "text/plain; charset=utf-8",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
  });
  res.end(payload);
}

function authorize(req) {
  const header = String(req.headers.authorization || "");
  const expected = "Bearer " + TOKEN;
  const a = Buffer.from(header, "utf8");
  const b = Buffer.from(expected, "utf8");
  if (a.length !== b.length) return false;
  try {
    return crypto.timingSafeEqual(a, b);
  } catch (error) {
    return false;
  }
}

function parseMultipart(body, boundary) {
  const text = body.toString("utf8");
  const delimiter = "--" + boundary;
  const segments = text.split(delimiter);
  const parts = Object.create(null);
  const files = Object.create(null);

  for (let i = 1; i < segments.length; i += 1) {
    let segment = segments[i];
    if (segment.startsWith("--")) break; // closing delimiter
    if (segment.startsWith("\r\n")) segment = segment.slice(2);

    const headerEnd = segment.indexOf("\r\n\r\n");
    if (headerEnd < 0) continue;

    const rawHeaders = segment.slice(0, headerEnd);
    let content = segment.slice(headerEnd + 4);
    if (content.endsWith("\r\n")) content = content.slice(0, -2);

    const headers = Object.create(null);
    rawHeaders.split("\r\n").forEach((line) => {
      const colon = line.indexOf(":");
      if (colon > 0) {
        headers[line.slice(0, colon).trim().toLowerCase()] = line.slice(colon + 1).trim();
      }
    });

    const disposition = headers["content-disposition"] || "";
    const name = /name="([^"]*)"/i.exec(disposition);
    if (!name) continue;
    const filename = /filename="([^"]*)"/i.exec(disposition);

    parts[name[1]] = content;
    if (filename) {
      files[name[1]] = {
        filename: filename[1],
        content_type: headers["content-type"] || "",
        bytes: Buffer.byteLength(content, "utf8")
      };
    }
  }

  return { parts, files };
}

function splitFrontmatter(markdown) {
  if (!markdown.startsWith("---\n")) return null;
  const closing = markdown.indexOf("\n---\n", 4);
  if (closing < 0) return null;
  let body = markdown.slice(closing + 5);
  if (body.startsWith("\n")) body = body.slice(1);
  return { frontmatter: markdown.slice(0, closing + 5), body };
}

function safeHostFromUrl(rawUrl) {
  try {
    const host = new URL(rawUrl).hostname;
    return host.toLowerCase().replace(/[^a-z0-9._-]/g, "_") || "unknown";
  } catch (error) {
    return "unknown";
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(Object.assign(new Error("payload too large"), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function handleCapture(req, res) {
  if (!authorize(req)) {
    send(res, 401, "Unauthorized\n");
    log("401");
    return;
  }

  let body;
  try {
    body = await readBody(req);
  } catch (error) {
    send(res, error.status || 400, "Bad request\n");
    log(String(error.status || 400));
    return;
  }

  const contentType = String(req.headers["content-type"] || "");
  const boundaryMatch = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType);
  if (!/^multipart\/form-data/i.test(contentType) || !boundaryMatch) {
    send(res, 400, "multipart/form-data required\n");
    log("400");
    return;
  }
  const boundary = (boundaryMatch[1] || boundaryMatch[2] || "").trim();

  const parsed = parseMultipart(body, boundary);
  const parts = parsed.parts;
  const required = ["url", "captured_at", "content_hash", "links", "markdown"];
  for (const key of required) {
    if (typeof parts[key] !== "string" || parts[key].length === 0) {
      send(res, 400, "missing part: " + key + "\n");
      log("400");
      return;
    }
  }

  const contentHash = String(parts.content_hash).trim().toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(contentHash)) {
    send(res, 400, "content_hash must be 64 hex characters\n");
    log("400");
    return;
  }

  let links = [];
  try {
    const parsedLinks = JSON.parse(parts.links);
    if (Array.isArray(parsedLinks)) links = parsedLinks.map(String);
  } catch (error) {
    // Keep the sidecar's links array valid even if a client is sloppy.
    links = [];
  }

  const host = safeHostFromUrl(parts.url);
  const markdown = parts.markdown;
  const split = splitFrontmatter(markdown);
  const calculatedHash = split ? sha256(split.body) : null;

  const directory = path.join(CAPTURE_ROOT, host);
  fs.mkdirSync(directory, { recursive: true });

  const markdownPath = path.join(directory, contentHash + ".md");
  const sidecarPath = path.join(directory, contentHash + ".json");
  fs.writeFileSync(markdownPath, markdown, "utf8");

  const sidecar = {
    received_at: new Date().toISOString(),
    request: {
      method: req.method,
      path: req.url,
      remote_address: req.socket.remoteAddress,
      bytes: body.length,
      content_type: contentType
    },
    host: host,
    parts: {
      url: parts.url,
      captured_at: parts.captured_at,
      content_hash: parts.content_hash,
      links: links,
      links_raw: parts.links,
      markdown: markdown
    },
    files: {
      markdown: parsed.files.markdown || {
        filename: "page-" + contentHash + ".md",
        content_type: "text/markdown; charset=utf-8",
        bytes: Buffer.byteLength(markdown, "utf8")
      }
    },
    links: links,
    content_hash_valid: calculatedHash ? calculatedHash === contentHash : false,
    calculated_content_hash: calculatedHash,
    images_inlined: (markdown.match(/data:image\//g) || []).length
  };

  fs.writeFileSync(sidecarPath, JSON.stringify(sidecar, null, 2) + "\n", "utf8");

  send(
    res,
    201,
    JSON.stringify({
      ok: true,
      markdown: path.relative(process.cwd(), markdownPath),
      sidecar: path.relative(process.cwd(), sidecarPath)
    }),
    "application/json; charset=utf-8"
  );
  log("201 " + host + " " + body.length);
}

const server = http.createServer((req, res) => {
  const method = req.method || "GET";
  const pathname = (() => {
    try {
      return new URL(req.url, "http://localhost").pathname;
    } catch (error) {
      return req.url || "/";
    }
  })();

  if (method === "OPTIONS") {
    send(res, 204, "");
    return;
  }

  if (method === "POST") {
    handleCapture(req, res).catch((error) => {
      send(res, 500, "server error\n");
      log("500");
      process.stderr.write(String((error && error.stack) || error) + "\n");
    });
    return;
  }

  if (method !== "GET" && method !== "HEAD") {
    send(res, 405, "Method not allowed\n");
    return;
  }

  if (pathname === "/" || pathname === "/index.html") {
    send(res, 200, INDEX_HTML, "text/html; charset=utf-8");
    return;
  }
  if (pathname === "/demo" || pathname === "/demo/") {
    send(res, 200, DEMO_HTML, "text/html; charset=utf-8");
    return;
  }
  if (pathname === "/demo/chapter-2" || pathname === "/demo/chapter-2/") {
    send(res, 200, CHAPTER_TWO_HTML, "text/html; charset=utf-8");
    return;
  }
  if (pathname === "/hero.png") {
    send(res, 200, Buffer.from(HERO_PNG_BASE64, "base64"), "image/png");
    return;
  }

  send(res, 404, "Not found\n");
});

server.listen(PORT, "0.0.0.0", () => {
  const address = server.address();
  const actualPort = address && typeof address === "object" ? address.port : PORT;
  log("Capture the Domain stub listening on http://0.0.0.0:" + actualPort);
  log("Demo pages: http://localhost:" + actualPort + "/demo and /demo/chapter-2");
  log("Capture endpoint path: /api/capture (bearer token required)");
  log("Captures directory: " + CAPTURE_ROOT);
});
