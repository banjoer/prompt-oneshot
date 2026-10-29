# RegexZero: A From-Scratch NFA Regex Engine and Grep CLI

**Difficulty:** Extreme  |  **Stack:** Node.js ≥ 18 (standard library only)  |  **Estimated time:** 8–12 h

## The Problem

Every developer greps daily, yet almost nobody can explain what happens between
the pattern and the matches — and most assume regex is "just backtracking".
That assumption is dangerous: naive backtracking engines exhibit exponential
blowups (ReDoS), which famously took down large chunks of the internet in a
2019 Cloudflare outage caused by one catastrophic WAF regex. The classic fix
is Thompson's 1968 construction: compile the pattern into a nondeterministic
finite automaton and simulate it, guaranteeing time linear in the input length
with no exponential cases. Your task is to build **RegexZero**: a hand-written
parser for a real regex subset, compiled to an ε-NFA via Thompson
construction, executed by a priority-ordered Pike VM whose match spans agree
with JavaScript's own `RegExp`, wrapped in a genuinely grep-compatible CLI
with match highlighting — plus an ASCII renderer that draws the compiled
automaton for debugging and teaching.

## Requirements

1. **Recursive-descent parser.** Parse the following subset into an explicit
   AST (node kinds: `Char`, `Any`, `Class`, `Anchor`, `Concat`, `Alt`,
   `Repeat{star,plus,quest}`, `Group`):
   - Literal characters.
   - Escapes: `\. \* \+ \? \| \( \) \[ \] \\ \n \t \r` and the shorthand
     classes `\d \D \w \W \s \S` (`\d` = `[0-9]`, `\w` = `[A-Za-z0-9_]`,
     `\s` = `[\t\n\v\f\r ]`, uppercase = complement).
   - `.` — any character except `\n`.
   - Character classes `[...]`: ranges (`a-z`), negation (`[^...]`), escapes
     inside (`\]`, `\\`, `\n`, …); a `-` is literal only at the start, at the
     end, or when escaped. An unescaped `]` always closes the class; a literal
     `]` must be escaped.
   - Quantifiers `*`, `+`, `?` (greedy) applying to the preceding atom.
   - Groups `(...)` — grouping/precedence only; no capture semantics needed.
   - Alternation `|` (n-ary, left-associative).
   - Anchors `^` and `$` as zero-width assertions valid anywhere in the
     pattern (start/end of the current line; no multiline mode).
   - Precedence (tightest first): quantified atom > concatenation >
     alternation. The empty pattern is legal (matches the empty string
     everywhere); empty alternation branches are legal (`a|` matches `a` or
     the empty string), matching JS `RegExp` behavior.
2. **Clean syntax errors.** Reject with a single-line stderr message
   `regexzero: invalid pattern: <reason>` and exit code 2 (no stack trace) on:
   a quantifier with no quantifiable atom (`*abc`, `a**`, `a*?`, `^*`),
   unclosed `(` or `[`, a trailing `\`, a descending range (`[z-a]`), an empty
   class (`[]` / `[^]`), or an unsupported escape (`\1`, `\b`, `\x41`, …).
3. **Thompson construction with deterministic state numbering.** Compile the
   AST to an ε-NFA where every fragment has one start and one accept state.
   `compile(node)` returns `{start, accept}`; allocate integer state ids
   depth-first, children before parents, left to right, exactly as follows:
   - Atom (`Char`/`Any`/`Class`/`Anchor`): two fresh states `s, a` and one
     edge `s → a` labeled with the atom (anchors are zero-width edges labeled
     `^` / `$`).
   - `Concat`: no new states; add `eps` edge `accept_i → start_{i+1}`.
   - `Alt` (n branches): compile branches left→right; fresh `S, A`; `eps`
     `S →` each branch start (in branch order) and each branch `accept → A`.
   - `Repeat*`: compile child; fresh `S, A`; `eps` edges `S → child.start`,
     `S → A`, `child.accept → child.start`, `child.accept → A`.
   - `Repeat+`: compile child; fresh `S, A`; `eps` edges `S → child.start`,
     `child.accept → child.start`, `child.accept → A`.
   - `Repeat?`: compile child; fresh `S, A`; `eps` edges `S → child.start`,
     `S → A`, `child.accept → A`.
   State count must be linear in pattern size (≤ 2 per atom/operator); the
   same pattern must always produce the same graph.
4. **Greedy priority wiring.** ε-successor order encodes greediness: for
   `*`/`+`/`?`, "enter/iterate the child" is always listed before "exit"; for
   alternation, earlier branches are listed first. This priority order is what
   makes the VM's spans agree with Perl/JavaScript (leftmost-first), not POSIX
   leftmost-longest: `a|ab` on `ab` must match `a` (span `[0,1)`), never `ab`.
5. **Priority-ordered Pike VM simulation.** Match by breadth-first simulation
   of the NFA, not backtracking: maintain the live thread list in priority
   order; compute ε-closures with a priority-preserving DFS that checks assert
   states against the current position (`^`: pos 0; `$`: pos == line length)
   and dedupes states per step. When a thread reaches ACCEPT during closure,
   record the current position as the match end and **cut** (discard) all
   lower-priority threads; surviving higher-priority threads keep stepping and
   may extend the recorded end. Nested quantifiers over empty-matchable bodies
   (`(a*)*`, `(a?)*b`) must terminate instantly — the closure visited-set
   prevents ε-loops. No recursion over the input and no backtracking:
   worst case O(states × line length) per match scan.
6. **Leftmost-first scanning with JS parity.** Per input line, find matches by
   the standard left-to-right scan: the earliest start position wins; the
   engine's priority order picks the span; after a match of `[s, e)`, resume
   scanning at `e`, or at `e + 1` if the match is empty (`s == e`).
   **Oracle parity:** for every pattern in the supported subset and every
   line of printable ASCII, the produced match spans must equal
   `[...line.matchAll(new RegExp(pattern, 'g'))].map(m => [m.index,
   m.index + m[0].length])`. `RegExp` is your specification — but may only be
   used inside `test.js` (see Constraints).
7. **CLI.** Entry point `grep.js`:
   `node grep.js [OPTIONS] PATTERN [FILE...]`
   - Input: each `FILE` in order; with no `FILE`, or for the filename `-`,
     read stdin. With two or more file arguments, prefix every output line
     with `FILENAME:` (count and match modes included).
   - Options: `-n` (prefix 1-based line number, `FILE:LINE:` with files),
     `-o` (print each match on its own line instead of the whole line; empty
     matches print as empty lines), `-c` (print only the count of selected
     lines per input), `-v` (invert: select non-matching lines; `-o` is
     ignored under `-v`, whole unhighlighted lines are printed), `-i`
     (ASCII case-insensitive matching), `--color=auto|always|never` and
     `--no-color` (alias for `never`), `--` (end of options, so patterns
     starting with `-` work), `-h`/`--help`, `--version`, `--nfa`.
8. **Exit codes (grep semantics).** `0` if at least one line was selected,
   `1` if none, `2` on any error. A bad pattern, bad option, or `--nfa` with
   extra arguments aborts immediately with a stderr message. A missing,
   unreadable, or directory file prints `regexzero: <file>: <reason>` to
   stderr but does **not** stop processing of the remaining files; the final
   exit code is then `2` even if matches were found.
9. **Highlighting and color policy.** In the default (whole-line) mode, print
   each selected line with **every** non-empty match span wrapped in bold red
   (`\x1b[1;31m` … `\x1b[0m`); zero-width matches select the line but highlight
   nothing. Filename and line-number prefixes are never colored. Color is
   emitted only when `--color=always`, or when mode is `auto` **and**
   `process.stdout.isTTY` **and** `TERM` is set and not `dumb` **and**
   `NO_COLOR` is not set. `-o` output is colored by the same rules.
10. **`--nfa` mode.** `node grep.js --nfa PATTERN` compiles the pattern and
    prints the automaton — reading no input — in two sections, then exits 0
    (exit 2 on an invalid pattern):
    - **Transition table** — states in ascending id order, one line each, with
      outgoing edges in priority order: `state N: 'a' -> M` for literals
      (`'\''`, `'\\'`, `'\n'` escaped), `state N: . -> M` for `Any`,
      `state N: [a-c] -> M` for classes (class text verbatim from the
      pattern), `state N: eps -> M1, M2` for ε edges, `state N: ^ -> M` /
      `state N: $ -> M` for assert edges, and `state N: ACCEPT` for the
      accept state. Because of the numbering convention in requirement 3, the
      table for `ab*c` must be exactly the 8-line reference shown in
      Sample Data.
    - **Diagram** — an ASCII-art rendering of the same graph: horizontal main
      spine with labeled edges (`─a─▶`, `─ε─▶`, `─^─▶`, `─$─▶`), loop and
      bypass edges routed above/below the spine with box-drawing characters,
      the start state single-circled `(0)` and the accept state
      double-circled `((N))`. Cosmetic layout is up to you, but every edge in
      the table must be identifiable in the diagram, and output must be
      byte-identical across runs for a given pattern.
11. **Streaming I/O.** Read input line by line (e.g. `node:readline` over
    `fs.createReadStream` / fd 0) — never `readFileSync` or equivalent
    whole-file buffering of input data. Split lines strictly on `\n` (a
    trailing `\r` is an ordinary character); handle a final line without a
    trailing newline, empty lines, and individual lines of at least 1 MB
    without crashing or stack overflow (recursion proportional to *pattern*
    nesting is fine; recursion proportional to *input* is not).
12. **Performance gates.**
    - No catastrophic backtracking: a 60-character line of `a`s against
      `(a*)*b` (no match) must finish in under 1 second with exit code 1.
    - Throughput: searching the 5 MB generated file from Sample Data with
      `ERROR .*latency=[0-9]+` must complete in under 3 seconds on a typical
      laptop and print the correct count.
    - `--nfa` on a 100-atom pattern must render without perceptible delay
      (linear-time construction).
13. **Self-test suite (`test.js`).** Runs with `node test.js`, prints a
    pass/fail summary, exits 0 on success and 1 on any failure:
    - A fixed corpus of **at least 25** `(pattern, input, expected matches)`
      cases covering every feature — start from the table in Sample Data and
      extend it (class escapes, `\D`/`\W`/`\S`, nested groups, n-ary
      alternation `a|b|c`, quantified groups, anchors mid-pattern, …).
    - A **seeded differential fuzzer**: implement a small deterministic PRNG
      inline (e.g. mulberry32 with a fixed seed), generate ≥ 500 random
      *valid-subset* patterns (bounded depth, alphabet `{a, b, c}`, all
      operators, never quantifying an anchor or a quantifier) × ≥ 3 random
      inputs each, and assert span equality against the `RegExp` oracle.
    - CLI checks via `node:child_process`: exit codes 0/1/2, stderr shape on
      bad patterns, and that two `--nfa` runs on the same pattern are
      byte-identical.
    - The `RegExp` oracle is allowed in this file only.
14. **Modularity.** Exactly six files in one flat directory: `grep.js`
    (CLI/arg parsing/IO), `parser.js` (tokenizer + AST), `nfa.js` (Thompson
    construction), `vm.js` (simulation + scanning), `render.js` (table +
    diagram), `test.js` (suite). CommonJS or ESM, your choice.
15. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it —
    specifically: `node grep.js --version` must print the tool name together
    with the build date/time and author/model, and every source file must
    carry a header comment with the same information.

## Constraints

- Node.js ≥ 18, **standard library only** — suggested: `node:fs`,
  `node:process`, `node:readline`, `node:assert`, `node:child_process` (tests
  only). No npm install, no `package.json`, no build step, no network access.
- **Forbidden in `grep.js`, `parser.js`, `nfa.js`, `vm.js`, `render.js`:**
  `RegExp`, regex literals, and `String.prototype.match` / `matchAll` /
  `search` / `replace` / `split` with a regex argument — i.e. no use of
  JavaScript's built-in regex machinery anywhere in the engine or CLI. These
  are allowed **only** inside `test.js`, where `RegExp` serves as the
  differential oracle.
- Match on strings as JavaScript UTF-16 code units (same as `RegExp`); input
  is decoded as UTF-8; parity is scoped to printable-ASCII lines as stated in
  requirement 6.
- Everything must run from the six files alone in a bare directory:
  `node grep.js …` and `node test.js` just work.
- Output byte-determinism where specified (`--nfa` table and diagram, corpus
  expectations).

## Sample Data / Inputs

Save this as `sample.log` (16 lines) in the working directory:

```
2026-10-29T08:14:02Z INFO  [auth] user=alice id=1042 login ok from 10.0.0.8
2026-10-29T08:14:07Z INFO  [auth] user=bob id=1043 login ok from 10.0.0.9
2026-10-29T08:15:31Z WARN  [cache] key=session:1042 evicted
2026-10-29T08:16:02Z ERROR [db] query timeout after 3001ms err=ETIMEDOUT
2026-10-29T08:16:02Z INFO  [db] retrying connection 1/5
2026-10-29T08:16:05Z ERROR [db] connection refused err=ECONNREFUSED host=10.0.0.20
2026-10-29T08:16:09Z INFO  [db] connection restored
2026-10-29T08:17:44Z WARN  [api] latency p95=812ms route=/v1/users
2026-10-29T08:18:10Z ERROR [api] unhandled exception err=E103 route=/v1/orders
2026-10-29T08:18:10Z INFO  [api] worker 7 restarting
2026-10-29T08:19:56Z INFO  [auth] user=alice id=1042 logout
2026-10-29T08:20:03Z DEBUG [cache] warmup complete keys=13841
2026-10-29T08:20:11Z WARN  [api] latency p95=955ms route=/v1/orders
2026-10-29T08:21:47Z ERROR [db] disk space low err=ENOSPC host=10.0.0.20
2026-10-29T08:22:00Z INFO  [system] backup started job=nightly
2026-10-29T08:22:31Z INFO  [system] backup finished job=nightly duration=31s
```

Expected behavior (shown uncolored, as when piped):

```
$ node grep.js -no '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' sample.log
1:10.0.0.8
2:10.0.0.9
6:10.0.0.20
14:10.0.0.20

$ node grep.js -c 'err=[A-Z0-9]+' sample.log
4

$ node grep.js -v 'INFO' sample.log | wc -l
7

$ printf 'alpha\nbeta\ngamma\n' | node grep.js 'ta$'
beta

$ node grep.js 'zzz' sample.log; echo "exit=$?"
exit=1

$ node grep.js '(' sample.log; echo "exit=$?"
regexzero: invalid pattern: unclosed group
exit=2
```

Reference `--nfa` output for `ab*c` — your **transition table must match this
exactly** (per the numbering convention in requirement 3); the diagram is a
style example (yours must show the same 9 edges):

```
$ node grep.js --nfa 'ab*c'
state 0: 'a' -> 1
state 1: eps -> 4
state 2: 'b' -> 3
state 3: eps -> 2, 5
state 4: eps -> 2, 5
state 5: eps -> 6
state 6: 'c' -> 7
state 7: ACCEPT

                     ┌──ε───┐
                     ▼      │
(0)─a─▶(1)─ε─▶(4)─ε─▶(2)─b─▶(3)─ε─▶(5)─ε─▶(6)─c─▶((7))
              │                    ▲
              └──────────ε─────────┘
```

Starter corpus for `test.js` (spans are `[start, end)`; extend to ≥ 25 cases):

| Pattern        | Input          | Expected matches                                |
|----------------|----------------|-------------------------------------------------|
| `abc`          | `xxabcxx`      | `abc`@[2,5)                                     |
| `a+`           | `caaab`        | `aaa`@[1,4)                                     |
| `a\|ab`        | `ab`           | `a`@[0,1) — leftmost-first, not longest         |
| `ab\|a`        | `ab`           | `ab`@[0,2)                                      |
| `(ab\|a)b`     | `ab`           | `ab`@[0,2) — via the second alternative         |
| `a*`           | `baa`          | ``@[0,0), `aa`@[1,3), ``@[3,3)                  |
| `x*z`          | `zxxz`         | `z`@[0,1), `xxz`@[1,4)                          |
| `ab?`          | `ab a`         | `ab`@[0,2), `a`@[3,4)                           |
| `(ab)+`        | `ababab xab`   | `ababab`@[0,6), `ab`@[8,10)                     |
| `a(b\|c)*d`    | `xxabcdad`     | `abcd`@[2,6), `ad`@[6,8)                        |
| `^a+`          | `aa bb aa`     | `aa`@[0,2) only                                 |
| `a$\|b`        | `ab`           | `b`@[1,2)                                       |
| `^$`           | `` (empty)     | ``@[0,0); on `x`: no match                      |
| `` (empty)     | `hi`           | ``@[0,0), ``@[1,1), ``@[2,2)                    |
| `[a-c]+`       | `abcxyz`       | `abc`@[0,3)                                     |
| `[^a-c]+`      | `abcxyz`       | `xyz`@[3,6)                                     |
| `a.c`          | `a.c axc`      | `a.c`@[0,3), `axc`@[4,7)                        |
| `a\.c`         | `a.c axc`      | `a.c`@[0,3) only                                |
| `\d+`          | `abc123def45`  | `123`@[3,6), `45`@[9,11)                        |
| `\w+`          | `foo_bar baz`  | `foo_bar`@[0,7), `baz`@[8,11)                   |
| `colou?r`      | `color colour` | `color`@[0,5), `colour`@[6,12)                  |
| `(a*)*b`       | `aaab` / `aaaa`| `aaab`@[0,4) / no match — and it must be fast   |

Performance fixtures:

```
# Catastrophic case for backtrackers — must return exit=1 in under 1 s:
printf 'a%.0s' {1..60} | node grep.js '(a*)*b'; echo "exit=$?"

# 5 MB throughput fixture (60 000 lines ≈ 5.1 MB):
node -e "const w=[];for(let i=0;i<60000;i++)w.push('2026-10-29T08:'+String(i%60).padStart(2,'0')+':00Z '+(i%97?'INFO':'ERROR')+' [api] route=/v1/'+(i%7)+' latency='+(i%1000)+'ms');require('fs').writeFileSync('big.log',w.join('\n'))"
time node grep.js -c 'ERROR .*latency=[0-9]+' big.log   # must print 619 in < 3 s
```

## Deliverable

- Exactly six files in one directory: **`grep.js`**, **`parser.js`**,
  **`nfa.js`**, **`vm.js`**, **`render.js`**, **`test.js`**.
- Run the CLI: `node grep.js [OPTIONS] PATTERN [FILE...]`
- Render the automaton: `node grep.js --nfa 'PATTERN'`
- Run the tests: `node test.js`
- Requires Node.js ≥ 18; nothing to install.

## Done When

- [ ] Every sample command above reproduces the shown output (uncolored when
      piped), including the exact 8-line `--nfa 'ab*c'` transition table and
      the `-c` counts of `4` and `619`.
- [ ] `node test.js` passes ≥ 25 corpus cases plus ≥ 500 seeded differential
      fuzz cases against the `RegExp` oracle, prints a summary, and exits 0.
- [ ] `grep -nE "RegExp|\.match(All)?\(|\.search\(|\.replace\(" grep.js
      parser.js nfa.js vm.js render.js` finds nothing.
- [ ] `printf 'a%.0s' {1..60} | node grep.js '(a*)*b'` exits 1 in under a
      second; the 5 MB `big.log` count runs in under 3 seconds.
- [ ] Piped output contains zero ANSI escapes; `--color=always` wraps every
      match in `1;31` red; `NO_COLOR=1` and `--no-color` each suppress color.
- [ ] Exit codes: match → 0, no match → 1, bad pattern / bad option /
      unreadable file → 2 with a one-line stderr message and no stack trace;
      a missing file does not stop later files from being searched.
- [ ] Multiple files produce `FILE:` prefixes; `-n` produces `FILE:LINE:`;
      stdin works with no FILE and with `-`.
- [ ] `--nfa 'a(b|c)*d'` shows a loop edge routed off the spine, both branch
      labels `b` and `c`, and two consecutive runs are byte-identical.
- [ ] A file with a final unterminated line, empty lines, and a 1 MB line is
      processed correctly; input is streamed (no `readFileSync` on input).
- [ ] Invalid patterns `(`, `a**`, `a*?`, `^*`, `[z-a]`, `[]`, `a\`, `\b`
      each exit 2 with `regexzero: invalid pattern: …` on stderr.
- [ ] `node grep.js --version` prints the tool name, build date/time, and
      author/model, and all six source files carry the same sign-off header.

## Stretch Goals (optional)

- **Lazy quantifiers** `*?`, `+?`, `??` — purely a priority flip in the
  ε-wiring; extend the parser, VM, corpus, and fuzzer accordingly.
- **Capture-group extraction:** add save/restore slots to the Pike VM threads
  (the classic Pike extension) and a `--group=N` flag that prints only capture
  group `N` of each match; show capture boundaries in `--nfa` output.
- **`--dot` mode:** emit the NFA as Graphviz DOT so
  `node grep.js --dot 'a(b|c)*d' | dot -Tpng > nfa.png` draws the graph
  (Graphviz itself is only needed to view the result, not to generate it).
