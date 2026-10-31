# Repo Apps

**Difficulty:** extreme  |  **Stack:** HTML/CSS/JavaScript (standalone web app)  |  **Estimated time:** 8–15+ hours

## The Problem

Developers frequently encounter interesting GitHub repositories that they want to inspect, understand, and even run without cloning them or setting up a local development environment.

Repo Apps is a mobile-first, standalone browser application that turns a GitHub repository URL into an interactive repository explorer. Users should be able to browse directories, inspect source code, render Markdown documents, and preview HTML applications directly inside the interface.

The application must go beyond being a simple GitHub file viewer. Its defining feature is the ability to preview standalone HTML applications using their associated CSS and JavaScript dependencies, whether those dependencies live inside the repository or are loaded from external CDNs.

The entire experience must work from a single HTML file that users can simply open in their browser. No installation, build process, local server, or backend should be required.

## Requirements

1. **Standalone application**
   - Deliver the entire application as a single `index.html` file.
   - Include all application HTML, CSS, and JavaScript in that file.
   - The application must work when opened directly in a modern browser using `file://`.
   - No build process, installation, local server, or backend may be required.
   - External libraries may be loaded through CDNs.
   - Handle unavailable CDN dependencies gracefully.

2. **GitHub repository input**
   - Provide a prominent input field for a GitHub repository URL.
   - Accept URLs in formats such as:
     - `https://github.com/owner/repository`
     - `https://github.com/owner/repository/tree/branch/path`
     - GitHub URLs containing a specific file.
   - Extract the repository owner, repository name, branch, and optional directory or file path.
   - Support default branches other than `main` and `master`.
   - Validate URLs and display useful errors for invalid or inaccessible repositories.
   - Provide an option to load a different repository without restarting the application.

3. **Repository explorer**
   - Display the repository's directory and file structure.
   - Allow users to navigate directories interactively.
   - Support nested directories.
   - Display filenames and distinguish file types visually.
   - Display the current directory path using breadcrumbs.
   - Allow navigation back to parent directories.
   - Support browser-style back and forward navigation within the repository.
   - Provide a loading indicator while retrieving repository contents.
   - Handle empty directories, inaccessible files, large repositories, API errors, and rate limits gracefully.
   - Avoid downloading the entire repository unnecessarily. Retrieve content on demand.

4. **Source code viewer**
   - Implement a dedicated source code viewer.
   - Support syntax highlighting for common languages, including:
     - JavaScript
     - TypeScript
     - Python
     - HTML
     - CSS
     - JSON
     - Java
     - C/C++
     - SQL
     - Shell scripts
     - YAML
     - XML
     - Markdown (raw mode)
   - Display line numbers.
   - Preserve indentation and formatting.
   - Support horizontal scrolling for long lines.
   - Provide a copy-to-clipboard action.
   - Provide a download action for individual files.
   - Use a readable monospace font.
   - Handle large files without freezing the interface.

5. **Markdown renderer**
   - Automatically recognize Markdown files (`.md`, `.markdown`).
   - Render Markdown as formatted content by default.
   - Support headings, paragraphs, links, lists, blockquotes, tables, images, inline code, and fenced code blocks.
   - Support GitHub-style Markdown features where practical.
   - Provide an obvious toggle between:
     - Rendered Markdown
     - Raw Markdown source
   - Preserve the selected viewing mode while navigating between Markdown files where appropriate.
   - Render repository-relative images and links correctly.
   - Resolve relative links against the current repository path.
   - Handle missing images and broken links gracefully.
   - Sanitize rendered Markdown to prevent script injection and unsafe HTML execution.

6. **HTML application preview — core feature**
   - Automatically recognize HTML files (`.html`, `.htm`).
   - Provide an explicit **Preview as App** action.
   - Allow switching between:
     - Source Code
     - Preview as App
   - Render the HTML document in an isolated iframe.
   - Preserve the original document's HTML structure and behavior as closely as possible.
   - Support CSS and JavaScript dependencies referenced by the HTML document.
   - Resolve relative dependency paths against the original HTML file's repository location.
   - Support dependencies located in:
     - The same directory.
     - Parent directories.
     - Nested repository directories.
   - Support absolute URLs and external CDN dependencies.
   - Support common references such as:
     - `<link rel="stylesheet" href="./styles.css">`
     - `<script src="./app.js"></script>`
     - `<script src="../shared/utils.js"></script>`
     - `<img src="./assets/image.png">`
     - External CDN stylesheets and scripts.
   - Support inline CSS and JavaScript.
   - Support multiple CSS and JavaScript dependencies.
   - Preserve dependency ordering, particularly for scripts.
   - Support common standalone HTML projects that do not require a backend or server-side rendering.
   - Provide a preview loading indicator and meaningful error reporting.
   - Include a refresh preview action.
   - Allow the preview to occupy the full available application area.
   - Provide a way to return immediately to the source.
   - Do not execute repository HTML in the application's own DOM or execution context.
   - Use iframe sandboxing and an appropriate security boundary.
   - Clearly document unavoidable browser security limitations.

7. **Preview dependency resolver**
   - Implement a dependency-resolution layer specifically for HTML previews.
   - Parse HTML documents and identify local resource references.
   - Resolve local paths to their corresponding GitHub repository files.
   - Retrieve referenced resources using the GitHub API or raw-content endpoints.
   - Reconstruct a preview document with resolved resource references.
   - Preserve the original resource order.
   - Avoid unnecessarily fetching the same dependency multiple times.
   - Cache successfully retrieved resources for the current session.
   - Detect missing dependencies and show which resource failed.
   - Support URL encoding and paths containing spaces.
   - Avoid corrupting JavaScript or CSS when rewriting resource references.
   - Do not blindly replace arbitrary text inside source files.
   - Account for CSS `url(...)` references, including relative fonts and images.
   - Support CSS `@import` dependencies.
   - Detect circular CSS imports and prevent infinite resolution loops.
   - Handle external CDN resources without attempting to fetch and rewrite their contents unnecessarily.
   - Ensure that the resulting preview remains isolated from the parent application.

8. **Repository navigation and file actions**
   - Allow opening files directly from the directory explorer.
   - Provide clear visual feedback for the currently selected file.
   - Allow switching between files without losing repository context.
   - Support opening README files conveniently.
   - Support common project entry points such as:
     - `index.html`
     - `README.md`
     - `package.json`
   - Provide a repository-level home or overview screen.
   - Display basic repository information where available, including repository name, description, default branch, and GitHub link.

9. **Repository history and local storage**
   - Persist recently visited repositories using browser localStorage or IndexedDB.
   - Store at least:
     - Repository owner.
     - Repository name.
     - Repository URL.
     - Last visited timestamp.
     - Default branch when known.
   - Display a repository history screen.
   - Allow reopening previously visited repositories.
   - Allow removing individual repositories from history.
   - Provide an option to clear all history.
   - Display repositories as attractive cards or thumbnails.
   - Include repository name, owner, and last visited information.
   - Avoid storing large source files permanently unless explicitly necessary.
   - Handle unavailable or corrupted local storage gracefully.

10. **Repository dashboard and thumbnails**
    - Create an attractive initial landing screen.
    - Show recently visited repositories.
    - Provide a prominent action to open a new repository.
    - Give repository cards a clear visual hierarchy.
    - Use repository avatars or other GitHub metadata where available.
    - Provide empty-state guidance for first-time users.
    - Make the dashboard useful on both small and large screens.

11. **Responsive mobile-first interface**
    - Optimize the entire experience for mobile devices.
    - Treat mobile as the primary design target.
    - Support desktop, tablet, and mobile layouts.
    - On mobile, provide an intuitive way to open and close the repository file explorer.
    - Use a drawer, collapsible panel, or another appropriate navigation pattern.
    - Ensure source code and Markdown remain readable on narrow screens.
    - Make controls sufficiently large for touch interaction.
    - Avoid horizontal page overflow.
    - Ensure the HTML preview can use the available screen area.
    - Provide a clear navigation hierarchy.
    - Support both portrait and landscape orientations.
    - Preserve application state when switching between navigation panels and viewing modes.

12. **Application design and usability**
    - Use a polished developer-tool aesthetic.
    - Provide a consistent visual design system.
    - Support light and dark themes.
    - Make the theme switch persistent.
    - Include useful icons for files, folders, actions, and navigation.
    - Provide contextual actions rather than overcrowding the interface.
    - Display useful loading, empty, success, and error states.
    - Avoid unnecessary modal dialogs.
    - Make the most important actions discoverable.
    - Ensure the application feels like a real product rather than a basic prototype.

13. **Search and navigation enhancements**
    - Provide a way to search filenames within the currently loaded repository.
    - Allow filtering files by name and extension.
    - Highlight matching results.
    - Selecting a result must open the corresponding file.
    - Do not require downloading the entire repository just to perform basic filename filtering.

14. **GitHub integration and API handling**
    - Use GitHub's public API for repository metadata and directory listings.
    - Support public repositories without requiring authentication.
    - Clearly communicate GitHub API rate-limit restrictions.
    - Handle HTTP errors and malformed responses.
    - Prefer efficient API requests.
    - Cache directory listings and file contents for the active session.
    - Use GitHub's default branch information instead of assuming a particular branch name.
    - Never embed a personal access token or other secret in the application.
    - Explain any limitations affecting private repositories.

15. **Performance and reliability**
    - Keep the application responsive while retrieving files.
    - Use asynchronous operations.
    - Prevent stale requests from overwriting newer navigation state.
    - Avoid unnecessary DOM reconstruction.
    - Implement sensible caching and cache invalidation.
    - Handle network failures without crashing the application.
    - Avoid excessive API requests when navigating repeatedly.
    - Keep memory usage reasonable.
    - Ensure long source files and large directory listings do not make the application unusable.

16. **Security**
    - Treat repository content as untrusted input.
    - Sanitize Markdown rendering.
    - Prevent repository source files from executing inside the parent application.
    - Isolate HTML previews using sandboxed iframes.
    - Avoid exposing parent application state or storage to previewed content.
    - Never evaluate repository JavaScript in the parent application's execution context.
    - Clearly distinguish between viewing source and executing a preview.
    - Do not claim that sandboxing makes arbitrary repository code completely safe.
    - Provide appropriate warnings before running repository HTML applications.

17. **Application documentation**
    - Include an in-app About or Help section.
    - Explain how to load a GitHub repository.
    - Explain the difference between source viewing and HTML preview.
    - Explain Markdown rendering and raw mode.
    - Explain preview dependency resolution.
    - Explain GitHub API limitations.
    - Explain browser security restrictions.
    - Make the interface understandable without consulting external documentation.

18. **Sign-off:** Display the date and time the solution was produced and the model/author that produced it. Make this visible in an About section or application footer. Use the actual production timestamp and actual model identity, not fabricated values.

## Constraints

- Deliver exactly one standalone HTML file: `index.html`.
- HTML, CSS, and JavaScript must be contained in that file.
- No installation, build tools, package managers, or local development server.
- No backend or external server controlled by the application author.
- External CDN libraries are permitted.
- Use vanilla JavaScript where practical.
- Libraries such as Prism.js, Highlight.js, Marked, DOMPurify, or equivalent may be used when they materially improve the result.
- The GitHub API and external CDN resources are permitted network dependencies.
- Public GitHub repositories must work without authentication.
- Use browser localStorage or IndexedDB for persistent history and preferences.
- Do not require a GitHub personal access token.
- Repository contents must be retrieved on demand.
- The application must be compatible with modern versions of Chrome, Firefox, Safari, and Edge.
- Use an iframe security boundary for HTML previews.
- Do not use `eval()` or `new Function()` to execute repository code inside the main application.
- The application must remain functional when optional libraries fail to load, with graceful degradation.
- Do not silently pretend unsupported backend-dependent applications can run in the browser.

## Sample Data / Inputs

Use these representative public repository URLs to demonstrate the application:

**Repository 1 — Basic HTML project**

`https://github.com/mdn/beginner-html-site`

Expected demonstration:
- Load the repository.
- Browse its directories and files.
- Open HTML files as source.
- Preview an HTML document.
- Resolve local CSS, JavaScript, and image dependencies where present.

**Repository 2 — Documentation-oriented project**

`https://github.com/markedjs/marked`

Expected demonstration:
- Browse the repository.
- Open Markdown documentation.
- Switch between rendered Markdown and raw source.
- Browse nested directories.

**Repository 3 — JavaScript project**

`https://github.com/lodash/lodash`

Expected demonstration:
- Browse a relatively large repository.
- Search filenames.
- Open JavaScript source files.
- View syntax-highlighted code.

These are demonstration inputs, not hardcoded repositories. The application must accept arbitrary compatible public GitHub repository URLs.

## Deliverable

Produce:

- `index.html` — the complete standalone application.

Run instructions:

1. Save the generated file as `index.html`.
2. Open it directly in Chrome, Firefox, Safari, or Edge.
3. Enter a public GitHub repository URL.
4. Start browsing immediately.

No additional setup commands should be necessary.

## Done When

- [ ] The application opens directly from a standalone HTML file.
- [ ] A user can enter a public GitHub repository URL and load it.
- [ ] Repository metadata and the default branch are detected correctly.
- [ ] The directory explorer supports nested navigation.
- [ ] Breadcrumbs and back navigation work correctly.
- [ ] Source code is displayed with syntax highlighting and line numbers.
- [ ] Markdown files render correctly.
- [ ] Markdown can be switched between rendered and raw modes.
- [ ] Relative Markdown links and images are resolved appropriately.
- [ ] HTML files can be opened in source mode.
- [ ] The **Preview as App** action opens an isolated HTML preview.
- [ ] Local CSS and JavaScript dependencies resolve correctly.
- [ ] Nested and parent-relative dependencies are supported.
- [ ] CSS imports and relative CSS assets are handled where supported.
- [ ] External CDN dependencies remain functional where browser policies permit.
- [ ] Script dependency ordering is preserved.
- [ ] Preview refresh and source/preview switching work.
- [ ] Repository history persists after closing and reopening the browser.
- [ ] Repository cards allow reopening and removing repositories.
- [ ] Search can find filenames without downloading every file.
- [ ] Light and dark themes work and persist.
- [ ] The interface is usable on mobile and desktop.
- [ ] API errors, missing files, and rate limits produce understandable feedback.
- [ ] Previewed repository code cannot directly access the parent application's JavaScript context or local storage.
- [ ] The interface clearly communicates preview security limitations.
- [ ] The application remains usable if an optional CDN library fails.
- [ ] The About section or footer displays the production date/time and model/author sign-off.

## Stretch Goals (optional)

1. **GitHub branch switching:** Allow users to switch branches and refresh the repository explorer accordingly.

2. **Multi-file preview workspace:** Allow HTML previews to navigate between linked local HTML pages while keeping the preview isolated and maintaining the correct repository-relative paths.

3. **Advanced developer experience:** Add file tabs, keyboard shortcuts, fullscreen preview, a resizable desktop explorer panel, and a quick-access command palette.

4. **Repository comparison:** Allow two repositories or branches to be opened and their source files compared side by side.

5. **Offline revisit:** Retain previously loaded repository metadata and selected file contents in a controlled local cache, allowing previously viewed content to remain accessible when offline.