#!/usr/bin/env python3
"""Tests for agent-ready. Run with: python3 -m unittest discover -s tests -v"""

import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("agent_ready", ROOT / "agent_ready.py")
ar = importlib.util.module_from_spec(SPEC)
sys.modules["agent_ready"] = ar
SPEC.loader.exec_module(ar)


def write(root: Path, rel: str, text: str = "x = 1\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def make_repo(tmp: Path, files: dict) -> Path:
    root = tmp / "repo"
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        write(root, rel, text)
    return root


GOOD_AGENTS_MD = """# AGENTS.md

Guidance for AI coding agents working in this repository.

## Commands

```bash
npm ci
npm test
npm run build
```

## Layout

- `src/` — application source
- `tests/` — test suite

## Rules

- Read a file before editing it.
- Run the tests before claiming a change works.
- Keep diffs small and explainable.
- Ask when the repository does not contain the answer.
""" + "\n- Follow the existing style.\n" * 5

GOOD_README = """# demo

A tiny demo project.

## Quick Start

```bash
npm ci
npm test
```
"""

GOOD_REPO = {
    "AGENTS.md": GOOD_AGENTS_MD,
    "README.md": GOOD_README,
    "llms.txt": "# demo\n- docs: ./README.md\n",
    "package.json": '{\n  "name": "demo",\n  "description": "A tiny demo project.",\n'
                    '  "scripts": {"test": "jest", "build": "tsc"},\n'
                    '  "devDependencies": {"typescript": "5.4.2"}\n}\n',
    "package-lock.json": '{"lockfileVersion": 3}\n',
    ".nvmrc": "20\n",
    ".gitignore": "node_modules/\ndist/\n",
    "tsconfig.json": '{"compilerOptions": {"strict": true}}\n',
    ".github/workflows/ci.yml": "jobs:\n  test:\n    steps:\n      - run: npm test\n",
    "src/index.ts": "export const hello = () => 'hi';\n",
    "src/util.ts": "export const add = (a: number, b: number) => a + b;\n",
    "src/a.test.ts": "test('a', () => {});\n",
    "src/b.test.ts": "test('b', () => {});\n",
    "tests/c.test.ts": "test('c', () => {});\n",
}

BAD_REPO = {
    "README.md": "just a readme with no commands\n",
    "everything.py": "".join(f"x{i} = {i}\n" for i in range(3000)),
    "more.py": "".join(f"y{i} = {i}\n" for i in range(2000)),
    "helper.py": "def f(): pass\n",
    "dist/bundle.js": "// built\n",
}


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_good_repo_scores_high(self):
        root = make_repo(self.tmp, GOOD_REPO)
        audit = ar.audit_repo(root)
        self.assertGreaterEqual(audit.score, 90, f"expected an A-grade repo, got {audit.score}: "
                                                 f"{[(c.id, c.earned, c.max_points) for c in audit.all_checks() if c.status != 'pass']}")
        self.assertIn(audit.grade, ("A", "A+"))

    def test_bad_repo_scores_low(self):
        root = make_repo(self.tmp, BAD_REPO)
        audit = ar.audit_repo(root)
        self.assertLess(audit.score, 45, f"expected a bad grade, got {audit.score}")
        self.assertIn(audit.grade, ("F", "D"))

    def test_score_is_bounded_and_categories_sum_to_total(self):
        root = make_repo(self.tmp, GOOD_REPO)
        audit = ar.audit_repo(root)
        self.assertGreaterEqual(audit.score, 0.0)
        self.assertLessEqual(audit.score, 100.0)
        total_max = sum(c.max_points for c in audit.categories)
        self.assertEqual(total_max, 100, "the rubric must add up to 100 points")
        for cat in audit.categories:
            self.assertLessEqual(cat.earned, cat.max_points)

    def test_empty_repo_does_not_crash(self):
        root = self.tmp / "empty"
        root.mkdir()
        audit = ar.audit_repo(root)
        self.assertEqual(audit.files_code, 0)
        self.assertIsInstance(audit.score, float)

    def test_grade_boundaries(self):
        self.assertEqual(ar.grade_of(100)[0], "A+")
        self.assertEqual(ar.grade_of(95)[0], "A+")
        self.assertEqual(ar.grade_of(85)[0], "A")
        self.assertEqual(ar.grade_of(70)[0], "B")
        self.assertEqual(ar.grade_of(55)[0], "C")
        self.assertEqual(ar.grade_of(40)[0], "D")
        self.assertEqual(ar.grade_of(0)[0], "F")


class CheckBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _check(self, root, cid):
        audit = ar.audit_repo(root)
        return next(c for c in audit.all_checks() if c.id == cid)

    def test_agents_md_beats_a_custom_name(self):
        native = make_repo(self.tmp, {"AGENTS.md": GOOD_AGENTS_MD, "main.py": "print(1)\n"})
        self.assertEqual(self._check(native, "agents-md").earned, 12)
        tmp2 = Path(tempfile.mkdtemp())
        try:
            custom = make_repo(tmp2, {"CLAUDE.md": GOOD_AGENTS_MD, "main.py": "print(1)\n"})
            self.assertLess(self._check(custom, "agents-md").earned, 12)
            self.assertGreater(self._check(custom, "agents-md").earned, 0)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

    def test_instructions_without_commands_earn_nothing(self):
        root = make_repo(self.tmp, {"AGENTS.md": "# AGENTS.md\n\nBe careful and write good code.\n" * 3})
        self.assertEqual(self._check(root, "agents-md-commands").earned, 0)

    def test_test_command_detection_python(self):
        root = make_repo(self.tmp, {
            "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "tests/test_a.py": "def test_a(): pass\n",
            "app.py": "print(1)\n",
        })
        self.assertGreaterEqual(self._check(root, "test-command").earned, 10)

    def test_test_command_detection_node(self):
        root = make_repo(self.tmp, {
            "package.json": '{"scripts": {"test": "vitest"}}',
            "src/index.js": "export const a = 1;\n",
        })
        self.assertGreaterEqual(self._check(root, "test-command").earned, 10)

    def test_lockfile_and_ci_are_worth_points(self):
        root = make_repo(self.tmp, {
            "README.md": "# x\n",
            "helper.py": "x = 1\n",
            "requirements.txt": "requests==2.31.0\n",
        })
        self.assertEqual(self._check(root, "lockfile").earned, 0,
                         "a project with dependencies and no lockfile must lose points")
        write(root, "poetry.lock", "")
        write(root, ".github/workflows/ci.yml", "jobs: {t: {steps: [{run: pytest}]}}\n")
        self.assertEqual(self._check(root, "lockfile").earned, 7)
        self.assertEqual(self._check(root, "ci-config").earned, 6)

    def test_zero_dependency_project_needs_no_lockfile(self):
        root = make_repo(self.tmp, {
            "README.md": "# x\n",
            "tool.py": "x = 1\n",
            "pyproject.toml": '[project]\nname = "x"\ndependencies = []\n',
        })
        check = self._check(root, "lockfile")
        self.assertEqual(check.earned, check.max_points)
        self.assertIn("no dependencies", check.evidence)

    def test_small_flat_repo_is_a_legitimate_layout(self):
        root = make_repo(self.tmp, {"tool.py": "x = 1\n", "README.md": "# x\n"})
        self.assertEqual(self._check(root, "source-layout").earned, 7)

    def test_giant_files_are_penalised_and_scaled(self):
        big = "".join(f"a{i} = {i}\n" for i in range(2000))
        root = make_repo(self.tmp, {"huge.py": big, "small.py": "x = 1\n", "README.md": "# x\n"})
        giant = self._check(root, "no-giant-files")
        self.assertLess(giant.earned, giant.max_points)
        self.assertIn("1,500", giant.evidence + giant.why)

    def test_strict_tsconfig_is_required_for_full_marks(self):
        loose = make_repo(self.tmp, {"tsconfig.json": '{"compilerOptions": {}}',
                                     "src/index.ts": "export {};\n"})
        self.assertLess(self._check(loose, "type-checking").earned, 4)
        tmp2 = Path(tempfile.mkdtemp())
        try:
            strict = make_repo(tmp2, {"tsconfig.json": '{"compilerOptions": {"strict": true}}',
                                      "src/index.ts": "export {};\n"})
            self.assertEqual(self._check(strict, "type-checking").earned, 4)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

    def test_build_output_in_tree_is_penalised(self):
        root = make_repo(self.tmp, {"dist/bundle.js": "// built\n", "src/index.ts": "export {};\n"})
        self.assertEqual(self._check(root, "clean-tree").earned, 0)
        write(root, ".gitignore", "dist/\n")
        self.assertEqual(self._check(root, "clean-tree").earned, 5)

    def test_every_failing_check_suggests_a_fix(self):
        root = make_repo(self.tmp, {"README.md": "# nothing\n"})
        audit = ar.audit_repo(root)
        for c in audit.all_checks():
            if c.status == "fail" and c.id not in ("tests-present",):
                self.assertTrue(c.fix, f"{c.id} fails but suggests no fix")


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = make_repo(self.tmp, GOOD_REPO)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ar.main(list(args))
        return code, buf.getvalue()

    def test_json_output(self):
        code, out = self.run_cli(str(self.root), "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["tool"], "agent-ready")
        self.assertIn("score", data)
        self.assertIn("grade", data)
        self.assertEqual(len(data["categories"]), 4)
        self.assertTrue(data["categories"][0]["checks"][0]["evidence"])
        self.assertIsInstance(data["top_fixes"], list)
        for cat in data["categories"]:
            for c in cat["checks"]:
                self.assertIn(c["status"], ("pass", "warn", "fail", "skip"))
                self.assertTrue(c["why"], "every check must explain why it matters")

    def test_badge_is_valid_svg_and_shows_the_grade(self):
        out_path = self.tmp / "badge.svg"
        code, _ = self.run_cli(str(self.root), "--badge", str(out_path), "--json")
        self.assertEqual(code, 0)
        tree = ET.parse(out_path)
        root_el = tree.getroot()
        self.assertTrue(root_el.get("width"))
        texts = [e.text for e in root_el.iter("{http://www.w3.org/2000/svg}text")]
        self.assertIn("agent ready", texts)
        self.assertTrue(any("/100" in (t or "") for t in texts))

    def test_markdown_report(self):
        out_path = self.tmp / "report.md"
        code, _ = self.run_cli(str(self.root), "--md", str(out_path), "--json")
        self.assertEqual(code, 0)
        text = out_path.read_text(encoding="utf-8")
        self.assertIn("# Agent readiness report", text)
        self.assertIn("What this measures", text)
        self.assertIn("A+", text)

    def test_report_lists_fixes_for_an_imperfect_repo(self):
        scratch = Path(tempfile.mkdtemp())
        try:
            broken = make_repo(scratch, BAD_REPO)
            out_path = self.tmp / "broken.md"
            code, _ = self.run_cli(str(broken), "--md", str(out_path), "--json")
            self.assertEqual(code, 0)
            self.assertIn("Top fixes", out_path.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_a_perfect_repo_has_no_fixes(self):
        audit = ar.audit_repo(self.root)
        self.assertEqual(audit.score, 100.0)
        self.assertEqual(audit.top_fixes(), [])

    def test_rules_prints_the_rubric(self):
        code, out = self.run_cli("--rules")
        self.assertEqual(code, 0)
        self.assertIn("100 points", out)
        self.assertIn("Grades", out)

    def test_fail_under_gates_ci(self):
        code, _ = self.run_cli(str(self.root), "--fail-under", "10", "--json")
        self.assertEqual(code, 0)
        # the same fixture with its instructions removed must fail the gate
        stripped = make_repo(Path(tempfile.mkdtemp()), {"main.py": "print(1)\n"})
        try:
            code, _ = self.run_cli(str(stripped), "--fail-under", "60", "--json")
            self.assertEqual(code, 1)
        finally:
            shutil.rmtree(stripped.parent, ignore_errors=True)

    def test_missing_directory_exits_two(self):
        code, _ = self.run_cli(str(self.tmp / "nope"), "--json")
        self.assertEqual(code, 2)


class InitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_writes_a_usable_agents_md_and_raises_the_score(self):
        root = make_repo(self.tmp, {
            "pyproject.toml": '[project]\nname = "demo"\ndescription = "A tiny demo library."\n',
            "README.md": "# demo\n\nA tiny demo library for tests.\n\n```bash\npip install -e .\npytest\n```\n",
            "main.py": "if __name__ == '__main__':\n    print('hi')\n",
            "tests/test_demo.py": "def test_x(): pass\n",
        })
        before = ar.audit_repo(root).score
        buf = io.StringIO()
        with redirect_stdout(buf):
            ar.main([str(root), "--init", "--json"])
        agents = root / "AGENTS.md"
        self.assertTrue(agents.exists(), "AGENTS.md should be created")
        text = agents.read_text(encoding="utf-8")
        self.assertIn("## Commands", text)
        self.assertIn("pytest", text)
        self.assertIn("A tiny demo library", text)
        self.assertNotIn("You join a project", text)
        after = ar.audit_repo(root).score
        self.assertGreater(after, before, "generating AGENTS.md must improve the score")

    def test_init_never_overwrites_existing_instructions(self):
        root = make_repo(self.tmp, {"AGENTS.md": "# mine\n\nkeep me\n", "main.py": "x = 1\n"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            ar.main([str(root), "--init", "--json"])
        self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), "# mine\n\nkeep me\n")

    def test_tagline_prefers_manifest_description(self):
        root = make_repo(self.tmp, {
            "package.json": '{"description": "Manifest tagline wins"}',
            "README.md": "# x\n\nSome other sentence that is long enough to be picked.\n",
        })
        audit = ar.audit_repo(root)
        repo = ar.scan_repo(root)
        self.assertIn("Manifest tagline wins", ar.generate_agents_md(repo, audit))


if __name__ == "__main__":
    unittest.main(verbosity=2)
