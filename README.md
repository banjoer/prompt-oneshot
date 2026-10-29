# prompt-oneshot

A collection of one-shot, self-contained engineering challenge prompts — a mix of
easy, medium, hard, and extreme problems you can copy-paste into any AI assistant
(or hand to a human) to get a complete, runnable solution in a single shot.

Every prompt is:

- **Self-contained** — everything needed is inline: problem, requirements, sample
  data, run commands. No external resources, links, or indexes.
- **Runnable & visual** — solutions render a UI, animate, drive a terminal, or
  produce artifacts you can open and *see working*.
- **Local-only** — storage, when needed, uses plain files or embedded databases
  (SQLite, localStorage). No servers, no network, no APIs.
- **Stack-scoped** — Python, HTML/CSS, JavaScript (browser/Node), or Java;
  stdlib-first, with a usual scaffold allowed only on hard/extreme challenges.

## Generating new prompts

Use [`CHALLENGE_GENERATOR.md`](CHALLENGE_GENERATOR.md): paste it into any LLM
chat, optionally with parameters (`difficulty: hard, stack: python`, or `random`).
Save the generated challenge to `oneshots/<kebab-case-title>.md` and add a row to
the catalogue below.

## Difficulty labels

| Label | Difficulty |
|:-----:|:----------|
| 🟢 | Easy |
| 🟡 | Medium |
| 🟠 | Hard |
| 🔴 | Extreme |

## Catalogue

| Title | Tech | Difficulty | Prompt |
|-------|------|:----------:|--------|
| _No prompts yet — generate one and add it here._ | | | |

<!-- Row template:
| <Title> | <e.g. Python, SQLite> | <🟢/🟡/🟠/🔴> <Easy/Medium/Hard/Extreme> | [prompt](oneshots/<file>.md) |
-->
