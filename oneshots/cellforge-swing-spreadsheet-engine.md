# CellForge: A Swing Spreadsheet Engine

**Difficulty:** Extreme  |  **Stack:** Java (Swing, JDK only)  |  **Estimated time:** 8–12 h

## The Problem

Every spreadsheet you have ever used — Excel, Google Sheets, LibreOffice
Calc — is built on the same deceptively small engine core: a formula
parser, a dependency graph, and a recalculation scheduler. Building one
yourself forces you to solve real problems that toy exercises only hint
at: writing a correct recursive-descent parser with proper precedence,
maintaining a dependency graph that must recompute in topological order
(and degrade gracefully when it contains a cycle), propagating
invalidation so a single keystroke ripples through a long chain of
dependent cells in milliseconds, and keeping a Swing UI responsive while
all of it happens. Your task is to build **CellForge**: a working
spreadsheet desktop app — editable grid, formula cells, five aggregate
functions, live dependency-driven recalculation, visible cycle errors,
and save/load to a plain-text format — using nothing but the JDK.

## Requirements

1. **Editable grid UI.** A Swing window showing a 100-row × 26-column
   (A–Z) grid with proper row and column headers (a `JTable` with custom
   model/renderers/editor, or hand-rolled components — your choice).
   Cells are editable in place via double-click, F2, or simply typing
   over a selection; Enter/Tab/arrow keys move the selection. The window
   title shows the current file name (or `Untitled`) plus a `*` when
   there are unsaved changes.
2. **Formula bar and status bar.** A text field above the grid always
   shows the *raw* content of the selected cell and commits on Enter. A
   status bar below the grid shows the selected cell's reference and the
   duration of the last recalculation in milliseconds.
3. **Cell model.** Each cell stores raw text. Leading `=` → formula.
   Empty → blank. Anything else → literal: if it parses as a decimal
   number it is numeric, otherwise it is a text string. Storage is
   sparse: only non-empty cells consume memory.
4. **Hand-written recursive-descent parser.** Formulas are parsed by a
   parser you write yourself into an AST, then evaluated from the AST.
   Grammar:

   ```
   formula  := expr
   expr     := term (('+' | '-') term)*
   term     := factor (('*' | '/' | '%') factor)*
   factor   := unary ('^' factor)?            // '^' right-associative
   unary    := '-' unary | '+' unary | primary
   primary  := NUMBER | CELLREF | FUNCCALL | '(' expr ')'
   FUNCCALL := NAME '(' arg (',' arg)* ')'    // NAME = letters only
   arg      := expr | RANGE                   // RANGE = CELLREF ':' CELLREF
   ```

   Numbers are decimals with optional fraction. Cell refs are 1–2
   letters + 1–3 digits, case-insensitive (`b7` = `B7`); a syntactically
   valid ref that falls outside the 100×26 grid (e.g. `AA12`, `A0`,
   `A101`) evaluates to `#REF!`. Ranges are only valid as function
   arguments; a range anywhere else is a parse error. `^` is
   exponentiation (`Math.pow`), so `=2^3^2` = 512, not 64.
5. **Functions.** `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`
   (case-insensitive), each taking ≥ 1 argument in any mix of numbers,
   refs, and ranges. Over ranges, empty cells and text cells are
   skipped; `COUNT` counts numeric cells only; `AVG` over zero numeric
   cells → `#DIV/0!`; `MIN`/`MAX` over zero numeric cells → `0`. A
   *direct* ref to a text cell used as a function argument or arithmetic
   operand evaluates to `#VALUE!`.
6. **Error taxonomy and propagation.** Exactly these error values:
   `#ERROR` (parse failure, wrong arity, range outside a function),
   `#NAME?` (unknown function name), `#REF!` (out-of-grid ref or range),
   `#VALUE!` (text used as a number), `#DIV/0!` (division or modulo by
   zero), and `#CYCLE!` (see below). Errors are sticky: any operand that
   is an error makes the whole formula yield that error. Error cells
   render in bold red in the grid.
7. **Dependency graph + topological recalculation.** The engine
   maintains a directed graph of cell dependencies extracted from each
   formula's refs and expanded ranges. Committing an edit must re-parse
   that cell, update its edges, and then re-evaluate **only the dirty
   subgraph in topological order** — never blindly re-parse the whole
   sheet. Editing `A1` in the 100-cell chain (see Sample Data) must
   visibly update all 100 cells within one second, and the status bar's
   recalc-time readout proves it.
8. **Cycle detection without hangs.** The evaluator must detect cycles
   (e.g. `A1` = `=B1+1`, `B1` = `=A1+1`) via DFS coloring or an
   equivalent algorithm. Every cell *on* a cycle displays `#CYCLE!`;
   cells that merely *depend* on a cycle also display `#CYCLE!`
   (propagated). The UI must never freeze or overflow the stack, and
   breaking the cycle by editing any member cell must restore correct
   values everywhere within one recalculation.
9. **Precedent highlighting.** When the selected cell contains a
   formula, the backgrounds of its direct precedents (refs and full
   range rectangles) are tinted a light color; the highlight updates as
   the selection moves and disappears for non-formula cells.
10. **Save / load.** `Ctrl+S` saves, `Ctrl+O` opens (via
    `JFileChooser`). Plain-text format: a magic header line, then one
    non-empty cell per line as `<REF><TAB><RAW-CONTENT>`:

    ```
    CELLFORGE1
    A1	Item
    D6	=SUM(D2:D4)
    ```

    A literal tab inside content is written as `\t` and a literal
    backslash as `\\`. Blank lines and lines starting with `#` are
    ignored on load. Loading replaces the sheet, recalculates
    everything, and shows the loaded values.
11. **Menus.** A menu bar with File (New, Open…, Save, Save As…, Exit)
    and Help (About). Choosing Exit with unsaved changes asks for
    confirmation.
12. **Headless mode.** Running with `--headless <file>` loads and
    evaluates the file **without creating any window**, prints the used
    bounding box as tab-separated *display values* (empty cells print as
    empty strings, errors as their codes) to stdout, then exits 0. This
    mode must reuse the exact same engine code as the UI: the engine
    lives in its own package and must not import `javax.swing` or
    `java.awt`.
13. **Number formatting.** Display values: whole numbers with |v| < 1e15
    print as integers (`36`, not `36.0`); other numbers print rounded to
    4 decimal places with trailing zeros stripped (`40.156666…` →
    `40.1567`). Text prints as-is. Headless output uses the identical
    formatting as the grid.
14. **Sign-off:** the finished solution must display, somewhere easy to
    spot, the date and time it was produced and the model/author that
    produced it (e.g. a header comment in the source, a footer on the
    page, or an about line in the CLI).

## Constraints

- **JDK 17+ standard library only** — `javac`/`java`, Swing for the UI.
  No Maven/Gradle, no external jars, no network access.
- The formula engine must be your own code. Explicitly forbidden:
  `javax.script.ScriptEngine` or any other `eval`-style shortcut, and
  regex-based expression evaluation. (Using regex only to *tokenize* is
  fine; parsing must be recursive descent.)
- Suggested layout (multi-file, from scratch):
  - `cellforge/engine/` — cells, sheet, tokenizer, parser, AST,
    evaluator, dependency graph (names may vary; **no Swing/AWT imports
    allowed in this package**)
  - `cellforge/ui/` — grid, formula bar, status bar, dialogs
  - `cellforge/Main.java` — entry point; handles the optional
    `--headless <file>` argument
- Fixed grid: 100 rows × 26 columns.
- Recalculation must be incremental (dirty-subgraph, topological order),
  and the UI must never block on edits.
- All state lives in memory; persistence is only via the text format
  above. No databases, no config files.

## Sample Data / Inputs

Save this as `budget.cfr` — it exercises literals, formulas, all five
functions, division, and multi-level dependencies:

```
CELLFORGE1
A1	Item
B1	Unit Price
C1	Qty
D1	Line Total
A2	Widget
B2	19.99
C2	3
D2	=B2*C2
A3	Gadget
B3	4.5
C3	8
D3	=B3*C3
A4	Gizmo
B4	12.25
C4	2
D4	=B4*C4
A6	Grand Total
D6	=SUM(D2:D4)
A7	Average Line
D7	=AVG(D2:D4)
A8	Cheapest
D8	=MIN(D2:D4)
A9	Priciest
D9	=MAX(D2:D4)
A10	Line Count
D10	=COUNT(D2:D4)
A11	Tax %
B11	8.25
A12	Tax Due
D12	=D6*B11/100
A13	With Tax
D13	=D6+D12
A14	Split 4 ways
D14	=D13/4
```

Key expected values after load: `D2=59.97`, `D3=36`, `D6=120.47`,
`D7=40.1567`, `D8=24.5`, `D9=59.97`, `D10=3`, `D12=9.9388`,
`D13=130.4088`, `D14=32.6022`.

Generate a 100-cell dependency chain for the incremental-recalc test
(test fixture only — not part of the solution):

```
python3 -c 'print("CELLFORGE1"); print("A1\t1"); [print(f"A{i}\t=A{i-1}*2") for i in range(2,101)]' > chain.cfr
```

With `A1=1`, cell `A100` must equal `2^99`, displayed as
`633825300114114700748351602688`.

Cycle test (build by hand in the UI): set `A1` to `=B1+1`, `B1` to
`=A1+1`, `C1` to `=A1*2`. All three must show `#CYCLE!` in red, with the
app fully responsive. Then set `B1` to `5`: `A1` must become `6` and
`C1` must become `12`.

## Deliverable

- A folder of `.java` sources (engine package + ui package + `Main`),
  created from scratch — no build files required.
- Compile (one command): `javac -d out $(find . -name '*.java')`
- Run the GUI: `java -cp out cellforge.Main` (optionally with a file:
  `java -cp out cellforge.Main budget.cfr`)
- Run headless: `java -cp out cellforge.Main --headless budget.cfr`

## Done When

- [ ] `javac` compiles everything with no errors, and
      `grep -rh '^import' cellforge/engine | grep -v 'java\.'` prints
      nothing (engine imports only JDK `java.*` packages — no Swing/AWT,
      nothing external).
- [ ] The GUI opens a 100×26 grid; typing `12`, `hello`, `=1+2*3^2`, and
      `=-(4+5)` into cells displays `12`, `hello`, `19`, and `-9`, while
      the formula bar shows the raw text of the selected cell.
- [ ] Loading `budget.cfr` shows every key value listed in Sample Data
      exactly, and `java -cp out cellforge.Main --headless budget.cfr`
      prints the same values as a TSV block with no window appearing.
- [ ] Selecting `D13` highlights `D6` and `D12`; selecting `D2`
      highlights `B2` and `C2`.
- [ ] Loading `chain.cfr`, then editing `A1` from `1` to `2`, updates
      all 100 cells in one recalculation (`A100` becomes
      `1267650600228229401496703205376`); the status bar reports the
      recalc duration.
- [ ] The cycle test shows three red `#CYCLE!` cells without freezing,
      and setting `B1` to `5` yields `A1=6`, `C1=12`.
- [ ] `=1/0` → `#DIV/0!`, `=NOPE(1)` → `#NAME?`, `=A101+1` → `#REF!`,
      `=A1*2` with text in `A1` → `#VALUE!`, and `=SUM(A1:A3)` over
      blanks/text → `0` — all rendered in bold red except the `0`.
- [ ] `Ctrl+S` writes a valid `CELLFORGE1` file; restarting the app and
      `Ctrl+O`-ing it restores every raw cell exactly; the title-bar `*`
      dirty flag appears on edit and clears on save.
- [ ] Exiting with unsaved changes prompts for confirmation; Help →
      About shows the sign-off line (date, time, model/author).

## Stretch Goals (optional)

- Undo/redo (`Ctrl+Z` / `Ctrl+Y`) implemented as a command stack over
  cell edits, coalescing consecutive edits of the same cell.
- Absolute refs (`$A$1`) plus copy/paste of a formula cell with
  Excel-style relative-ref offsetting.
- File → Export CSV… writing the computed display values of the used
  bounding box to a `.csv` file.
