package dev.oneshot.outbox.web;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Human-readable API docs rendered from /openapi.json in the browser.
 * No CDN, no external assets, no Swagger UI dependency.
 */
@RestController
public class DocsController {

    @GetMapping(value = "/api/docs", produces = MediaType.TEXT_HTML_VALUE)
    public String docs() {
        return """
                <!doctype html>
                <html lang="en">
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>Outbox API docs</title>
                  <style>
                    :root { color-scheme: light dark; }
                    body { font: 15px/1.55 ui-sans-serif, system-ui, sans-serif; max-width: 980px;
                           margin: 0 auto; padding: 24px; background: Canvas; color: CanvasText; }
                    h1 { font-size: 1.6rem; margin-bottom: .2rem; }
                    .sub { opacity: .7; margin: 0 0 1.4rem; }
                    .endpoint { border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
                                border-radius: 10px; padding: 12px 14px; margin: 10px 0; }
                    .method { display: inline-block; font-weight: 700; font-size: .75rem; letter-spacing: .06em;
                              padding: 3px 8px; border-radius: 999px; background: #2563eb; color: #fff; margin-right: 8px; }
                    .method.post { background: #15803d; } .method.patch { background: #b45309; }
                    .method.delete { background: #b91c1c; } .method.put { background: #7c3aed; }
                    code, .path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
                    .summary { font-weight: 600; }
                    .desc { opacity: .82; margin-top: 4px; }
                    .badge { font-size: .7rem; border: 1px solid currentColor; border-radius: 999px;
                             padding: 1px 6px; opacity: .7; margin-left: 6px; }
                    a { color: #2563eb; }
                    .error { color: #b91c1c; }
                    ul.tags { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; }
                    ul.tags li { border: 1px solid color-mix(in srgb, CanvasText 22%, transparent);
                                 border-radius: 999px; padding: 3px 10px; font-size: .82rem; }
                  </style>
                </head>
                <body>
                  <h1>Human-in-the-Loop Outbox API</h1>
                  <p class="sub">Rendered from <a href="/openapi.json">/openapi.json</a>.
                     The raw spec is always authoritative.</p>
                  <ul class="tags" id="tags"></ul>
                  <div id="out">Loading the OpenAPI document…</div>
                  <script>
                    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c =>
                      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
                    fetch('/openapi.json').then(r => {
                      if (!r.ok) throw new Error('HTTP ' + r.status);
                      return r.json();
                    }).then(spec => {
                      const tags = new Set();
                      const groups = new Map();
                      for (const [path, ops] of Object.entries(spec.paths || {})) {
                        for (const [method, op] of Object.entries(ops)) {
                          if (!op || typeof op !== 'object') continue;
                          const tag = (op.tags && op.tags[0]) || 'Other';
                          tags.add(tag);
                          if (!groups.has(tag)) groups.set(tag, []);
                          groups.get(tag).push({path, method, op});
                        }
                      }
                      document.getElementById('tags').innerHTML =
                        [...tags].map(t => '<li>' + esc(t) + '</li>').join('');
                      let html = '';
                      for (const [tag, items] of groups) {
                        html += '<h2>' + esc(tag) + '</h2>';
                        for (const {path, method, op} of items) {
                          const m = method.toLowerCase();
                          html += '<div class="endpoint"><div><span class="method ' + m + '">'
                            + esc(method.toUpperCase()) + '</span><span class="path">' + esc(path) + '</span>'
                            + (op.summary ? '<span class="badge">' + esc(op.summary) + '</span>' : '')
                            + '</div>'
                            + (op.description ? '<div class="desc">' + esc(op.description) + '</div>' : '')
                            + '</div>';
                        }
                      }
                      html += '<h2>Specification</h2><p>OpenAPI ' + esc(spec.openapi)
                        + ' — ' + Object.keys(spec.paths || {}).length + ' paths, '
                        + Object.keys(spec.components?.schemas || {}).length + ' schemas.</p>';
                      document.getElementById('out').innerHTML = html;
                    }).catch(err => {
                      document.getElementById('out').innerHTML =
                        '<p class="error">Could not load /openapi.json: ' + esc(err.message) + '</p>';
                    });
                  </script>
                </body>
                </html>
                """;
    }
}
