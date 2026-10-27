<h1 align="center">agent-ready</h1>

<p align="center"><b>Is your codebase ready for an AI coding agent?</b><br>
One command. 16 checks. A score out of 100 — and a badge you can commit.</p>

<p align="center">
  <a href="assets/agent-ready.svg"><img alt="agent-ready score" src="assets/agent-ready.svg"></a>
  <a href="https://github.com/paulwang20110424-commits/agent-ready/actions/workflows/tests.yml"><img alt="tests" src="https://github.com/paulwang20110424-commits/agent-ready/actions/workflows/tests.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8%2B-blue.svg">
  <img alt="Zero dependencies" src="https://img.shields.io/badge/dependencies-0-brightgreen.svg">
  <a href="README.zh-CN.md"><img alt="中文" src="https://img.shields.io/badge/README-中文-red.svg"></a>
</p>

---

## The gap nobody measures

You handed a repository to Claude Code, Cursor, Codex or Aider. It read the README, grepped for the
test command, guessed, edited the wrong file — and you spent the next twenty minutes explaining your
own project to a machine that could not ask you a single question.

That cost is structural. **An AI agent is a new contributor that can never ask.** It cannot ask where
the program starts, how to run the tests, which of the four config files is the real one, or whether
`dist/` is the source. Every missing answer becomes exploration, and exploration is exactly what you
pay for in tokens, latency and wrong edits.

`agent-ready` measures that gap. It asks one question — *how much of what an agent needs is actually
written down in this repository?* — and answers with a number, a letter grade, and the shortest
ordered list of fixes.

## Try it on a project you know

```console
$ python3 agent_ready.py ~/code/flask
```

```
  agent-ready 1.0.0  ·  /Users/me/code/flask
  ──────────────────────────────────────────────────────────────────────────
  84 source files  ·  18,340 LOC  ·  Python 83  ·  Shell 1

      C   65.0 / 100
      ████████████████████░░░░░░░░░░

  FRONT DOOR     █░░░░░░░░░   4.0 / 36
    ✗  Agent instructions file          no AGENTS.md, CLAUDE.md, .cursorrules or copilot instructions
    ✗  Real commands inside it          no instructions file to read
    !  README quickstart with commands  README.md has some commands, but not a full install → run path
    ✗  Instructions are a map           no instructions file
    ✗  llms.txt index                   no llms.txt
  RUN RELIABLY   ██████████  28.0 / 28
    ✓  One obvious way to run tests     pyproject.toml test config · 48 test files
    ✓  Dependency lockfile committed    uv.lock
    ✓  CI runs the checks               .github/workflows
    ✓  Runtime version is pinned        .devcontainer/devcontainer.json
  NAVIGABLE      █████████░  21.0 / 24
    ✓  Predictable source layout        src/ · 0 source files at root
    !  Files small enough to reason     2 files over 1,500 lines (20% of all code)
    ✓  A findable entry point           src/flask/__main__.py
    ✓  A test suite exists              48 test files, 8,253 lines
  HYGIENE        ██████████  12.0 / 12
    ✓  No build output in the tree      clean
    ✓  Types are checked                pyproject: mypy/pyright
    ✓  Dependencies are pinned          no '*' / 'latest' / '>=' ranges found

  TOP FIXES
    +12    Create AGENTS.md with build/test/lint commands and a short layout map.
       run: python3 agent_ready.py . --init
     +8    Put install/test/lint commands in fenced code blocks.
     +4    Add the missing install or run/test command in a fenced block.
```

Read that again: **Flask scores 28/28 for runnability and 4/36 on the front door.** Lockfile, CI,
dev container, type checking, 48 test files — flawless. And still an agent that lands in it has to
reverse-engineer where to start, because none of that knowledge is written in the one place an agent
looks first.

That is not a criticism of Flask. It is a new kind of debt that appeared about eighteen months ago
and that nobody has been measuring.

## We scored the popular ones

| Repository | Score | Grade | Biggest gap |
|---|---|---|---|
| flask | 65 | **C** | no agent instructions (4/36 front door) |
| fastapi | 59 | **C** | instructions + layout discoverability |
| opencode | 65 | **C** | instructions + giant files |
| express | 48 | **D** | no lockfile, no pinned runtime, no instructions |
| a 567k-line TypeScript monorepo | 82 | **B** | giant files, no pinned runtime |

Nobody is an A. These are mature, well-loved projects, and each one still leaves an agent guessing
at least six things. If you believe your repo is different, the audit is one command:

```bash
curl -fsSLO https://raw.githubusercontent.com/paulwang20110424-commits/agent-ready/main/agent_ready.py
python3 agent_ready.py .
```

## Quick start

No dependencies, no API keys, no network, no account. Python 3.8+.

```bash
# 1. nothing to install — it is one file
curl -fsSLO https://raw.githubusercontent.com/paulwang20110424-commits/agent-ready/main/agent_ready.py
python3 agent_ready.py .

# 2. or install the command
pipx install "git+https://github.com/paulwang20110424-commits/agent-ready"
agent-ready ~/code/my-app

# 3. or clone and run
git clone https://github.com/paulwang20110424-commits/agent-ready && cd agent-ready
make test
```

## The 16 checks (100 points)

Four areas, every point backed by evidence it prints right next to the score.

| Area | Points | What it asks |
|---|---|---|
| **Front door** | 36 | Is there an `AGENTS.md`? Does it contain *runnable commands*? Does the README have a real quickstart? Is there an `llms.txt`? Is the instructions file a map (20–500 lines) rather than a manual? |
| **Run reliably** | 28 | Is there one discoverable test command? Is a lockfile committed? Is CI configured? Is the runtime version pinned? |
| **Navigable** | 24 | Is the layout predictable? Any file over 1,500 lines? A findable entry point? A real test suite? |
| **Hygiene** | 12 | Is build output committed? Is a type checker enabled (strict)? Are dependencies pinned? |

Fairness rules that took real projects to get right:

- A project with **no dependencies** does not lose points for having no lockfile.
- A small flat repo (a single-file tool) is a legitimate layout — `src/` is not mandatory.
- `sympy/`, `django/`, `requests/` are package layouts and score the same as `src/`.
- `python -m unittest`, `make test`, `cargo test`, `go test` are all first-class test commands.
- A single 400-line test file counts as a real suite; three stub files do not.

Run `agent-ready . --rules` to print the whole rubric, and `--json` to get every number.

## Fix it, not just find it

`--init` writes an `AGENTS.md` from what is actually in your repository: the real install and test
commands for your package manager, your entry points, your directory layout, and the rules that
matter. No templates, no boilerplate, no API call.

```console
$ python3 agent_ready.py . --init
  wrote /Users/me/code/project/AGENTS.md  (re-run the audit to see the new score)

$ python3 agent_ready.py . --json | jq '.grade, .score'
"F"      # before
31.0
```

On a real repository with no agent instructions at all, one command took it from **C 61 → A 85**.
The generated file is a starting point you are expected to edit — it contains only true statements
about your repo, which is more than most hand-written instruction files manage.

## Put the badge in your README

`--badge` writes a static SVG. Commit it, link it, done — no server, no account, no expiration.

```bash
python3 agent_ready.py . --badge assets/agent-ready.svg
```

```markdown
[![agent ready](assets/agent-ready.svg)](https://github.com/you/your-repo)
```

The badge shows your real grade and score, and it re-generates when you improve. It is honest by
construction: the number is recomputed from your tree, not typed by hand.

## Gate it in CI

```yaml
- name: Agent readiness must not regress
  run: python3 agent_ready.py . --fail-under 85
```

Exit code 1 breaks the build if the score drops. Add `--json` and you can chart it over time.

## Usage

```
agent-ready [ROOT] [options]

  ROOT                     repository to audit (default: .)

      --init               write AGENTS.md from what is in this repo
      --badge [PATH]       write an SVG badge (default: agent-ready.svg)
      --md [PATH]          write a markdown report (default: AGENT_READINESS.md)
      --json               machine-readable output, for tooling and agents
      --rules              print the full scoring rubric and exit
  -v, --verbose            explain every check and its fix
      --fail-under N       exit 1 if the score is below N (for CI)
      --no-color           disable colour
      --version
```

## Why you can trust the number

- **Deterministic.** Same tree, same score. No LLM, no sampling, no variance.
- **Explainable.** Every check prints the evidence it used (`AGENTS.md: 150 lines`,
  `2 files over 1,500 lines (20% of all code)`), the reason it matters, and the fix.
- **Auditable.** `--rules` prints all 100 points. If you disagree with a weight, that is a
  conversation with a number attached — open an issue.
- **Local.** It never makes a network call and never writes to your repo unless you pass `--init`,
  `--md` or `--badge`.

## What it is not

- **Not a code-quality score.** Beautiful code in a flat repo with no test command still fails an agent.
- **Not a security audit.** It does not look for vulnerabilities.
- **Not perfect.** Detection is heuristic; a weird layout can produce a false negative. If the score
  feels wrong for your repo, that is a bug worth reporting — the rules are meant to be fair to
  legitimate projects, and several were rewritten after real-repo testing.

## Dogfood

This repository is audited by itself, and the badge at the top is generated by the tool:

```console
$ python3 agent_ready.py .
      A+  96.0 / 100
```

The 4 missing points are a type checker we have not wired up yet. We could have added a config file
to take the 100 — that would defeat the point of the exercise.

## Contributing

The whole tool is `agent_ready.py`. A new rule is one `check_*` function returning evidence, a `why`
and a `fix` — plus a test. Keep the weights summing to 100, run `make ci`, and do not add
dependencies.

```bash
make test    # 27 tests, under a second, no dependencies
make audit   # score this repository with the tool you just changed
```

## License

MIT. Use it, ship it, embed it in your own tooling.

---

<p align="center">
  <b>Run it on your repo. If the score stings, the fix list is right there.</b><br>
  <sub>中文说明见 <a href="README.zh-CN.md">README.zh-CN.md</a></sub>
</p>
