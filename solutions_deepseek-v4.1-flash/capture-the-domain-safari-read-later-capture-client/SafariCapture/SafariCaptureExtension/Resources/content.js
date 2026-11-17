/*
 * Capture the Domain - content script.
 *
 * Runs in every frame (all_frames: true) but only the top frame of an
 * armed host produces captures.  Converts the main article to Markdown with
 * image placeholders; the background worker fetches images, hashes the body
 * and uploads it.
 */
(function () {
  "use strict";

  var S = globalThis.SafariCapture;
  if (!S || !S.api) return;
  var api = S.api;

  // Requirement 4: never capture sub-frames.
  if (window.top !== window) return;

  var NOISE_TAGS = new Set([
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "form",
    "noscript"
  ]);

  var BLOCK_TAGS = new Set([
    "address",
    "article",
    "blockquote",
    "details",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "main",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul"
  ]);

  var arm = { until: 0, host: "", at: 0 };
  var readyResolve;
  var readyPromise = new Promise(function (resolve) {
    readyResolve = resolve;
  });
  var captureInFlight = false;
  var spa = null;
  var lastAttempt = { url: "", at: 0 };

  /* ------------------------------------------------------------------ */
  /* Arming state                                                        */
  /* ------------------------------------------------------------------ */

  async function refreshArm() {
    try {
      var stored = await api.storage.local.get([S.KEYS.armedUntil, S.KEYS.armedHost, S.KEYS.armedAt]);
      arm = {
        until: Number(stored[S.KEYS.armedUntil]) || 0,
        host: S.normalizeHost(stored[S.KEYS.armedHost] || ""),
        at: Number(stored[S.KEYS.armedAt]) || 0
      };
    } catch (error) {
      arm = { until: 0, host: "", at: 0 };
    }
    readyResolve();
  }

  api.storage.onChanged.addListener(function (changes, area) {
    if (area !== "local") return;
    if (!changes[S.KEYS.armedUntil] && !changes[S.KEYS.armedHost] && !changes[S.KEYS.armedAt]) {
      return;
    }
    refreshArm();
  });

  function isEligible() {
    return (
      window.top === window &&
      !!arm.host &&
      Date.now() < arm.until &&
      location.hostname.toLowerCase() === arm.host &&
      /^https?:$/.test(location.protocol) &&
      /^text\/html$|^application\/xhtml\+xml$/i.test(document.contentType || "")
    );
  }

  /* ------------------------------------------------------------------ */
  /* Triggering                                                          */
  /* ------------------------------------------------------------------ */

  async function attempt(reason) {
    await readyPromise;
    if (!isEligible()) return;
    if (captureInFlight) return;
    if (reason === "load" && document.readyState !== "complete") return;

    // Early SPA bootstrapping can fire replaceState at almost the same time
    // as the load capture; one snapshot is enough.
    var now = Date.now();
    if (reason === "spa" && lastAttempt.url === location.href && now - lastAttempt.at < 1500) {
      return;
    }

    captureInFlight = true;
    var triggeredAt = Date.now();
    lastAttempt = { url: location.href, at: triggeredAt };

    try {
      var page = extractPage();
      if (!page || !page.markdown || page.markdown.trim().length < 20) {
        await reportClientLog({
          url: location.href,
          status: "failed",
          bytes: 0,
          reason: "no extractable content",
          images_failed: 0
        });
        return;
      }

      if (Date.now() - triggeredAt > S.CAPTURE_BUDGET_MS) {
        await reportClientLog({
          url: location.href,
          status: "failed",
          bytes: S.byteLength(page.markdown),
          reason: "timeout",
          images_failed: 0
        });
        return;
      }

      page.reason = reason;
      page.captured_at = S.nowIso();
      // Hand off and keep watching.  The background performs image fetches,
      // hashing, upload and queueing; a slow endpoint must not block the next
      // SPA navigation in this tab.
      var sending = api.runtime.sendMessage({
        type: "capture",
        triggeredAt: triggeredAt,
        data: page
      });
      if (sending && typeof sending.catch === "function") {
        sending.catch(function () {
          // The background worker may be restarting; the next navigation will
          // try again, and nothing is uploaded more than once by accident.
        });
      }
    } catch (error) {
      // The background worker may be restarting.  A failed message is not a
      // capture; the next navigation/deadline checks still apply.
    } finally {
      captureInFlight = false;
    }
  }

  async function reportClientLog(entry) {
    try {
      await api.runtime.sendMessage({ type: "clientLog", entry: entry });
    } catch (error) {
      // Nothing else to do; the popup log lives in background storage.
    }
  }

  function scheduleInitialCapture() {
    // document_idle/document_start means the load event may already have
    // fired.  Give late async layout a short moment, then capture.
    setTimeout(function () {
      attempt("load");
    }, 350);
  }

  /* ------------------------------------------------------------------ */
  /* History / SPA observation                                           */
  /* ------------------------------------------------------------------ */

  function installHistoryHooks() {
    ["pushState", "replaceState"].forEach(function (name) {
      try {
        var original = history[name];
        if (!original || original.__safariCaptureWrapped) return;
        var wrapped = function () {
          var result = original.apply(this, arguments);
          onHistoryChange();
          return result;
        };
        wrapped.__safariCaptureWrapped = true;
        history[name] = wrapped;
      } catch (error) {
        // A page can freeze history; full navigation still works.
      }
    });

    window.addEventListener("popstate", onHistoryChange, true);
    window.addEventListener("hashchange", onHistoryChange, true);
  }

  function onHistoryChange() {
    if (!arm.host) {
      // Wait for the first storage read, but do not re-enter indefinitely if
      // the extension is simply disarmed.
      readyPromise.then(function () {
        if (isEligible()) scheduleSpaCapture();
      });
      return;
    }
    if (!isEligible()) return;
    scheduleSpaCapture();
  }

  function scheduleSpaCapture() {
    if (spa) {
      spa.bump();
      return;
    }

    var token = {};
    var quietTimer = null;
    var maxTimer = null;
    var observer = null;

    function cleanup() {
      if (quietTimer) clearTimeout(quietTimer);
      if (maxTimer) clearTimeout(maxTimer);
      if (observer) observer.disconnect();
      quietTimer = null;
      maxTimer = null;
      observer = null;
      if (spa && spa.token === token) spa = null;
    }

    function finish() {
      if (!spa || spa.token !== token) return;
      cleanup();
      attempt("spa");
    }

    function bump() {
      if (!spa || spa.token !== token) return;
      if (quietTimer) clearTimeout(quietTimer);
      quietTimer = setTimeout(finish, S.MUTATION_QUIET_MS);
    }

    var target = document.documentElement || document;
    try {
      observer = new MutationObserver(bump);
      observer.observe(target, {
        childList: true,
        subtree: true,
        characterData: true
      });
    } catch (error) {
      observer = null;
    }

    spa = { token: token, bump: bump, cleanup: cleanup };
    bump();
    // A permanently mutating page (timers, autoplay counters) must not starve
    // the capture: force it after four seconds.
    maxTimer = setTimeout(finish, 4000);
  }

  /* ------------------------------------------------------------------ */
  /* Article extraction                                                  */
  /* ------------------------------------------------------------------ */

  function cleanClone(element) {
    var clone = element.cloneNode(true);
    clone
      .querySelectorAll("nav,header,footer,aside,script,style,form,noscript")
      .forEach(function (node) {
        node.remove();
      });
    return clone;
  }

  function textStats(element) {
    var clone = cleanClone(element);
    var text = (clone.textContent || "").replace(/\s+/g, " ").trim();
    var linkLength = 0;
    clone.querySelectorAll("a[href]").forEach(function (anchor) {
      linkLength += (anchor.textContent || "").replace(/\s+/g, " ").trim().length;
    });
    return {
      length: text.length,
      linkDensity: text.length ? linkLength / text.length : 0,
      paragraphs: clone.querySelectorAll("p").length,
      headings: clone.querySelectorAll("h1,h2,h3").length
    };
  }

  function pickRoot() {
    var candidates = [];
    var seen = new Set();
    var selectors = [
      "article",
      "main",
      "[role='main']",
      "[itemprop='articleBody']",
      ".post-content",
      ".entry-content",
      ".article-body",
      ".article__body"
    ];

    selectors.forEach(function (selector) {
      try {
        document.querySelectorAll(selector).forEach(function (element) {
          if (!seen.has(element)) {
            seen.add(element);
            candidates.push(element);
          }
        });
      } catch (error) {
        // ignore unsupported selector
      }
    });

    var body = document.body;
    if (body) {
      if (!seen.has(body)) {
        seen.add(body);
        candidates.push(body);
      }
      Array.prototype.forEach.call(body.children, function (child) {
        if ((child.tagName === "DIV" || child.tagName === "SECTION") && !seen.has(child)) {
          seen.add(child);
          candidates.push(child);
        }
      });
    }

    var best = null;
    var bestScore = -Infinity;

    candidates.forEach(function (element) {
      var stats = textStats(element);
      if (stats.length < 200) return; // fallback below if nothing qualifies
      var score =
        stats.length * (1 - Math.min(0.9, stats.linkDensity * 1.2)) +
        stats.paragraphs * 45 +
        stats.headings * 25;

      if (element.tagName === "ARTICLE") score *= 1.5;
      else if (element.tagName === "MAIN" || element.getAttribute("role") === "main") score *= 1.25;
      else if (element === body) score *= 0.65;

      if (score > bestScore) {
        bestScore = score;
        best = element;
      }
    });

    // Requirement 6: fall back to document.body when no candidate reaches
    // 200 characters of text.
    if (!best) best = body || document.documentElement;

    return { element: best, root: cleanClone(best) };
  }

  function pageTitle() {
    var meta = document.querySelector("meta[property='og:title'],meta[name='twitter:title']");
    if (meta && meta.content && meta.content.trim()) return meta.content.trim();
    if (document.title && document.title.trim()) return document.title.trim();
    var h1 = document.querySelector("h1");
    if (h1 && h1.textContent.trim()) return h1.textContent.replace(/\s+/g, " ").trim();
    return location.hostname;
  }

  function collectLinks(root) {
    var links = [];
    var seen = new Set();
    var pageHost = location.host;

    root.querySelectorAll("a[href]").forEach(function (anchor) {
      var raw = String(anchor.getAttribute("href") || "").trim();
      if (!raw || raw.charAt(0) === "#") return;
      if (/^(mailto|javascript|tel|data|blob):/i.test(raw)) return;

      var url;
      try {
        url = new URL(raw, document.baseURI || location.href);
      } catch (error) {
        return;
      }
      if (!/^https?:$/.test(url.protocol)) return;
      if (url.host !== pageHost) return; // same-host only
      // Fragment-only targets were skipped above.  A real page URL that also
      // carries a fragment remains a distinct same-host URL.
      if (!seen.has(url.href)) {
        seen.add(url.href);
        links.push(url.href);
      }
    });

    return links;
  }

  function imageToken(index) {
    return "@@SC_IMG_" + index + "@@";
  }

  function altText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .replace(/[[\]()]/g, "")
      .trim();
  }

  function renderImage(image, context) {
    var raw = image.getAttribute("src") || "";
    if (!raw) {
      var srcset = image.getAttribute("srcset") || "";
      if (srcset) raw = srcset.split(",")[0].trim().split(/\s+/)[0];
    }
    if (!raw) return "";

    var absolute;
    try {
      absolute = new URL(raw, document.baseURI || location.href).href;
    } catch (error) {
      return "";
    }

    if (/^data:/i.test(absolute)) {
      return /^data:image\//i.test(absolute)
        ? "![" + altText(image.getAttribute("alt")) + "](" + absolute + ")"
        : "";
    }
    if (!/^https?:/i.test(absolute)) return ""; // blob:, about:, etc.

    var index = context.images.length;
    context.images.push({
      url: absolute,
      alt: altText(image.getAttribute("alt"))
    });
    return "![" + altText(image.getAttribute("alt")) + "](" + imageToken(index) + ")";
  }

  function mdUrl(url) {
    return String(url)
      .replace(/ /g, "%20")
      .replace(/\(/g, "%28")
      .replace(/\)/g, "%29");
  }

  function escapeText(value) {
    return String(value == null ? "" : value)
      .replace(/\s+/g, " ")
      .replace(/([\\`*_[\]<>])/g, "\\$1")
      .replace(/^(\s*)([#>+-])(?=\s)/gm, "$1\\$2")
      .replace(/^(\s*)(\d+)\.(?=\s)/gm, "$1$2\\.");
  }

  function inlineCode(value) {
    var text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    var longest = 0;
    var runs = text.match(/`+/g) || [];
    runs.forEach(function (run) {
      longest = Math.max(longest, run.length);
    });
    var fence = "`".repeat(longest + 1);
    var pad = /^`|`$/.test(text) ? " " : "";
    return fence + pad + text + pad + fence;
  }

  function inlineElement(element, context) {
    var tag = element.tagName.toLowerCase();
    var children = Array.prototype.slice.call(element.childNodes);

    switch (tag) {
      case "br":
        return "\n";
      case "wbr":
        return "";
      case "strong":
      case "b": {
        var bold = inlineNodes(children, context);
        return bold ? "**" + bold + "**" : "";
      }
      case "em":
      case "i": {
        var italic = inlineNodes(children, context);
        return italic ? "*" + italic + "*" : "";
      }
      case "del":
      case "s":
      case "strike": {
        var struck = inlineNodes(children, context);
        return struck ? "~~" + struck + "~~" : "";
      }
      case "code":
      case "kbd":
      case "samp":
        return inlineCode(element.textContent || "");
      case "a": {
        var label = inlineNodes(children, context);
        var raw = String(element.getAttribute("href") || "").trim();
        if (!raw || raw.charAt(0) === "#") return label;
        if (/^(mailto|javascript|tel|data|blob):/i.test(raw)) return label;

        var url;
        try {
          url = new URL(raw, document.baseURI || location.href);
        } catch (error) {
          return label;
        }
        if (!/^https?:$/.test(url.protocol)) return label;
        if (!label) label = escapeText(url.href);
        return "[" + label + "](" + mdUrl(url.href) + ")";
      }
      case "img":
        return renderImage(element, context);
      case "picture": {
        var pictureImage = element.querySelector("img");
        return pictureImage ? renderImage(pictureImage, context) : "";
      }
      case "sub":
      case "sup":
      case "mark":
      case "small":
      case "span":
      case "time":
      case "abbr":
      case "cite":
      case "q":
        return inlineNodes(children, context);
      case "svg":
      case "canvas":
      case "video":
      case "audio":
      case "iframe":
      case "object":
      case "embed":
      case "input":
      case "button":
        return "";
      default:
        return inlineNodes(children, context);
    }
  }

  function inlineNodes(nodes, context) {
    var output = "";
    Array.prototype.forEach.call(nodes || [], function (node) {
      if (node.nodeType === 3) {
        output += escapeText(node.nodeValue || "");
      } else if (node.nodeType === 1) {
        output += inlineElement(node, context);
      }
    });
    return output
      .replace(/[ \t]+/g, " ")
      .replace(/ *\n */g, "\n")
      .replace(/\n{2,}/g, "\n")
      .trim();
  }

  function renderPre(element, context) {
    var codeElement = element.querySelector("code") || element;
    var text = String(codeElement.textContent || "")
      .replace(/\r\n?/g, "\n")
      .replace(/\n$/, "");
    if (!text.trim()) return "";

    var classes = String(codeElement.className || "") + " " + String(element.className || "");
    var languageMatch = classes.match(/(?:language|lang)-([A-Za-z0-9_+.-]+)/);
    var language = languageMatch ? languageMatch[1] : "";

    var longest = 0;
    var runs = text.match(/`+/g) || [];
    runs.forEach(function (run) {
      longest = Math.max(longest, run.length);
    });
    var fence = "`".repeat(Math.max(3, longest + 1));
    return fence + language + "\n" + text + "\n" + fence;
  }

  function renderTable(element, context) {
    var rows = Array.prototype.filter.call(element.querySelectorAll("tr"), function (row) {
      return row.closest("table") === element;
    });
    if (!rows.length) return "";

    var matrix = rows.map(function (row) {
      return Array.prototype.filter
        .call(row.children, function (cell) {
          return cell.tagName === "TD" || cell.tagName === "TH";
        })
        .map(function (cell) {
          return inlineNodes(Array.prototype.slice.call(cell.childNodes), context)
            .replace(/\|/g, "\\|")
            .replace(/\n+/g, " ")
            .trim();
        });
    });

    var width = 0;
    matrix.forEach(function (row) {
      width = Math.max(width, row.length);
    });
    if (!width) return "";

    matrix.forEach(function (row) {
      while (row.length < width) row.push("");
    });

    function format(row) {
      return "| " + row.join(" | ") + " |";
    }

    var lines = [format(matrix[0]), format(new Array(width).fill("---"))];
    for (var i = 1; i < matrix.length; i += 1) lines.push(format(matrix[i]));
    return lines.join("\n");
  }

  function renderFigure(element, context) {
    var parts = [];
    Array.prototype.forEach.call(element.children, function (child) {
      var tag = child.tagName.toLowerCase();
      if (tag === "img") {
        var image = renderImage(child, context);
        if (image) parts.push(image);
      } else if (tag === "figcaption") {
        var caption = inlineNodes(Array.prototype.slice.call(child.childNodes), context).trim();
        if (caption) parts.push("_" + caption + "_");
      } else if (tag === "picture" || tag === "a") {
        var inline = inlineElement(child, context);
        if (inline) parts.push(inline);
      } else {
        var block = renderBlock(child, context);
        if (block) parts.push(block);
      }
    });
    if (!parts.length) {
      return renderNodes(Array.prototype.slice.call(element.childNodes), context);
    }
    return parts.join("\n\n");
  }

  function renderList(element, context, depth) {
    var ordered = element.tagName === "OL";
    var number = parseInt(element.getAttribute("start"), 10);
    if (!isFinite(number) || number < 1) number = 1;

    var lines = [];
    Array.prototype.forEach.call(element.children, function (item) {
      if (item.tagName !== "LI") return;

      var own = [];
      var nested = [];
      Array.prototype.forEach.call(item.childNodes, function (node) {
        if (node.nodeType === 1 && (node.tagName === "UL" || node.tagName === "OL")) {
          nested.push(node);
        } else {
          own.push(node);
        }
      });

      var text = renderNodes(own, context).trim();
      var indent = "  ".repeat(depth);
      var marker = ordered ? number++ + ". " : "- ";
      var textLines = text ? text.split("\n") : [""];

      if (!text) {
        lines.push(indent + marker.trim());
      } else {
        lines.push(indent + marker + textLines[0]);
        for (var i = 1; i < textLines.length; i += 1) {
          lines.push(indent + "  " + textLines[i]);
        }
      }

      nested.forEach(function (subList) {
        var rendered = renderList(subList, context, depth + 1);
        if (rendered) lines.push(rendered);
      });
    });

    return lines.join("\n");
  }

  function renderBlock(element, context) {
    var tag = element.tagName.toLowerCase();
    var children = Array.prototype.slice.call(element.childNodes);

    switch (tag) {
      case "h1":
      case "h2":
      case "h3":
      case "h4":
      case "h5":
      case "h6": {
        var heading = inlineNodes(children, context).replace(/\s+/g, " ").trim();
        return heading ? "#".repeat(Number(tag.charAt(1))) + " " + heading : "";
      }
      case "p":
        return inlineNodes(children, context).trim();
      case "hr":
        return "---";
      case "ul":
      case "ol":
        return renderList(element, context, 0);
      case "li":
        return inlineNodes(children, context).trim();
      case "blockquote": {
        var quoted = renderNodes(children, context);
        if (!quoted) return "";
        return quoted
          .split("\n")
          .map(function (line) {
            return line ? "> " + line : ">";
          })
          .join("\n");
      }
      case "pre":
        return renderPre(element, context);
      case "table":
        return renderTable(element, context);
      case "figure":
        return renderFigure(element, context);
      case "figcaption": {
        var caption = inlineNodes(children, context).trim();
        return caption ? "_" + caption + "_" : "";
      }
      case "dl": {
        var definitionLines = [];
        Array.prototype.forEach.call(element.querySelectorAll("dt,dd"), function (node) {
          if (node.closest("dl") !== element) return;
          if (node.tagName === "DT") {
            var term = inlineNodes(Array.prototype.slice.call(node.childNodes), context).trim();
            if (term) definitionLines.push("**" + term + "**");
          } else {
            var definition = inlineNodes(Array.prototype.slice.call(node.childNodes), context).trim();
            if (definition) definitionLines.push(definition);
          }
        });
        return definitionLines.join("\n\n");
      }
      default:
        return renderNodes(children, context);
    }
  }

  function renderNodes(nodes, context) {
    var blocks = [];
    var inlineBuffer = [];

    function flush() {
      if (!inlineBuffer.length) return;
      var text = inlineNodes(inlineBuffer, context).trim();
      if (text) blocks.push(text);
      inlineBuffer = [];
    }

    Array.prototype.forEach.call(nodes || [], function (node) {
      if (node.nodeType === 3) {
        if (node.nodeValue && node.nodeValue.trim()) inlineBuffer.push(node);
        else if (inlineBuffer.length) inlineBuffer.push(node);
        return;
      }
      if (node.nodeType !== 1) return;

      var tag = node.tagName.toLowerCase();
      if (NOISE_TAGS.has(tag)) return;

      if (BLOCK_TAGS.has(tag)) {
        flush();
        var block = renderBlock(node, context);
        if (block) blocks.push(block);
      } else {
        inlineBuffer.push(node);
      }
    });

    flush();
    return blocks.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  function extractPage() {
    if (!document.body) return null;

    var picked = pickRoot();
    if (!picked.root) return null;

    var context = { images: [] };
    var markdown = renderNodes(Array.prototype.slice.call(picked.root.childNodes), context);
    if (!markdown) return null;

    return {
      url: location.href,
      title: pageTitle(),
      host: location.hostname.toLowerCase(),
      markdown: markdown,
      images: context.images,
      links: collectLinks(picked.root)
    };
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */

  installHistoryHooks();

  if (document.readyState === "complete") {
    scheduleInitialCapture();
  } else {
    window.addEventListener("load", scheduleInitialCapture, { once: true });
  }

  refreshArm();
})();
