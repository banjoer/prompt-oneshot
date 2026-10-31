# RepoLens — Mobile-First GitHub Repository Explorer

**Difficulty:** hard  |  **Stack:** HTML/CSS/JavaScript (standalone web app)  |  **Estimated time:** 4–8 hours

## The Problem

Developers frequently encounter interesting GitHub repositories that they want to inspect without cloning them, opening a desktop IDE, or navigating GitHub's relatively dense mobile interface.

RepoLens is a self-contained, mobile-first web application that turns any public GitHub repository URL into an interactive repository browser. Users should be able to explore folders, inspect source files with syntax highlighting, and read Markdown documents in a properly rendered reading view, with the ability to switch between rendered Markdown and raw source.

The application should also act as a lightweight personal repository library, remembering previously visited repositories and making it easy to return to them. The experience should feel like a compact, polished code-reading application rather than a miniature GitHub clone.

## Requirements

1. **Repository URL input**
   - Provide a prominent input where users can paste a GitHub repository URL.
   - Support standard repository URLs:
     - `https://github.com/owner/repository`
     - `https://github.com/owner/repository/tree/branch/path`
   - Extract the owner, repository name, branch, and optional starting directory.
   - Also support convenient `owner/repository` notation.
   - Validate URLs and provide useful error messages for invalid or unsupported repositories.
   - Loading a repository must not require a page refresh.

2. **Repository navigation**
   - Display the repository's directory structure in an interactive file browser.
   - Allow users to navigate into directories and return to parent directories.
   - Display file and folder names, with recognizable icons based on file type.
   - Include breadcrumbs showing the current directory.
   - Support nested directories without imposing an arbitrary shallow navigation limit.
   - Display a loading indicator while retrieving repository contents.
   - Provide useful empty states and error handling for inaccessible or nonexistent paths.
   - Include a convenient repository-level navigation action to return to the root directory.

3. **File viewing**
   - Selecting a file must open it inside the application's main reading area.
   - Detect the file type using its extension.
   - Display a filename, file type, and relevant repository path.
   - Include a source-code viewer with:
     - Syntax highlighting.
     - Line numbers.
     - Monospaced typography.
     - Horizontal scrolling for long lines.
     - A copy-to-clipboard action.
     - A way to close the current file and return to browsing.
   - Support common programming languages, including JavaScript, TypeScript, Python, Java, HTML, CSS, JSON, YAML, SQL, and shell scripts.
   - Provide a sensible fallback for unsupported file types.
   - Handle large files gracefully, with appropriate loading feedback and a clear indication when a file exceeds the application's practical display limits.

4. **Markdown rendering**
   - Automatically detect Markdown files (`.md`, `.markdown`, and `.mdown`).
   - Provide two viewing modes:
     - **Rendered:** A readable Markdown document with headings, paragraphs, tables, lists, blockquotes, links, inline code, and fenced code blocks.
     - **Raw:** The original Markdown source displayed in the syntax-highlighted code viewer.
   - Provide a clearly visible toggle between Rendered and Raw.
   - Preserve readable typography and spacing in rendered mode.
   - Support GitHub-style Markdown features where practical.
   - Resolve relative Markdown links and images against the repository context where possible.
   - Clicking an internal Markdown link should navigate within RepoLens rather than unnecessarily taking the user outside the application.
   - Open external links safely in a new browser tab.
   - Sanitize rendered Markdown to prevent script injection and unsafe HTML execution.

5. **Repository metadata**
   - Show repository owner and name.
   - Display the default branch and repository description when available.
   - Show repository visibility and language information when available.
   - Include a link to open the original repository on GitHub.
   - Provide a clear visual indication of the currently selected repository.

6. **Repository library and history**
   - Maintain a locally persisted collection of previously visited repositories.
   - Use browser localStorage or IndexedDB.
   - Store at least:
     - Repository owner.
     - Repository name.
     - Repository URL.
     - Default or selected branch.
     - Last visited timestamp.
   - Display recently visited repositories in a dedicated library or navigation section.
   - Allow users to reopen a previous repository with one action.
   - Allow users to remove individual repositories from history.
   - Allow users to clear the entire history.
   - Avoid adding duplicate entries when reopening the same repository.
   - Update the last-visited timestamp when a repository is opened.
   - Preserve history after browser refreshes and application restarts.

7. **Repository library presentation**
   - Give each saved repository a visually distinct entry or card.
   - Display owner/name, description when available, primary language when available, and last-visited information.
   - Use initials, simple generated avatars, or another lightweight visual treatment where appropriate.
   - Make repository cards easy to select on mobile.
   - Provide a convenient way to add another repository directly from the library.
   - Include a useful empty state explaining how to add the first repository.

8. **Responsive interface**
   - Design mobile-first, assuming that most users will access the application on a smartphone.
   - On mobile:
     - Use a compact navigation layout.
     - Keep repository browsing and file reading comfortable on narrow screens.
     - Use a dedicated drawer, overlay, or equivalent for repository navigation.
     - Make the file browser and reader easy to switch between.
     - Ensure controls have sufficiently large touch targets.
     - Prevent horizontal overflow in the overall interface.
   - On desktop:
     - Use a multi-panel layout where practical.
     - Keep repository navigation visible alongside the file reader.
     - Use available screen width efficiently.
   - Support both portrait and landscape mobile orientations.
   - Respect safe-area insets on devices that have them.
   - Use responsive typography and spacing.

9. **Navigation and usability**
   - Provide clear navigation between:
     - Repository library.
     - Current repository browser.
     - Current file reader.
   - Include a back-navigation mechanism appropriate to the current screen.
   - Ensure the application remains usable when browser back/forward navigation is used.
   - Preserve the currently selected repository and navigation path when switching between reading and browsing views.
   - Provide consistent loading, error, and empty states.
   - Avoid unnecessary modal dialogs.
   - Add lightweight toast notifications for actions such as copying code, saving repositories, and encountering recoverable errors.

10. **GitHub integration**
    - Use GitHub's public REST API to retrieve repository metadata, directory listings, and file contents.
    - Do not require users to authenticate for public repositories.
    - Handle GitHub API rate limits gracefully.
    - Display meaningful messages for private repositories, unavailable resources, and API failures.
    - Cache repository metadata and directory listings in memory when practical to reduce unnecessary requests.
    - Do not assume that the default branch is always named `main` or `master`.
    - Handle branch names containing slashes correctly.
    - Support repository paths containing spaces and URL-encoded characters.
    - Use the Git Trees API when useful for more efficient repository navigation, but do not sacrifice the usability of the file browser.

11. **Visual design**
    - Create a polished developer-oriented visual identity.
    - Use a clean, modern interface with strong typographic hierarchy.
    - Include a cohesive color palette suitable for extended reading sessions.
    - Support light and dark themes, with a theme toggle.
    - Remember the user's theme preference locally.
    - Use subtle borders, restrained shadows, and clear visual separation between navigation and content.
    - Make Markdown reading particularly comfortable, with a sensible maximum reading width.
    - Ensure syntax highlighting remains readable in both themes.
    - Avoid excessive animations and decorative elements that compete with the content.
    - Provide small transitions for navigation and panel changes where appropriate.

12. **Performance and reliability**
    - Avoid unnecessary full-page rerenders.
    - Prevent stale asynchronous requests from overwriting the state of a newly selected repository or file.
    - Handle network failures and request timeouts.
    - Avoid loading the entire repository when the user only needs one directory or file.
    - Keep the application responsive while loading and rendering content.
    - Handle binary files gracefully instead of attempting to display them as source code.
    - Provide an appropriate fallback for files that cannot be rendered directly.

13. **Application architecture**
    - Organize the JavaScript into clear functional sections or modules within the single HTML file.
    - Separate repository API access, persistence, navigation state, rendering, and UI interactions logically.
    - Keep dependencies lightweight and use well-established libraries where they materially improve the experience.
    - Use a Markdown parser, HTML sanitizer, and syntax highlighter if appropriate.
    - Include basic comments explaining important implementation decisions.
    - Ensure all required dependencies are loaded through browser-compatible CDN resources or implemented directly.

14. **Accessibility**
    - Use semantic HTML.
    - Provide accessible labels for interactive controls.
    - Support keyboard navigation on desktop.
    - Ensure sufficient color contrast.
    - Include visible focus states.
    - Provide appropriate ARIA attributes for drawers, dialogs, and toggles.
    - Respect reduced-motion preferences.

15. **Sign-off:** The finished application must display a clearly identifiable About, version, or footer section containing the date and time the solution was produced and the model or author responsible for producing it. Use the actual generation date/time and actual model identity rather than placeholders.

## Constraints

- Deliver the entire application as a single standalone `index.html` file.
- The user must not need to install Node.js, Python, npm, a development server, or any other runtime.
- Opening `index.html` in a modern browser should be sufficient to launch the application.
- HTML, CSS, and JavaScript must be contained in the delivered file.
- External libraries are permitted when useful, provided they are loaded through browser-compatible CDN URLs.
- No backend, database server, build pipeline, or authentication service.
- Use browser localStorage or IndexedDB for persistence.
- Use GitHub's public API for repository access.
- No application-specific network service other than GitHub and the necessary CDN-hosted libraries.
- Do not require a GitHub personal access token.
- Clearly communicate that public repositories are supported and private repositories require a different authentication approach.
- Do not embed repository-specific assumptions.
- Ensure that the application can run on current versions of Chrome, Safari, Firefox, and Edge, including mobile Safari and Chrome for Android.
- Avoid APIs that are unavailable in ordinary browser contexts.
- Account for possible browser restrictions involving `file://` origins, especially around localStorage and CDN resource loading. Provide graceful fallbacks and clearly explain any browser limitation without requiring a local server.

## Sample Data / Inputs

The application must accept these example repository inputs:

**Example 1 — Repository root**

`https://github.com/facebook/react`

Expected behavior:
- Load the React repository metadata.
- Show its top-level directories and files.
- Allow the user to navigate into folders.
- Allow the user to open source files and Markdown documentation.

**Example 2 — Repository with a specific starting directory**

`https://github.com/microsoft/vscode/tree/main/src`

Expected behavior:
- Load the VS Code repository.
- Start browsing inside `src`.
- Display the appropriate breadcrumb hierarchy.
- Allow navigation back to the repository root.

**Example 3 — Short repository notation**

`vercel/next.js`

Expected behavior:
- Interpret this as the GitHub repository `https://github.com/vercel/next.js`.
- Resolve its default branch automatically.

**Example 4 — Markdown document**

`https://github.com/owner/repository/blob/main/README.md`

Expected behavior:
- Open the specified Markdown document directly.
- Initially display its rendered version.
- Allow switching to its raw source.

**Example 5 — Repository history**

1. Open `facebook/react`.
2. Open `microsoft/vscode`.
3. Refresh the browser.
4. Return to the repository library.
5. Verify that both repositories remain available and are ordered by their last-visited timestamps.

## Deliverable

- One complete, production-quality `index.html` file.
- All CSS and JavaScript embedded in the HTML file.
- CDN dependencies referenced directly from the document.
- No additional project files or build instructions.
- Exact launch instruction: Open `index.html` in a modern web browser.
- Include a short explanation of supported browsers and any relevant `file://` restrictions.
- Include a brief implementation overview describing the GitHub API integration, Markdown renderer, syntax highlighter, and local persistence strategy.

## Done When

- [ ] The application launches by opening the standalone HTML file.
- [ ] A GitHub repository can be loaded by pasting its URL.
- [ ] Short `owner/repository` notation works.
- [ ] A repository can be explored through nested directories.
- [ ] Breadcrumb navigation works correctly.
- [ ] Source files open with syntax highlighting and line numbers.
- [ ] Code can be copied to the clipboard.
- [ ] Markdown files automatically open in rendered mode.
- [ ] Markdown can be switched between rendered and raw modes.
- [ ] Internal Markdown links navigate within the application where supported.
- [ ] External links open safely.
- [ ] Repository metadata is displayed correctly.
- [ ] Previously visited repositories persist after refresh.
- [ ] Repository history supports reopening and deletion.
- [ ] The application has a usable library/home screen.
- [ ] The mobile interface is comfortable to use on a smartphone.
- [ ] The desktop interface takes advantage of larger screens.
- [ ] The navigation drawer or equivalent works properly on mobile.
- [ ] Light and dark themes both work.
- [ ] Theme preference persists.
- [ ] GitHub API errors and rate limits produce understandable messages.
- [ ] Loading indicators and empty states are present.
- [ ] Binary and unsupported files are handled gracefully.
- [ ] Rapid repository or file switching does not cause stale content to appear.
- [ ] The interface has no unintended horizontal overflow.
- [ ] Keyboard navigation and accessibility basics work.
- [ ] The application includes its required date/time and model/author sign-off.
- [ ] No installation, build, or local server is required.

## Stretch Goals (optional)

1. **Repository search:** Add a searchable file tree or quick-open command that allows users to locate files by name without manually navigating every directory.

2. **Reading bookmarks:** Allow users to bookmark individual files and Markdown documents, persisting bookmarks per repository so they can return to important files quickly.

3. **GitHub-style navigation enhancements:** Display file sizes, last commit information where practical, branch selection, and a repository search shortcut.

4. **Reading customization:** Add adjustable code font size, line wrapping, and a distraction-free reading mode.

5. **Offline reading cache:** Cache recently opened files locally and allow users to reopen previously fetched content without an internet connection, clearly indicating when displayed content may be stale.