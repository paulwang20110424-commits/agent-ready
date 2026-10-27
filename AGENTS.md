# AGENTS.md

Guidance for AI coding agents working in this repository. It is a map, not a manual:
everything here is chosen so you can make a correct first edit in a few minutes.

## What this project is

`agent_ready.py` scores a repository 0-100 on how well an AI coding agent can work in it,
prints what is missing and why it matters, and can generate the missing `AGENTS.md`.

Zero runtime dependencies by design. One file. Python 3.8+.

## Commands

Run these exactly. Do not invent alternatives, and do not add dependencies.

```bash
# install for development (the tool itself has no runtime dependencies)
python3 -m pip install -e .

# run the test suite - this is how you verify any change
python3 -m unittest discover -s tests -v

# audit this repository with the tool you are editing
python3 agent_ready.py .

# machine-readable audit, useful when you need exact numbers
python3 agent_ready.py . --json
```

## Layout

- `agent_ready.py` - the entire tool: scanning, the 16 checks, scoring, terminal/markdown/JSON
  rendering, SVG badge generation, and `--init` AGENTS.md generation.
- `tests/test_agent_ready.py` - the full test suite (no dependencies, runs in under a second).
- `.github/workflows/tests.yml` - CI across Python 3.8-3.13.
- `assets/agent-ready.svg` - the badge this project displays in its own README.
- `pyproject.toml` - packaging and the `agent-ready` console script.

## Changing the rubric

The score must stay explainable; that is the whole product. When you touch scoring:

1. Each rule lives in one `check_*` function and returns a `Check` with evidence, a `why` and a `fix`.
2. The weights live in `render_rules()` and must keep the total at exactly 100 points.
3. Every rule needs a test in `tests/test_agent_ready.py` covering pass, warn and fail.
4. Re-run `python3 agent_ready.py .` - this repository must not regress.
5. If a rule is unfair to a legitimate project layout, fix the rule rather than the project.

## Rules for changes here

- Read a whole function before editing it; never patch code you have not read.
- Keep the tool dependency-free. Standard library only, Python 3.8 compatible syntax.
- Never make network calls, never touch a user's files without an explicit flag, never phone home.
- Every user-visible string must be honest: no score inflation, no "AI-powered" claims.
- Change one concern per commit; keep the diff explainable in one sentence.
- Run the tests before claiming a change works. Passing tests are the only evidence.
- If the repository does not contain the answer you need, ask instead of guessing.
