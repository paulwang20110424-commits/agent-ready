#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent-ready - is this codebase ready for an AI coding agent?

Zero dependencies. One file. Python 3.8+.

    agent-ready .                 score this repo 0-100 with a letter grade
    agent-ready . --badge a.svg   write a badge you can commit and show off
    agent-ready . --init          generate an AGENTS.md from what is actually here
    agent-ready . --md report.md  a shareable audit report

Every point is deterministic and explained. No network, no LLM, no account.

The idea is simple: a coding agent is a new contributor that can never ask a
question. It cannot ask "how do I run the tests?", "where does the program
start?", "which file is the important one?" - so it guesses, and guessing is
what you pay for in tokens, latency, and wrong edits.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# File knowledge
# --------------------------------------------------------------------------

CODE_EXT: Dict[str, str] = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript",
    ".vue": "Vue", ".svelte": "Svelte",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".scala": "Scala",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".swift": "Swift",
    ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".hpp": "C++", ".m": "Objective-C",
    ".ex": "Elixir", ".exs": "Elixir", ".lua": "Lua", ".dart": "Dart", ".zig": "Zig",
    ".sh": "Shell", ".bash": "Shell",
}

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "bower_components",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox",
    ".venv", "venv", "env", "site-packages", ".gradle", ".next", ".nuxt",
    ".svelte-kit", ".cache", ".parcel-cache", ".turbo", "coverage", "htmlcov",
    "vendor", "third_party", "third-party", "Pods", "DerivedData", ".dart_tool",
    ".terraform", ".expo", "bazel-out", ".stack-work", "elm-stuff", "_build",
}

# Directories that are build output: fine to exist, suspicious to commit.
BUILD_DIRS = {"dist", "build", "out", "output", "target", "obj", ".eggs", "htmlcov", "coverage"}

AGENT_FILES = [
    "AGENTS.md", "agents.md", "CLAUDE.md", "claude.md", "GEMINI.md",
    ".cursorrules", ".github/copilot-instructions.md", ".windsurfrules",
    ".clinerules", "CONVENTIONS.md", ".cursor/rules",
]
NATIVE_AGENT_FILE = "AGENTS.md"

LOCKFILES = [
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock", "requirements.lock",
    "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock", "packages.lock.json",
    "gradle.lockfile", "pubspec.lock", "mix.lock", "flake.lock",
]

PINNED_RUNTIME = [
    ".nvmrc", ".node-version", ".python-version", ".ruby-version", ".tool-versions",
    "rust-toolchain", "rust-toolchain.toml", ".sdkmanrc", "global.json",
    "Dockerfile", "docker-compose.yml", "compose.yaml", ".devcontainer/devcontainer.json",
    "mise.toml", ".mise.toml",
]

CI_PATHS = [
    ".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml",
    ".travis.yml", "Jenkinsfile", "bitbucket-pipelines.yml", ".buildkite",
    ".drone.yml", "appveyor.yml", ".woodpecker.yml",
]

LAYOUT_DIRS = ["src", "lib", "packages", "app", "apps", "cmd", "internal", "pkg", "core"]

ENTRY_FILES = [
    "main.py", "__main__.py", "manage.py", "wsgi.py", "asgi.py", "index.php",
    "main.go", "main.rs", "main.c", "main.cpp", "main.swift", "Application.java",
    "Program.cs", "Main.kt", "main.ex",
]
ENTRY_DIR_FILES = re.compile(r"^(src|app|cmd|bin|packages/[^/]+/src)/(main|index|cli|server|app)\.\w+$")

README_NAMES = ["README.md", "readme.md", "README.rst", "README", "README.txt", "Readme.md"]

INSTALL_CMD_RE = re.compile(
    r"\b(npm (ci|install|i)|yarn( install)?|pnpm (install|i)|bun install|pip3? install|"
    r"poetry install|uv (sync|pip install)|pipx install|bundle install|composer install|"
    r"cargo (build|install)|go (get|mod download)|dotnet restore|mvn install|gradle build)\b"
)
TEST_CMD_RE = re.compile(
    r"\b(npm (run )?test|yarn test|pnpm test|bun test|pytest|py\.test|tox|nox|unittest|"
    r"python3? -m pytest|python3? -m unittest|go test|cargo test|mvn test|gradle test|"
    r"dotnet test|phpunit|rspec|jest|vitest|make test|bats)\b"
)
BUILD_CMD_RE = re.compile(r"\b(npm run build|yarn build|pnpm build|cargo build|go build|make|dotnet build|mvn package|gradle build|tsc)\b")
LINT_CMD_RE = re.compile(r"\b(eslint|ruff|flake8|pylint|prettier|black|golangci-lint|cargo clippy|rubocop|shellcheck|mypy|pyright|tsc --noEmit)\b")
RUN_CMD_RE = re.compile(r"\b(npm (run )?dev|npm start|yarn dev|pnpm dev|python3? \S+\.py|uvicorn|flask run|go run|cargo run|docker compose up|make run)\b")

MAX_SCAN_FILES = 60_000

# --------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------

@dataclass
class RepoFile:
    path: str          # posix, relative to root
    ext: str
    language: str
    lines: int
    size: int
    is_binary: bool = False


def _glob_to_regex(pattern: str) -> str:
    out: List[str] = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern.startswith("**", i):
                i += 2
                if i < n and pattern[i] == "/":
                    i += 1
                out.append("(?:.*/)?")
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = i + 1
            while j < n and pattern[j] != "]":
                j += 1
            out.append(pattern[i:j + 1] if j < n else re.escape(c))
            i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


class IgnoreRules:
    def __init__(self, patterns: Iterable[str] = ()) -> None:
        self.rules: List[Tuple[bool, bool, re.Pattern]] = []
        for raw in patterns:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:]
            dir_only = line.endswith("/")
            line = line.strip("/")
            if not line:
                continue
            anchored = "/" in line
            body = _glob_to_regex(line)
            rx = re.compile(("^" + body + "$") if anchored else ("(?:^|/)" + body + "$"))
            self.rules.append((negate, dir_only, rx))

    @classmethod
    def from_repo(cls, root: Path) -> "IgnoreRules":
        patterns: List[str] = []
        for name in (".gitignore", ".dockerignore", ".npmignore"):
            p = root / name
            if p.is_file():
                try:
                    patterns.extend(p.read_text(encoding="utf-8", errors="replace").splitlines())
                except OSError:
                    pass
        return cls(patterns)

    def ignored(self, relpath: str, is_dir: bool = False) -> bool:
        result = False
        for negate, _dir_only, rx in self.rules:
            if rx.search(relpath):
                result = not negate
        return result


@dataclass
class Repo:
    root: Path
    files: List[RepoFile]
    ignore: IgnoreRules
    names: Dict[str, str] = field(default_factory=dict)   # lowercase basename/relpath -> relpath

    def find(self, *candidates: str) -> Optional[str]:
        for cand in candidates:
            if (self.root / cand).exists():
                return cand
        for cand in candidates:
            key = cand.lower().strip("/")
            if key in self.names:
                return self.names[key]
        return None

    def has_dir(self, name: str) -> bool:
        return (self.root / name).is_dir()

    def exists(self, relpath: str) -> bool:
        return (self.root / relpath).exists()

    def read(self, relpath: str, limit: int = 400_000) -> str:
        try:
            with (self.root / relpath).open("rb") as fh:
                return fh.read(limit).decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return ""

    @property
    def code_files(self) -> List[RepoFile]:
        return [f for f in self.files if f.language and not f.is_binary]

    @property
    def total_loc(self) -> int:
        return sum(f.lines for f in self.code_files)

    def languages(self) -> List[Tuple[str, int]]:
        counter: Counter = Counter(f.language for f in self.code_files if f.language)
        return counter.most_common()

    def top_level_dirs(self) -> List[str]:
        return sorted(p.name for p in self.root.iterdir()
                      if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith("."))


def count_lines(path: Path) -> Tuple[int, int, bool]:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            chunk = fh.read(1024 * 512)
        if b"\x00" in chunk[:8000]:
            return 0, size, True
        if not chunk:
            return 0, size, False
        lines = chunk.count(b"\n") + (0 if chunk.endswith(b"\n") else 1)
        if size > len(chunk):
            lines = int(lines * (size / float(len(chunk))))
        return lines, size, False
    except (OSError, ValueError):
        return 0, 0, False


def scan_repo(root: Path) -> Repo:
    ignore = IgnoreRules.from_repo(root)
    files: List[RepoFile] = []
    names: Dict[str, str] = {}
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        keep: List[str] = []
        for d in sorted(dirnames):
            if d in SKIP_DIRS:
                continue
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if ignore.ignored(rel, True):
                continue
            keep.append(d)
            names.setdefault(d.lower(), rel)
        dirnames[:] = keep
        for fname in sorted(filenames):
            seen += 1
            if seen > MAX_SCAN_FILES:
                break
            rel = f"{rel_dir}/{fname}" if rel_dir else fname
            names.setdefault(rel.lower(), rel)
            names.setdefault(fname.lower(), rel)
            ext = os.path.splitext(fname)[1].lower()
            language = CODE_EXT.get(ext, "")
            lines, size, binary = count_lines(Path(dirpath) / fname)
            files.append(RepoFile(path=rel, ext=ext, language=language,
                                  lines=lines, size=size, is_binary=binary))
        if seen > MAX_SCAN_FILES:
            break
    return Repo(root=root, files=files, ignore=ignore, names=names)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"


@dataclass
class Check:
    id: str
    title: str
    max_points: int
    earned: float
    status: str
    evidence: str
    why: str
    fix: str = ""
    auto: str = ""     # a command that fixes it, if we can fix it ourselves


@dataclass
class Category:
    name: str
    max_points: int
    checks: List[Check]

    @property
    def earned(self) -> float:
        return sum(c.earned for c in self.checks)


def _status(earned: float, maximum: float) -> str:
    if maximum <= 0:
        return SKIP
    ratio = earned / maximum
    if ratio >= 0.999:
        return PASS
    return WARN if ratio > 0 else FAIL


def _mk(cid: str, title: str, maximum: float, earned: float, evidence: str,
        why: str, fix: str = "", auto: str = "") -> Check:
    return Check(id=cid, title=title, max_points=int(round(maximum)),
                 earned=round(min(earned, maximum), 2), status=_status(earned, maximum),
                 evidence=evidence, why=why, fix=fix, auto=auto)


def fenced_blocks(text: str) -> List[str]:
    return re.findall(r"```.*?\n(.*?)```", text, re.S)


def commands_in(text: str) -> Dict[str, int]:
    """Which kinds of runnable command does this markdown actually contain?"""
    found = {"install": 0, "test": 0, "build": 0, "lint": 0, "run": 0}
    for block in fenced_blocks(text):
        for line in block.splitlines():
            line = line.strip().lstrip("$ ").strip()
            if not line or line.startswith("#"):
                continue
            for key, rx in (("install", INSTALL_CMD_RE), ("test", TEST_CMD_RE),
                            ("build", BUILD_CMD_RE), ("lint", LINT_CMD_RE),
                            ("run", RUN_CMD_RE)):
                if rx.search(line):
                    found[key] += 1
    return found


def detect_package_manager(repo: Repo) -> Tuple[str, str]:
    """Return (install command, test command) inferred from the repo."""
    if repo.exists("pnpm-lock.yaml"):
        return "pnpm install", "pnpm test"
    if repo.exists("yarn.lock"):
        return "yarn install", "yarn test"
    if repo.exists("bun.lockb"):
        return "bun install", "bun test"
    if repo.exists("package.json"):
        return "npm ci", "npm test"
    if repo.exists("uv.lock"):
        return "uv sync", "uv run pytest"
    if repo.exists("poetry.lock") or repo.exists("pyproject.toml") and "[tool.poetry]" in repo.read("pyproject.toml"):
        return "poetry install", "poetry run pytest"
    if repo.exists("Pipfile"):
        return "pipenv install", "pipenv run pytest"
    if repo.exists("requirements.txt") or repo.exists("setup.py") or repo.exists("pyproject.toml"):
        return "pip install -e .", "pytest"
    if repo.exists("Cargo.toml"):
        return "cargo build", "cargo test"
    if repo.exists("go.mod"):
        return "go mod download", "go test ./..."
    if repo.exists("Gemfile"):
        return "bundle install", "bundle exec rspec"
    if repo.exists("composer.json"):
        return "composer install", "composer test"
    if repo.exists("pom.xml"):
        return "mvn install", "mvn test"
    if repo.exists("build.gradle") or repo.exists("build.gradle.kts"):
        return "./gradlew build", "./gradlew test"
    return "", ""


TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs)/|[._-](test|spec)\.[a-z]+$|_test\.\w+$|"
    r"(Test|Tests|_spec)\.(java|kt|cs|scala|php|rb)$"
)


def test_files(repo: Repo) -> List[RepoFile]:
    return [f for f in repo.code_files if TEST_PATH_RE.search(f.path)]


def source_files_at_root(repo: Repo) -> List[RepoFile]:
    return [f for f in repo.code_files if "/" not in f.path]


# ---- individual checks ----------------------------------------------------

def check_agents_md(repo: Repo) -> Check:
    maximum = 12
    found: Optional[str] = None
    for cand in AGENT_FILES:
        hit = repo.find(cand)
        if hit:
            found = hit
            break
    if not found:
        return _mk("agents-md", "Agent instructions file", maximum, 0,
                   "no AGENTS.md, CLAUDE.md, .cursorrules or copilot instructions",
                   "An agent re-derives your conventions from scratch every session. "
                   "This file is the cheapest permanent fix in the whole audit.",
                   "Create AGENTS.md with build/test/lint commands and a short layout map.",
                   "python3 agent_ready.py . --init")
    native = os.path.basename(found).lower() == NATIVE_AGENT_FILE.lower()
    points = maximum if native else maximum * 2 / 3
    return _mk("agents-md", "Agent instructions file", maximum, points,
               f"{found}" + ("" if native else "  (non-standard name: agents look for AGENTS.md)"),
               "One canonical file that every agent tool reads — no per-tool duplication.",
               "" if native else "Rename or symlink it to AGENTS.md so all tools pick it up.")


def check_agents_commands(repo: Repo, agent_file: Optional[str]) -> Check:
    maximum = 8
    if not agent_file:
        return _mk("agents-md-commands", "Real commands inside the instructions", maximum, 0,
                   "no instructions file to read",
                   "An agent that cannot see the test command will invent one — and fail.",
                   "Put install/test/lint commands in fenced code blocks.",
                   "python3 agent_ready.py . --init")
    text = repo.read(agent_file)
    cmds = commands_in(text)
    kinds = [k for k, v in cmds.items() if v]
    if not kinds:
        return _mk("agents-md-commands", "Real commands inside the instructions", maximum, 0,
                   f"{agent_file} contains no runnable commands",
                   "Prose rules are cheap; commands are what an agent actually executes.",
                   "Add fenced blocks with install / test / lint commands.",
                   "python3 agent_ready.py . --init")
    points = maximum if len(kinds) >= 2 else maximum / 2
    return _mk("agents-md-commands", "Real commands inside the instructions", maximum, points,
               "found: " + ", ".join(sorted(kinds)),
               "Runnable commands turn 'figure out the project' into 'read one file'.")


def check_readme_quickstart(repo: Repo) -> Check:
    maximum = 8
    readme = repo.find(*README_NAMES)
    if not readme:
        return _mk("readme-quickstart", "README quickstart with commands", maximum, 0,
                   "no README found",
                   "Both humans and agents start at the README; without commands it is a brochure.",
                   "Add a Quick Start section with copy-pasteable commands.")
    text = repo.read(readme)
    cmds = commands_in(text)
    if cmds["install"] and (cmds["test"] or cmds["run"] or cmds["build"]):
        return _mk("readme-quickstart", "README quickstart with commands", maximum, maximum,
                   f"{readme} has install + runnable commands",
                   "The fastest possible path from clone to running code.")
    if sum(cmds.values()) > 0:
        return _mk("readme-quickstart", "README quickstart with commands", maximum, maximum / 2,
                   f"{readme} has some commands, but not a full install → run path",
                   "A partial quickstart leaves the agent guessing the missing half.",
                   "Add the missing install or run/test command in a fenced block.")
    return _mk("readme-quickstart", "README quickstart with commands", maximum, 0,
               f"{readme} has no fenced commands",
               "Without commands the agent must reverse-engineer your setup.",
               "Add a Quick Start section with install + test commands.")


def check_agent_file_size(repo: Repo, agent_file: Optional[str]) -> Check:
    maximum = 4
    if not agent_file:
        return _mk("agents-md-size", "Instructions are a map, not a manual", maximum, 0,
                   "no instructions file", "Long instruction files crowd out the code they describe.",
                   "Keep AGENTS.md between ~20 and ~500 lines.", "python3 agent_ready.py . --init")
    lines = repo.read(agent_file).count("\n") + 1
    if 20 <= lines <= 500:
        return _mk("agents-md-size", "Instructions are a map, not a manual", maximum, maximum,
                   f"{agent_file}: {lines} lines",
                   "Enough to orient, small enough to load on every single turn.")
    if lines < 20:
        return _mk("agents-md-size", "Instructions are a map, not a manual", maximum, maximum / 2,
                   f"{agent_file}: only {lines} lines",
                   "Too thin to change behaviour — an agent still has to explore.",
                   "Add the layout map and the commands.")
    return _mk("agents-md-size", "Instructions are a map, not a manual", maximum, maximum / 2,
               f"{agent_file}: {lines} lines (long)",
               "Every line here is context spent before the agent reads any code.",
               "Move detail into docs/ and link it; keep AGENTS.md as the index.")


def check_llms_txt(repo: Repo) -> Check:
    maximum = 4
    hit = repo.find("llms.txt", "docs/llms.txt", "public/llms.txt")
    if hit:
        return _mk("llms-txt", "llms.txt index", maximum, maximum, hit,
                   "A machine-first index of your docs: the emerging convention for agent-readable projects.")
    return _mk("llms-txt", "llms.txt index", maximum, 0,
               "no llms.txt",
               "Optional but a strong signal: a flat, link-rich index for machines instead of a rendered site.",
               "Add llms.txt listing the key docs and their links.")


def check_test_command(repo: Repo) -> Check:
    maximum = 10
    install_cmd, test_cmd = detect_package_manager(repo)
    evidence: List[str] = []
    points = 0.0
    # explicit script/config for tests
    pkg = repo.find("package.json")
    if pkg:
        data = repo.read(pkg)
        if re.search(r'"test"\s*:', data):
            points = max(points, 10.0)
            evidence.append('package.json "scripts.test"')
        elif '"scripts"' in data:
            points = max(points, 4.0)
            evidence.append("package.json without a test script")
    if repo.exists("Makefile") and re.search(r"^test:", repo.read("Makefile"), re.M):
        points = max(points, 10.0)
        evidence.append("Makefile target 'test'")
    for cfg in ("pytest.ini", "tox.ini", "noxfile.py", "setup.cfg"):
        if repo.exists(cfg):
            points = max(points, 10.0)
            evidence.append(cfg)
    pyproject = repo.find("pyproject.toml")
    if pyproject and re.search(r"\[tool\.(pytest|tox|nox)", repo.read(pyproject)):
        points = max(points, 10.0)
        evidence.append("pyproject.toml test config")
    if repo.exists("Cargo.toml") or repo.exists("go.mod"):
        points = max(points, 10.0)
        evidence.append("cargo test" if repo.exists("Cargo.toml") else "go test (built in)")
    if not points:
        for ci in (".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml"):
            p = repo.root / ci
            if p.is_dir():
                for f in sorted(p.glob("*.yml")) + sorted(p.glob("*.yaml")):
                    if TEST_CMD_RE.search(f.read_text(encoding="utf-8", errors="replace")):
                        points = 8.0
                        evidence.append(f"{ci}/{f.name}")
                        break
            elif p.is_file() and TEST_CMD_RE.search(p.read_text(encoding="utf-8", errors="replace")):
                points = 8.0
                evidence.append(ci)
            if points:
                break
    n_test_files = len(test_files(repo))
    if n_test_files:
        evidence.append(f"{n_test_files} test files")
    if points:
        return _mk("test-command", "One obvious way to run the tests", maximum, points,
                   " · ".join(evidence),
                   "This is the single highest-value fact in a codebase: it is how an agent knows "
                   "its change did not break anything.")
    if n_test_files:
        return _mk("test-command", "One obvious way to run the tests", maximum, 4,
                   f"{n_test_files} test files, but no discoverable command",
                   "Tests exist but the agent cannot discover how to run them.",
                   f"Document it: add a 'test' script / Makefile target, e.g. `{test_cmd or 'pytest'}`.")
    return _mk("test-command", "One obvious way to run the tests", maximum, 0,
               "no tests and no test command",
               "Without tests an agent cannot verify anything it writes — expect confident breakage.",
               "Add a test suite and a documented command to run it.")


def has_dependencies(repo: Repo) -> bool:
    """Does this project install anything at all? A zero-dependency tool has nothing to lock."""
    pkg = repo.find("package.json")
    if pkg:
        text = repo.read(pkg)
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            m = re.search(r'"%s"\s*:\s*\{([^}]*)\}' % key, text, re.S)
            if m and re.search(r'"[^"]+"\s*:', m.group(1)):
                return True
    pyproject = repo.find("pyproject.toml")
    if pyproject:
        text = repo.read(pyproject)
        m = re.search(r"^\s*dependencies\s*=\s*\[(.*?)\]", text, re.S | re.M)
        if m and m.group(1).strip():
            return True
        m = re.search(r"\[tool\.poetry\.dependencies\](.*?)(?=^\[|\Z)", text, re.S | re.M)
        if m and re.search(r"^\s*[a-zA-Z][\w-]*\s*=", m.group(1), re.M):
            names = re.findall(r"^\s*([a-zA-Z][\w-]*)\s*=", m.group(1), re.M)
            if [n for n in names if n.lower() != "python"]:
                return True
    for req in ("requirements.txt", "requirements-dev.txt"):
        hit = repo.find(req)
        if hit and re.search(r"^\s*[a-zA-Z][\w.-]*\s*[<>=!~]", repo.read(hit), re.M):
            return True
    if repo.exists("Cargo.toml") and re.search(r"^\[dependencies\]", repo.read("Cargo.toml"), re.M):
        return True
    if repo.exists("go.mod") and re.search(r"^require\s", repo.read("go.mod"), re.M):
        return True
    if repo.exists("Gemfile") and re.search(r"^\s*gem\s", repo.read("Gemfile"), re.M):
        return True
    return False


def check_lockfile(repo: Repo) -> Check:
    maximum = 7
    found = [n for n in LOCKFILES if repo.exists(n)]
    if found:
        return _mk("lockfile", "Dependency lockfile committed", maximum, maximum,
                   ", ".join(found),
                   "Reproducible installs: the agent gets the exact tree you tested, not 'latest'.")
    if not has_dependencies(repo):
        return _mk("lockfile", "Dependency lockfile committed", maximum, maximum,
                   "no dependencies declared (nothing to lock)",
                   "Nothing to install means nothing to drift: the strongest possible reproducibility.")
    return _mk("lockfile", "Dependency lockfile committed", maximum, 0,
               "no lockfile at the repo root",
               "Unpinned installs are the #1 cause of 'works on my machine' for both people and agents.",
               "Commit your lockfile (package-lock.json, poetry.lock, uv.lock, Cargo.lock, go.sum…).")


def check_ci(repo: Repo) -> Check:
    maximum = 6
    for ci in CI_PATHS:
        if repo.exists(ci):
            return _mk("ci-config", "CI runs the checks", maximum, maximum, ci,
                       "If CI is the source of truth, an agent can trust local results — and you can "
                       "hand it the exact command CI runs.")
    return _mk("ci-config", "CI runs the checks", maximum, 0, "no CI configuration found",
               "CI defines 'correct' in a way neither you nor an agent can argue with.",
               "Add a minimal workflow that installs, builds and tests.")


def check_pinned_runtime(repo: Repo) -> Check:
    maximum = 5
    found = [n for n in PINNED_RUNTIME if repo.exists(n)]
    if found:
        return _mk("pinned-runtime", "Runtime version is pinned", maximum, maximum,
                   ", ".join(found[:3]),
                   "Agents pick whatever runtime is on the machine; pinning removes a whole class of "
                   "'works in CI, fails here' failures.")
    return _mk("pinned-runtime", "Runtime version is pinned", maximum, 0,
               "no .nvmrc/.python-version/.tool-versions/Dockerfile",
               "An unpinned runtime is a silent variable in every single run.",
               "Add .python-version, .nvmrc, .tool-versions or a Dockerfile.")


def source_roots(repo: Repo) -> List[str]:
    """Directories that plausibly hold the source: src/-style, or a package dir.

    A flat repo is not automatically disorganised: `sympy/`, `django/`, `requests/`
    are perfectly conventional. Accept a top-level directory that is clearly a
    package (has __init__.py or matches the project name and holds code).
    """
    present = [d for d in LAYOUT_DIRS if repo.has_dir(d)]
    if present:
        return present
    root_sources = source_files_at_root(repo)
    if len(root_sources) <= 15:
        # small tools: the root *is* the predictable place
        return ["."]
    project = re.sub(r"[^a-z0-9]", "", repo.root.name.lower())
    for d in repo.top_level_dirs():
        path = repo.root / d
        if not path.is_dir():
            continue
        has_init = (path / "__init__.py").exists()
        norm = re.sub(r"[^a-z0-9]", "", d.lower())
        code_inside = [f for f in repo.code_files if f.path.startswith(d + "/")]
        if has_init and len(code_inside) >= 3:
            present.append(d)
        elif norm and (norm in project or project in norm) and len(code_inside) >= 3:
            present.append(d)
    return present[:4]


def check_layout(repo: Repo) -> Check:
    maximum = 7
    present = source_roots(repo)
    root_sources = source_files_at_root(repo)
    if present and len(root_sources) <= 25:
        label = "flat layout" if present == ["."] else f"{', '.join(present[:4])}/"
        return _mk("source-layout", "Source code lives in a predictable place", maximum, maximum,
                   f"{label} · {len(root_sources)} source files at root",
                   "A conventional layout lets an agent jump to the right directory instead of "
                   "reading the whole tree.")
    if present:
        return _mk("source-layout", "Source code lives in a predictable place", maximum, maximum / 2,
                   f"{', '.join(present[:4])}/ but {len(root_sources)} source files sit at the root",
                   "Mixed layout: some code is organised, some is wherever it was written.",
                   "Move root-level sources into the existing source directory.")
    return _mk("source-layout", "Source code lives in a predictable place", maximum, 0,
               f"no src/·lib/·app/·packages/ directory · {len(root_sources)} source files at root",
               "Flat repositories force an agent to list every file before it can decide anything.",
               "Adopt a src/ (or lib/, app/) layout.")


def check_giant_files(repo: Repo) -> Check:
    maximum = 9
    code = [f for f in repo.code_files if f.lines > 0]
    if not code:
        return _mk("no-giant-files", "Files are small enough to reason about", maximum, maximum,
                   "no source files", "Nothing to split.")
    code.sort(key=lambda f: -f.lines)
    giants = [f for f in code if f.lines > 1500]
    total = sum(f.lines for f in code)
    biggest = code[0]
    share = (biggest.lines * 100.0 / total) if total else 0
    if not giants:
        return _mk("no-giant-files", "Files are small enough to reason about", maximum, maximum,
                   f"largest: {biggest.path} ({biggest.lines:,} lines)",
                   "Every file fits in a working context, so an agent can read a whole unit before editing it.")
    giant_lines = sum(f.lines for f in giants)
    giant_share = (giant_lines * 100.0 / total) if total else 0.0
    ratio = len(giants) * 100.0 / max(1, len(code))
    if len(giants) <= 3:
        pts = maximum * 2 / 3
    elif ratio <= 1.0:
        pts = maximum * 4 / 9
    else:
        pts = 0
    listing = ", ".join(f"{f.path} ({f.lines:,})" for f in giants[:3])
    return _mk("no-giant-files", "Files are small enough to reason about", maximum, pts,
               f"{len(giants)} file(s) over 1,500 lines ({giant_share:.0f}% of all code): {listing} · "
               f"largest holds {share:.0f}%",
               "Giant files are where agents truncate, patch the wrong function, and invent APIs. "
               "Reading one costs more than reading twelve small ones.",
               "Split the largest files along their existing seams (classes, sections, helpers).")


def check_entry_point(repo: Repo) -> Check:
    maximum = 5
    hits: List[str] = []
    for f in repo.code_files:
        base = os.path.basename(f.path)
        if base in ENTRY_FILES:
            hits.append(f.path)
        elif ENTRY_DIR_FILES.match(f.path):
            hits.append(f.path)
    if not hits:
        hits = [f.path for f in script_entry_points(repo)]
    if hits:
        return _mk("entry-point", "A findable entry point", maximum, maximum,
                   ", ".join(sorted(hits)[:3]) + (" …" if len(hits) > 3 else ""),
                   "The agent needs one anchor: where execution begins.")
    return _mk("entry-point", "A findable entry point", maximum, 0,
               "no main.py / index.ts / main.go / cmd/* style entry point",
               "Without an entry point an agent cannot trace a request end to end.",
               "Name your entry point conventionally, or document it in AGENTS.md.")


def check_tests_present(repo: Repo) -> Check:
    maximum = 3
    tests = test_files(repo)
    test_lines = sum(f.lines for f in tests)
    if len(tests) >= 3 or test_lines >= 200:
        detail = f"{len(tests)} test file(s), {test_lines:,} lines"
        return _mk("tests-present", "A test suite exists", maximum, maximum, detail,
                   "Tests are the feedback loop an agent uses instead of asking you questions.")
    if tests:
        return _mk("tests-present", "A test suite exists", maximum, maximum * 2 / 3,
                   f"{len(tests)} test file(s), {test_lines:,} lines — thin coverage surface",
                   "A single small test file gives an agent one thin safety net.",
                   "Add tests around the core module before handing the repo to an agent.")
    return _mk("tests-present", "A test suite exists", maximum, 0, "no test files found",
               "No tests means no ground truth for 'did my change work'.",
               "Start with a few tests around the core module.")


def check_clean_tree(repo: Repo) -> Check:
    maximum = 5
    junk: List[str] = []
    for d in BUILD_DIRS:
        if repo.has_dir(d) and not repo.ignore.ignored(d, True):
            junk.append(f"{d}/ (present and not gitignored)")
    big_binaries = [f for f in repo.files
                    if f.is_binary and f.size > 2_000_000
                    and f.ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf"}]
    for f in big_binaries[:3]:
        junk.append(f"{f.path} ({f.size // 1_000_000} MB binary)")
    if not junk:
        return _mk("clean-tree", "No build output or junk in the tree", maximum, maximum,
                   "clean", "Agents happily read generated files and treat them as source.")
    return _mk("clean-tree", "No build output or junk in the tree", maximum, 0,
               "; ".join(junk[:3]),
               "Generated or binary files burn context and teach the agent the wrong patterns.",
               "Add them to .gitignore and remove them from the working tree.")


def check_type_checking(repo: Repo) -> Check:
    maximum = 4
    strong: List[str] = []     # strict / real checker
    weak: List[str] = []       # configured but loose

    tsconfigs = [f.path for f in repo.files
                 if re.match(r"(.*/)?(ts|js)config(\.[\w-]+)?\.json$", f.path)]
    for path in tsconfigs[:12]:
        if re.search(r'"strict"\s*:\s*true', repo.read(path)):
            strong.append(f"{path}: strict")
        else:
            weak.append(f"{path}: not strict")
    if repo.exists("mypy.ini") or repo.exists(".mypy.ini") or repo.exists("pyrightconfig.json"):
        strong.append("mypy/pyright config")
    pyproject = repo.find("pyproject.toml")
    if pyproject and re.search(r"\[tool\.(mypy|pyright)\]", repo.read(pyproject)):
        strong.append("pyproject: mypy/pyright")
    if repo.exists("Cargo.toml") or repo.exists("go.mod"):
        strong.append("compiler-checked language")
    if repo.exists("setup.cfg") and re.search(r"^\[mypy\]", repo.read("setup.cfg"), re.M):
        strong.append("setup.cfg: mypy")

    evidence = ", ".join((strong + weak)[:3]) or "no type checker configured"
    if strong:
        return _mk("type-checking", "Types are checked", maximum, maximum, evidence,
                   "A type checker is a machine-readable contract: it catches an agent's mistakes "
                   "before you do.")
    if weak:
        return _mk("type-checking", "Types are checked", maximum, maximum / 2, evidence,
                   "A checker is configured but loose, so most type mistakes still get through.",
                   'Turn on strict mode ("strict": true, or mypy --strict).')
    return _mk("type-checking", "Types are checked", maximum, 0, evidence,
               "Without types an agent cannot know the shape of any value it passes around.",
               "Enable pyright/mypy, or tsconfig strict mode.")


def check_deterministic_deps(repo: Repo) -> Check:
    maximum = 3
    loose: List[str] = []
    pkg = repo.find("package.json")
    if pkg:
        data = repo.read(pkg)
        for m in re.finditer(r'"[^"]+"\s*:\s*"([^"]*)"', data):
            spec = m.group(1)
            if spec in ("*", "latest", "") or spec.startswith(">="):
                loose.append(spec)
    req = repo.find("requirements.txt")
    if req:
        for line in repo.read(req).splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "==" not in line and ">=" in line:
                loose.append(line[:30])
    if not loose:
        return _mk("deterministic-deps", "Dependencies are pinned", maximum, maximum,
                   "no '*' / 'latest' / '>=' ranges found",
                   "Pinned dependencies mean the agent's install matches yours.")
    return _mk("deterministic-deps", "Dependencies are pinned", maximum, 0,
               f"{len(loose)} unpinned spec(s), e.g. {loose[0]!r}",
               "Floating versions make every install a new experiment.",
               "Pin to exact versions and let the lockfile handle updates.")


def run_checks(repo: Repo) -> List[Category]:
    agent_file = None
    for cand in AGENT_FILES:
        hit = repo.find(cand)
        if hit:
            agent_file = hit
            break

    front = Category("FRONT DOOR", 36, [
        check_agents_md(repo),
        check_agents_commands(repo, agent_file),
        check_readme_quickstart(repo),
        check_agent_file_size(repo, agent_file),
        check_llms_txt(repo),
    ])
    run = Category("RUN RELIABLY", 28, [
        check_test_command(repo),
        check_lockfile(repo),
        check_ci(repo),
        check_pinned_runtime(repo),
    ])
    navigate = Category("NAVIGABLE", 24, [
        check_layout(repo),
        check_giant_files(repo),
        check_entry_point(repo),
        check_tests_present(repo),
    ])
    hygiene = Category("HYGIENE", 12, [
        check_clean_tree(repo),
        check_type_checking(repo),
        check_deterministic_deps(repo),
    ])
    return [front, run, navigate, hygiene]


def score_of(categories: Sequence[Category]) -> float:
    maximum = sum(c.max_points for c in categories) or 1
    earned = sum(c.earned for c in categories)
    return round(earned * 100.0 / maximum, 1)


def grade_of(score: float) -> Tuple[str, str]:
    """Return (grade, colour key)."""
    if score >= 95:
        return "A+", "brightgreen"
    if score >= 85:
        return "A", "green"
    if score >= 70:
        return "B", "yellowgreen"
    if score >= 55:
        return "C", "yellow"
    if score >= 40:
        return "D", "orange"
    return "F", "red"


# --------------------------------------------------------------------------
# Report model
# --------------------------------------------------------------------------

@dataclass
class Audit:
    root: str
    generated_at: str
    score: float
    grade: str
    colour: str
    categories: List[Category]
    languages: List[Tuple[str, int]]
    files_total: int
    files_code: int
    loc: int
    biggest: List[RepoFile]
    install_cmd: str
    test_cmd: str

    def all_checks(self) -> List[Check]:
        return [c for cat in self.categories for c in cat.checks]

    def top_fixes(self, limit: int = 3) -> List[Check]:
        loss = [c for c in self.all_checks() if c.earned < c.max_points]
        loss.sort(key=lambda c: -(c.max_points - c.earned))
        return loss[:limit]

    def as_dict(self) -> dict:
        return {
            "tool": "agent-ready",
            "version": __version__,
            "root": self.root,
            "generated_at": self.generated_at,
            "score": self.score,
            "grade": self.grade,
            "summary": {
                "files_total": self.files_total,
                "files_code": self.files_code,
                "loc": self.loc,
                "languages": [{"name": n, "files": c} for n, c in self.languages],
                "largest_files": [{"path": f.path, "lines": f.lines} for f in self.biggest[:5]],
                "install_command": self.install_cmd,
                "test_command": self.test_cmd,
            },
            "categories": [
                {
                    "name": cat.name,
                    "earned": round(cat.earned, 1),
                    "max": cat.max_points,
                    "checks": [
                        {
                            "id": c.id,
                            "title": c.title,
                            "status": c.status,
                            "earned": c.earned,
                            "max": c.max_points,
                            "evidence": c.evidence,
                            "why": c.why,
                            "fix": c.fix,
                            "auto": c.auto,
                        }
                        for c in cat.checks
                    ],
                }
                for cat in self.categories
            ],
            "top_fixes": [
                {"check": c.id, "gain": round(c.max_points - c.earned, 1), "fix": c.fix}
                for c in self.top_fixes(5)
            ],
        }


def audit_repo(root: Path) -> Audit:
    import datetime
    repo = scan_repo(root)
    categories = run_checks(repo)
    score = score_of(categories)
    grade, colour = grade_of(score)
    code = sorted(repo.code_files, key=lambda f: -f.lines)
    install_cmd, test_cmd = detect_package_manager(repo)
    return Audit(
        root=str(root),
        generated_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        score=score,
        grade=grade,
        colour=colour,
        categories=categories,
        languages=repo.languages()[:5],
        files_total=len(repo.files),
        files_code=len(repo.code_files),
        loc=repo.total_loc,
        biggest=code[:5],
        install_cmd=install_cmd,
        test_cmd=test_cmd,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

class Style:
    def __init__(self, enabled: bool) -> None:
        self.on = enabled

    def _w(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def bold(self, t: str) -> str: return self._w("1", t)
    def dim(self, t: str) -> str: return self._w("2", t)
    def green(self, t: str) -> str: return self._w("32", t)
    def yellow(self, t: str) -> str: return self._w("33", t)
    def red(self, t: str) -> str: return self._w("31", t)
    def cyan(self, t: str) -> str: return self._w("36", t)

    def graded(self, grade: str, text: str) -> str:
        if grade in ("A+", "A"):
            return self.green(text)
        if grade in ("B", "C"):
            return self.yellow(text)
        return self.red(text)

    def status(self, st: str, text: str) -> str:
        if st == PASS:
            return self.green(text)
        if st == WARN:
            return self.yellow(text)
        return self.red(text)


SYMBOL = {PASS: "✓", WARN: "!", FAIL: "✗", SKIP: "·"}


def bar(points: float, maximum: float, width: int = 24) -> str:
    if maximum <= 0:
        return "·" * width
    filled = int(round(min(max(points / maximum, 0.0), 1.0) * width))
    return "█" * filled + "░" * (width - filled)


def render(audit: Audit, style: Style, verbose: bool) -> str:
    out: List[str] = []
    rule = "─" * 74
    out.append("")
    out.append("  " + style.bold("agent-ready") + style.dim(f" {__version__}  ·  {audit.root}"))
    out.append("  " + style.dim(rule))
    langs = "  ·  ".join(f"{n} {c}" for n, c in audit.languages[:4]) or "no source files"
    out.append("  " + "  ·  ".join([
        style.bold(f"{audit.files_code:,}") + " source files",
        style.bold(f"{audit.loc:,}") + " LOC",
        style.dim(langs),
    ]))
    out.append("")
    out.append("      " + style.graded(audit.grade, style.bold(f"{audit.grade:<3}"))
               + style.graded(audit.grade, style.bold(f"{audit.score:5.1f} / 100")))
    out.append("      " + style.graded(audit.grade, bar(audit.score, 100, 30)))
    out.append("")

    for cat in audit.categories:
        head = "  %-14s %s %5.1f / %-3d" % (style.bold(cat.name),
                                            style.dim(bar(cat.earned, cat.max_points, 10)),
                                            cat.earned, cat.max_points)
        out.append(head)
        for c in cat.checks:
            sym = style.status(c.status, SYMBOL[c.status])
            title = c.title
            ev = c.evidence
            line = "    %s  %-42s %s" % (sym, title, style.dim(ev))
            out.append(line[:150])
            if verbose:
                out.append("       " + style.dim("why: " + c.why))
                if c.status != PASS and c.fix:
                    out.append("       " + style.cyan("fix: " + c.fix))
                    if c.auto:
                        out.append("       " + style.dim("run: " + c.auto))

    fixes = audit.top_fixes(3)
    if fixes:
        out.append("")
        out.append("  " + style.dim(rule))
        out.append("  " + style.bold("TOP FIXES"))
        for c in fixes:
            gain = c.max_points - c.earned
            tag = ("+%g" % gain).ljust(6)
            out.append("    " + style.graded("A", tag) + " " + c.fix)
            if c.auto:
                out.append("       " + style.dim("run: " + c.auto))

    out.append("")
    out.append("  " + style.dim(rule))
    out.append("  " + style.dim("next: ")
               + style.cyan("python3 agent_ready.py . --init") + style.dim("   write AGENTS.md for this repo"))
    out.append("  " + style.dim("      ")
               + style.cyan("python3 agent_ready.py . --badge assets/agent-ready.svg")
               + style.dim("   free badge for your README"))
    out.append("")
    return "\n".join(out)


def render_markdown(audit: Audit) -> str:
    lines: List[str] = []
    lines.append("# Agent readiness report")
    lines.append("")
    lines.append(f"> Generated by [agent-ready](https://github.com/paulwang20110424-commits/agent-ready) "
                 f"on {audit.generated_at[:10]}")
    lines.append("")
    lines.append(f"## {audit.grade} — {audit.score:.1f} / 100")
    lines.append("")
    lines.append(f"`{audit.root}` · {audit.files_code:,} source files · {audit.loc:,} LOC")
    lines.append("")
    lines.append("| Area | Score |")
    lines.append("|---|---|")
    for cat in audit.categories:
        lines.append(f"| {cat.name.title()} | {cat.earned:g} / {cat.max_points} |")
    lines.append("")
    for cat in audit.categories:
        lines.append(f"### {cat.name.title()} — {cat.earned:g} / {cat.max_points}")
        lines.append("")
        lines.append("| | Check | Evidence |")
        lines.append("|---|---|---|")
        for c in cat.checks:
            mark = {PASS: "✅", WARN: "⚠️", FAIL: "❌", SKIP: "➖"}[c.status]
            lines.append(f"| {mark} | **{c.title}** ({c.earned:g}/{c.max_points}) | {c.evidence} |")
        lines.append("")
    fixes = audit.top_fixes(3)
    if fixes:
        lines.append("## Top fixes")
        lines.append("")
        for c in fixes:
            lines.append(f"- **+{c.max_points - c.earned:g} points** — {c.fix}")
            if c.auto:
                lines.append(f"  ```bash\n  {c.auto}\n  ```")
        lines.append("")
    lines.append("## What this measures")
    lines.append("")
    lines.append("Whether a coding agent can orient itself in this repository without asking a human: "
                 "is there an instructions file, are there runnable commands, is the layout predictable, "
                 "are files small enough to read. It does **not** measure code quality.")
    lines.append("")
    return "\n".join(lines)


def render_badge(audit: Audit, label: str = "agent ready") -> str:
    """A static shields-style SVG. Commit it, link it, no server involved."""
    value = f"{audit.grade} {audit.score:g}/100"
    colours = {
        "brightgreen": "#4c1", "green": "#97ca00", "yellowgreen": "#a4a61d",
        "yellow": "#dfb317", "orange": "#fe7d37", "red": "#e05d44",
    }
    colour = colours.get(audit.colour, "#9f9f9f")
    cw = 6.6
    lw = int(len(label) * cw) + 12
    vw = int(len(value) * cw) + 12
    total = lw + vw
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{lw}" height="20" fill="#555"/>
    <rect x="{lw}" width="{vw}" height="20" fill="{colour}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lw / 2:.0f}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{lw / 2:.0f}" y="14">{label}</text>
    <text x="{lw + vw / 2:.0f}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{lw + vw / 2:.0f}" y="14">{value}</text>
  </g>
</svg>
'''


# --------------------------------------------------------------------------
# --init : generate an AGENTS.md from what is actually in the repo
# --------------------------------------------------------------------------

def project_tagline(repo: Repo, readme_text: str) -> str:
    """The project's own one-liner, preferring structured manifests over prose."""
    pkg = repo.find("package.json")
    if pkg:
        m = re.search(r'"description"\s*:\s*"([^"]{10,200})"', repo.read(pkg))
        if m:
            return m.group(1)
    for manifest in ("pyproject.toml", "Cargo.toml", "composer.json"):
        hit = repo.find(manifest)
        if hit:
            m = re.search(r'description\s*=\s*"([^"]{10,200})"', repo.read(hit))
            if m:
                return m.group(1)
    # first sentence of the README body, skipping badges/HTML/headings
    paragraph: List[str] = []
    for line in readme_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!", "<", "[", "|", ">", "=", "```", "-", "*")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
        if len(" ".join(paragraph)) > 400:
            break
    text = re.sub(r"[`*_\[\]]|\([^)]*\)", "", " ".join(paragraph)).strip()
    text = re.sub(r"\s+", " ", text)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(sentence) >= 25:
            return sentence[:180].rstrip()
    return text[:180]


SCRIPT_ENTRY_RE = re.compile(
    r"""(if\s+__name__\s*==\s*['"]__main__['"]|^#!.*\b(node|python3?|bash|sh|ruby|php|deno|bun)\b)""",
    re.M,
)


def script_entry_points(repo: Repo, limit: int = 3) -> List[RepoFile]:
    """Files that are actually runnable, for repos without conventional entry names."""
    hits: List[RepoFile] = []
    for f in repo.code_files:
        if f.path.count("/") > 1:
            continue
        head = repo.read(f.path, limit=4000)
        if head and SCRIPT_ENTRY_RE.search(head):
            hits.append(f)
    hits.sort(key=lambda f: -f.lines)
    return hits[:limit]


def detect_layout_summary(repo: Repo) -> List[Tuple[str, str]]:
    """(directory, one-line description) for the top source directories."""
    out: List[Tuple[str, str]] = []
    counts: Counter = Counter()
    for f in repo.code_files:
        parts = f.path.split("/")
        if len(parts) > 1:
            top = "/".join(parts[:2]) if parts[0] in ("packages", "apps", "src") and len(parts) > 2 else parts[0]
            counts[top] += 1
    for name, count in counts.most_common(8):
        if repo.exists(name) and (repo.root / name).is_dir():
            out.append((name, "%d source file%s" % (count, "" if count == 1 else "s")))
    return out


def generate_agents_md(repo: Repo, audit: Audit) -> str:
    install_cmd, test_cmd = audit.install_cmd, audit.test_cmd
    readme = repo.find(*README_NAMES)
    readme_text = repo.read(readme) if readme else ""
    tagline = project_tagline(repo, readme_text)
    project = os.path.basename(audit.root)
    langs = audit.languages
    entries = [f for f in repo.code_files
               if os.path.basename(f.path) in ENTRY_FILES or ENTRY_DIR_FILES.match(f.path)]
    if not entries:
        entries = script_entry_points(repo)
    entries = sorted(entries, key=lambda f: f.path)[:4]

    L: List[str] = []
    L.append(f"# AGENTS.md")
    L.append("")
    L.append(f"This file is for AI coding agents working in `{project}`. "
             f"It is a map, not a manual: everything here should help you make your first correct edit sooner.")
    L.append("")
    if tagline:
        L.append(f"**Project:** {tagline}")
        L.append("")
    if langs:
        L.append("**Stack:** " + ", ".join(f"{n} ({c} files)" for n, c in langs[:3]))
        L.append("")
    L.append("## Commands")
    L.append("")
    L.append("Run these exactly; do not invent alternatives.")
    L.append("")
    L.append("```bash")
    if install_cmd:
        L.append(f"# install dependencies")
        L.append(install_cmd)
    if test_cmd:
        L.append("")
        L.append(f"# run the tests (this is how you verify any change)")
        L.append(test_cmd)
    L.append("```")
    L.append("")
    if entries:
        L.append("## Start here")
        L.append("")
        L.append("Read these before editing anything else:")
        L.append("")
        for e in entries:
            L.append(f"- `{e.path}` — entry point")
        if readme:
            L.append(f"- `{readme}` — what this project is for")
        L.append("")
    layout = detect_layout_summary(repo)
    if layout:
        L.append("## Layout")
        L.append("")
        for name, note in layout:
            L.append(f"- `{name}/` — {note}")
        L.append("")
    L.append("## Rules")
    L.append("")
    L.append("- Read a file completely before editing it; never patch code you have not seen.")
    L.append("- Change one concern per commit. Keep the diff explainable in one sentence.")
    if test_cmd:
        L.append(f"- Run `{test_cmd}` before claiming a change works. Passing tests are the only evidence.")
    L.append("- Do not reformat, rename or reorganise files you were not asked to touch.")
    L.append("- If a task needs information that is not in the repository, ask — do not guess.")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Rulebook (for people who want to argue with the score)
# --------------------------------------------------------------------------

def render_rules() -> str:
    out = ["", "  agent-ready 1.0.0 · the rubric (100 points)", ""]
    names = {
        "agents-md": "Agent instructions file exists (AGENTS.md preferred)",
        "agents-md-commands": "Instructions contain runnable commands",
        "readme-quickstart": "README has install + run/test commands",
        "agents-md-size": "Instructions are 20–500 lines (a map, not a manual)",
        "llms-txt": "llms.txt machine index",
        "test-command": "One discoverable way to run tests",
        "lockfile": "Lockfile committed",
        "ci-config": "CI configuration present",
        "pinned-runtime": "Runtime version pinned",
        "source-layout": "Conventional source layout",
        "no-giant-files": "No source file over 1,500 lines",
        "entry-point": "Findable entry point",
        "tests-present": "A real test suite",
        "clean-tree": "No committed build output / giant binaries",
        "type-checking": "Type checker enabled (strict)",
        "deterministic-deps": "Dependencies pinned",
    }
    weights = {
        "agents-md": 12, "agents-md-commands": 8, "readme-quickstart": 8,
        "agents-md-size": 4, "llms-txt": 4, "test-command": 10, "lockfile": 7,
        "ci-config": 6, "pinned-runtime": 5, "source-layout": 7, "no-giant-files": 9,
        "entry-point": 5, "tests-present": 3, "clean-tree": 5, "type-checking": 4,
        "deterministic-deps": 3,
    }
    cats = {
        "FRONT DOOR": ["agents-md", "agents-md-commands", "readme-quickstart", "agents-md-size", "llms-txt"],
        "RUN RELIABLY": ["test-command", "lockfile", "ci-config", "pinned-runtime"],
        "NAVIGABLE": ["source-layout", "no-giant-files", "entry-point", "tests-present"],
        "HYGIENE": ["clean-tree", "type-checking", "deterministic-deps"],
    }
    for cat, ids in cats.items():
        total = sum(weights[i] for i in ids)
        out.append(f"  {cat:<14} {total} points")
        for i in ids:
            out.append(f"    {weights[i]:>2}  {names[i]}")
        out.append("")
    out.append("  Grades: A+ ≥95 · A ≥85 · B ≥70 · C ≥55 · D ≥40 · F <40")
    out.append("  This measures agent-readiness, not code quality.")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent-ready",
        description="Score how ready a repository is for an AI coding agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  agent-ready .                          score the current repository
  agent-ready . --init                   write a real AGENTS.md for this repo
  agent-ready . --badge assets/ready.svg write a badge to commit in your README
  agent-ready . --md report.md           a shareable audit report
  agent-ready . --rules                  print the full rubric
""",
    )
    p.add_argument("root", nargs="?", default=".", help="repository to audit (default: .)")
    p.add_argument("--init", action="store_true", help="write AGENTS.md from what is in this repo")
    p.add_argument("--badge", nargs="?", const="agent-ready.svg", default=None, metavar="PATH",
                   help="write an SVG badge (default: agent-ready.svg)")
    p.add_argument("--md", nargs="?", const="AGENT_READINESS.md", default=None, metavar="PATH",
                   help="write a markdown report (default: AGENT_READINESS.md)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--rules", action="store_true", help="print the scoring rubric and exit")
    p.add_argument("--verbose", "-v", action="store_true", help="explain every check and its fix")
    p.add_argument("--no-color", action="store_true", help="disable colour")
    p.add_argument("--fail-under", type=float, default=None, metavar="SCORE",
                   help="exit 1 if the score is below this (for CI)")
    p.add_argument("--version", action="version", version="agent-ready " + __version__)
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.rules:
        print(render_rules())
        return 0

    root = Path(args.root).expanduser()
    if not root.exists():
        print(f"agent-ready: no such directory: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"agent-ready: not a directory: {root}", file=sys.stderr)
        return 2
    root = root.resolve()

    style = Style(not args.no_color and os.environ.get("NO_COLOR") is None and sys.stdout.isatty())

    audit = audit_repo(root)
    if args.json:
        print(json.dumps(audit.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(render(audit, style, args.verbose))

    if args.md:
        out = Path(args.md)
        out = out if out.is_absolute() else Path.cwd() / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(audit), encoding="utf-8")
        if not args.json:
            print("  " + style.dim("wrote ") + style.cyan(str(out)))

    if args.badge:
        out = Path(args.badge)
        out = out if out.is_absolute() else Path.cwd() / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_badge(audit), encoding="utf-8")
        if not args.json:
            print("  " + style.dim("wrote ") + style.cyan(str(out)))
            print("  " + style.dim("       add to your README:  ") + style.cyan(f"![agent ready]({args.badge})"))

    if args.init:
        repo = scan_repo(root)
        target = root / "AGENTS.md"
        if target.exists():
            print("  " + style.yellow(f"AGENTS.md already exists — compare with: agent-ready --json"),
                  file=sys.stderr)
        else:
            target.write_text(generate_agents_md(repo, audit), encoding="utf-8")
            print("  " + style.dim("wrote ") + style.cyan(str(target))
                  + style.dim("  (re-run the audit to see the new score)"))

    if args.fail_under is not None and audit.score < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
