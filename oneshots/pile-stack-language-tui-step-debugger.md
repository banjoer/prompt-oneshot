# Pile: A Stack Language & TUI Step Debugger

**Difficulty:** Extreme  |  **Stack:** Python (standard library only)  |  **Estimated time:** 8–14 h

## The Problem

Your team's little Forth-like scripting language, **Pile**, started as a joke
and is now used for real build-time calculations — and people are debugging it
by sprinkling print words into their code. Every serious language eventually
needs two tools: something that *runs* code and something that lets you *watch
it run*. Building both forces you through the real toolchain: a lexer, a
compiler that lowers structured control flow to flat jump-based instructions,
an iterative virtual machine with explicit stacks, and a full-screen terminal
UI that renders live machine state without flicker. Your task is to ship
**pile.py**: a single-file interpreter for Pile with three modes — `run`,
`trace`, and `debug` — where `debug` is a gdb-flavored TUI step debugger with
breakpoints, stepping, and live views of the data stack, variables, call
stack, and source position.

## Requirements

1. **CLI.** One file, `pile.py`, with subcommands:
   `python3 pile.py run <file.pile>`, `python3 pile.py trace <file.pile>`, and
   `python3 pile.py debug <file.pile>`. All three accept `--max-steps N`
   (default `100000`). A missing file or a compile error prints
   `error: <message> at line <n>` to **stderr** and exits `1` *before* anything
   is printed to stdout.
2. **Lexer.** Tokens are whitespace-separated; `#` starts a comment that runs
   to end of line (except inside strings). Integer literals are optional `-`
   directly attached to digits (`-5` is a literal; `- 5` is subtraction then a
   literal). String literals are double-quoted on one line with escapes `\"`,
   `\\`, `\n`, `\t` — any other escape sequence is a compile error. Every
   token/instruction retains its 1-based source line for errors and the
   debugger.
3. **Compiler.** Recursive descent over the grammar below, producing a **flat
   instruction list** (each instruction tagged with its source line), with
   structured control flow lowered to jump instructions whose targets are
   patched after their blocks are compiled. Collect `def` names in a first
   pass so functions may call themselves and functions defined later in the
   file. Compile errors (all with line numbers): unknown word, `store`/`load`
   not followed by a valid name, `break` outside a loop, `return` outside a
   `def`, `i` outside a `times` loop, duplicate `def`, a `def` or variable
   name colliding with a reserved keyword, and a `store`/`load` name
   colliding with a `def` name.
4. **Values & operators.** Values are arbitrary-precision integers or strings.
   Truthiness: integer `0` and the empty string are falsy; everything else is
   truthy. `+` concatenates when both operands are strings, otherwise both
   operands must be ints (anything else → runtime error). `-`, `*`, `/`, `%`
   are int-only; `/` is floor division and `%` is Python-style modulo;
   division or modulo by zero is a runtime error. Comparisons push `1`/`0`;
   `<`, `<=`, `>`, `>=` require two ints (otherwise runtime error); `=` and
   `!=` accept any pair of types, returning `0`/`1` for mixed types. `and`/
   `or` pop two values and push `1`/`0` by truthiness; `not` pops one and
   pushes `1`/`0`.
5. **Stack ops.** `dup` ( a -- a a ), `drop` ( a -- ), `swap` ( a b -- b a ),
   `over` ( a b -- a b a ), `rot` ( a b c -- b c a ). Popping from an empty
   stack anywhere is a runtime error: `stack underflow`.
6. **Variables.** One global namespace. `store name` pops the top of stack
   into variable `name` (creating it); `load name` pushes its current value.
   `load` of a never-stored variable is a runtime error:
   `undefined variable 'name'`. Variables come into existence at first
   `store` (this is also when they appear in the debugger's variables pane).
7. **Conditionals.** `if` pops one value; truthy runs the then-block, falsy
   runs the optional `else` block. Blocks may be empty. No value is produced
   or consumed beyond the popped condition.
8. **While loops.** `while <cond-block> do <body-block> end`: on entry and
   after every body execution the cond-block runs and its top value is
   popped; falsy exits the loop, truthy runs the body again. The cond-block
   must leave at least one value (underflow rules apply).
9. **Times loops.** `times` pops an integer count `n` (non-int → runtime
   error); `n <= 0` skips the body entirely. The body executes `n` times; the
   word `i` pushes the current 0-based iteration index. In nested `times`
   loops, `i` refers to the innermost loop.
10. **Loop & function exits.** `break` exits the innermost enclosing loop
    (`while` or `times`); it is a compile error outside any loop. `return`
    exits the current function early; it is a compile error at top level.
11. **Functions.** `def name ... end` defines; a bare word matching a defined
    name calls it. Arguments and results travel on the shared data stack
    (Forth-style — no parameter lists). Recursion must work, and the VM must
    implement calls with an **explicit call stack**, not Python recursion, so
    a program 5000 calls deep runs without `RecursionError` (see
    `countdown.pile` below). The call stack is exposed to the debugger.
12. **I/O words.** `.` pops and prints the value followed by a newline;
    `echo` pops and prints with no newline; `cr` prints a newline; `emit`
    pops an int in 0–127 and prints the ASCII character (out of range →
    runtime error). Integers print in decimal, strings print raw. In `run`
    and `trace` modes output goes to stdout; in `debug` mode program output
    is captured into the output pane and must never corrupt the TUI.
13. **Steppable VM core.** All three modes drive one shared implementation:
    a VM with an explicit instruction pointer, data stack, variable map, call
    stack, loop-index stack, halted/error flags, and an output callback —
    plus a `step()` method that executes **exactly one** instruction and
    reports status. `run` is a loop over `step()`; `trace` prints then steps;
    `debug` renders then steps on keypress. Do not write three interpreters.
14. **Run mode.** Executes to completion: program output on stdout, exit `0`.
    A runtime error prints `error: <message> at line <n>` to stderr, exit `1`
    (partial program output already printed stays printed). Exceeding
    `--max-steps` prints `error: step limit (<n>) exceeded at line <m>` to
    stderr, exit `1`.
15. **Trace mode.** Before executing each instruction, print exactly
    `TRACE ip=%04d line=%d op=%s stack=%s` where the stack is rendered
    Python-list-style with strings double-quoted (`[1, 2, "hi"]`, top of
    stack rightmost) and shows the state *before* the instruction executes.
    `op` naming is up to you. Program output interleaves naturally on stdout.
    On successful halt, the final line is `HALT steps=<n>`; exit `0`. Error
    and step-limit behavior matches run mode.
16. **Debugger layout.** `debug` opens a full-screen ANSI TUI, **paused
    before the first instruction**, with five regions: (a) a source pane
    (left, ≥ 55% of width) showing line numbers, a gutter, the executing line
    highlighted, and breakpoint markers; (b) a right column with a DATA STACK
    pane (top of stack on the bottom row, visually marked), a VARIABLES pane
    (alphabetical `name = value`), and a CALL STACK pane (innermost frame
    last, depth shown, top level shown as `main`); (c) an output strip with
    the most recent lines of program output; (d) a status bar showing state
    (`PAUSED`/`RUNNING`/`FINISHED`/`ERROR`), `ip`, current line, step count,
    and key hints.
17. **Step & continue.** `s` executes exactly one instruction and re-pauses;
    the highlight follows the executing line, auto-scrolling/re-centering
    when it leaves the visible window. Values changed by the last step are
    visually flashed (new stack top; variables whose values changed). `c`
    continues until: an instruction whose source line holds a breakpoint is
    **about to execute** (pause *before* it), the program halts (`FINISHED`),
    an error occurs (`ERROR` in red on the status bar, with message and
    line), or the `--max-steps` chunk is exhausted (pause with a "step limit"
    notice; pressing `c` again continues). Stepping while `FINISHED`/`ERROR`
    does nothing.
18. **Breakpoints, cursor, restart, help.** While paused, `j`/`k` (and the
    arrow keys) move a visible source cursor; `b` toggles a breakpoint on the
    cursor line (red `●` in the gutter, `*` in monochrome mode). Breakpoints
    may be set on any line but only trigger when an instruction on that line
    is reached. `r` resets the VM to its initial state (steps = 0, empty
    stack, no variables) **while preserving breakpoints**. `h` or `?` shows a
    help overlay listing every key; any keypress dismisses it.
19. **Terminal discipline.** Use the alternate screen, hide the cursor, and
    put the TTY in raw/cbreak mode via `termios`/`tty`; read keys
    non-blockingly with `select`. Compose every frame fully in memory and
    flush it in a **single write** (no flicker or tearing). Handle
    `SIGWINCH`: re-layout from `shutil.get_terminal_size()` within one frame;
    below 60 columns or 16 rows show a centered "terminal too small" notice
    until space returns. `q` and Ctrl-C restore termios attributes, show the
    cursor, leave the alternate screen, and exit `0` — prompt on a clean
    line, no traceback, no escape-sequence garbage.
20. **Color discipline.** All styling goes through a small internal helper.
    When `NO_COLOR` is set or `TERM` is `dumb`/missing, emit **zero** escape
    codes: monochrome rendering, ASCII borders (`-`, `|`, `+`), `>` for the
    executing line and `*` for breakpoints.
21. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it
    (e.g. a header comment in the source, a footer on the page, or an about
    line in the CLI).

## Constraints

- Python 3.8+ **standard library only**. Suggested: `argparse`, `sys`, `os`,
  `termios`, `tty`, `select`, `signal`, `shutil`, `dataclasses`. Explicitly
  forbidden: `curses`, `rich`, `textual`, `blessed`, and any third-party
  package or pip install.
- Deliverables are created from scratch: one source file plus the example
  programs copied verbatim from below. No build step, no config files, no
  network access.
- `run` and `trace` must work with stdout redirected to a pipe or file (no
  ANSI codes in those modes). `debug` requires a TTY.
- Output must be byte-for-byte deterministic so the expected outputs below
  can be diffed.
- Reserved keywords (never valid as function or variable names): `def end if
  else while do times break return store load i`.
- Names match `[A-Za-z_][A-Za-z0-9_]*`.

## Sample Data / Inputs

Grammar (words are case-sensitive; `INT`/`STRING` are literals, `NAME` an
identifier):

```
program   := item*
item      := "def" NAME statement* "end" | statement
statement := INT | STRING | OP | NAME                 # bare NAME = function call
           | "store" NAME | "load" NAME
           | "if" statement* ("else" statement*)? "end"
           | "while" statement* "do" statement* "end"
           | "times" statement* "end"
           | "break" | "return" | "i"
```

Operator words: `+  -  *  /  %  =  !=  <  <=  >  >=  and  or  not  dup  drop
swap  over  rot  .  echo  cr  emit`

The four example programs (save them verbatim under `examples/`):

**`examples/fizzbuzz.pile`**

```
# fizzbuzz.pile — classic FizzBuzz in Pile
1 store n
while load n 30 <= do
  load n 15 % 0 =
  if
    "FizzBuzz" .
  else
    load n 3 % 0 =
    if
      "Fizz" .
    else
      load n 5 % 0 =
      if
        "Buzz" .
      else
        load n .
      end
    end
  end
  load n 1 + store n
end
```

Expected output (all 30 lines, each produced by `.`):

```
1
2
Fizz
4
Buzz
Fizz
7
8
Fizz
Buzz
11
Fizz
13
14
FizzBuzz
16
17
Fizz
19
Buzz
Fizz
22
23
Fizz
Buzz
26
Fizz
28
29
FizzBuzz
```

**`examples/factorial.pile`** — expected output is the single line `6! = 720`

```
# factorial.pile — recursive factorial
def fact
  dup 1 <=
  if
    drop 1
  else
    dup 1 - fact *
  end
end

"6! = " echo
6 fact .
```

**`examples/sumsq.pile`** — expected output is the single line `sumsq(0..9) = 285`

```
# sumsq.pile — sum of i² for i in 0..9, using a times loop
0 store total
10 times
  i dup *
  load total +
  store total
end
"sumsq(0..9) = " echo
load total .
```

**`examples/countdown.pile`** — expected: 5001 lines, first line `5000`,
last line `liftoff!` (proves the explicit call stack: 5001 nested frames
would crash a Python-recursive VM)

```
# countdown.pile — deep recursion; the VM must not use Python recursion
def countdown
  dup 0 <=
  if
    drop "liftoff!" .
  else
    dup .
    1 - countdown
  end
end

5000 countdown
```

Trace-mode shape (`op` names are yours; format, stack rendering, and the
`HALT` line are not). For a file containing exactly `1 2 + .`:

```
TRACE ip=0000 line=1 op=push(1) stack=[]
TRACE ip=0001 line=1 op=push(2) stack=[1]
TRACE ip=0002 line=1 op=add stack=[1, 2]
TRACE ip=0003 line=1 op=print stack=[3]
3
TRACE ip=0004 line=1 op=halt stack=[]
HALT steps=5
```

Error cases your implementation must reproduce (message text up to you, the
`error: ... at line N` shape, stderr routing, and exit code `1` are not):

- `1 2 frobnicate` → compile error `unknown word 'frobnicate' at line 1`
- `1 0 / .` → runtime error `division by zero at line 1`
- `load missing` → runtime error `undefined variable 'missing' at line 1`
- `drop` alone in a file → runtime error `stack underflow at line 1`
- Infinite loop `while 1 do end` run with `--max-steps 1000` → step-limit
  error naming `1000`, exit `1`

## Deliverable

- **`pile.py`** — the complete interpreter + debugger (single file)
- **`examples/fizzbuzz.pile`**, **`examples/factorial.pile`**,
  **`examples/sumsq.pile`**, **`examples/countdown.pile`** — the files above,
  copied verbatim
- Run: `python3 pile.py run examples/fizzbuzz.pile`
- Trace: `python3 pile.py trace examples/factorial.pile`
- Debug: `python3 pile.py debug examples/fizzbuzz.pile`

## Done When

- [ ] `python3 pile.py run examples/fizzbuzz.pile` prints exactly the 30-line
      expected output above (`diff` clean against it), exit `0`.
- [ ] `run examples/factorial.pile` prints `6! = 720` and
      `run examples/sumsq.pile` prints `sumsq(0..9) = 285`.
- [ ] `run examples/countdown.pile | tail -1` prints `liftoff!`,
      `... | wc -l` reports `5001`, and no `RecursionError` occurs.
- [ ] Tracing a file containing `1 2 + .` produces output matching the trace
      shape above (five `TRACE` lines in the documented format, the `3`, and
      `HALT steps=5` last), exit `0`.
- [ ] Each error case in Sample Data prints its `error: ... at line N`
      message to **stderr**, nothing to stdout, and exits `1` — including the
      `--max-steps 1000` infinite-loop case.
- [ ] `python3 pile.py debug examples/fizzbuzz.pile` opens the full-screen
      TUI paused before the first instruction: source with line numbers,
      empty data-stack pane, empty variables pane, call stack showing `main`,
      empty output strip, and a status bar with `PAUSED`, `ip`, line, steps,
      and key hints.
- [ ] Pressing `s` executes exactly one instruction each time: the line
      highlight moves through the source (scrolling when needed) and the
      stack/variables panes update; the variable that just changed is
      visually highlighted.
- [ ] Moving the cursor to line 6 (`    "FizzBuzz" .`) and pressing `b`
      plants a breakpoint marker; pressing `c` pauses there *before* the line
      executes, with the variables pane showing `n = 15`; pressing `c` again
      pauses there with `n = 30`; a third `c` ends in `FINISHED` with all 30
      output lines in the output strip.
- [ ] In `debug examples/factorial.pile`, breakpointing line 3
      (`  dup 1 <=`) and continuing repeatedly shows the CALL STACK pane
      growing to depth 7 (`main` plus six `fact` frames).
- [ ] Pressing `r` mid-session resets steps to 0, empties the stack and
      variables, keeps breakpoints, and returns to the paused-at-start state.
- [ ] Resizing the terminal re-lays out all panes within a frame; shrinking
      below 60×16 shows the "terminal too small" notice and growing back
      restores the UI without artifacts.
- [ ] With `NO_COLOR=1` (or `TERM=dumb`) the TUI renders monochrome ASCII and
      emits no escape codes.
- [ ] `q` and Ctrl-C each restore the terminal perfectly (cursor visible,
      prompt on a clean line, exit `0`, no traceback).
- [ ] `grep -E "import (curses|rich|textual|blessed)" pile.py` finds nothing,
      and `run`/`trace` output contains no ANSI escape codes when piped.

## Stretch Goals (optional)

- **Step out:** `f` runs until the call-stack depth drops below its current
  value (i.e. the current function returns), then pauses.
- **Watch expressions:** `w` opens an inline prompt accepting any Pile
  snippet (e.g. `load n 2 *`); after every step/continue the snippet is
  evaluated on a scratch copy of the VM state and its result shown in a watch
  pane.
- **Conditional breakpoints:** `B` plants a breakpoint with an attached Pile
  expression; `c` pauses at that line only when the expression evaluates
  truthy at that moment.
