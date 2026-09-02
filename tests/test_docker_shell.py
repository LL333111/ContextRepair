import unittest

from contextrepair.tools.docker_shell import (
    _is_read_only_git_command,
    _network_safe_eval_script,
    _official_exit_code,
    _record_test_exit_code,
    _requires_reinstall_for_paths,
    _seedable_image_artifacts,
)


class DockerShellTests(unittest.TestCase):
    def test_extracts_last_official_test_exit_code(self):
        output = ">>>>> Test Exit Code: 1\nnoise\n>>>>> Test Exit Code: 0\n"
        self.assertEqual(_official_exit_code(output), 0)

    def test_missing_official_exit_code_is_an_error(self):
        self.assertEqual(_official_exit_code("test output without marker"), 2)

    def test_injects_exit_capture_before_end_marker(self):
        script = "pytest -q\n: '>>>>> End Test Output'\ngit checkout tests\n"
        patched = _record_test_exit_code(script)
        self.assertIn("contextrepair_test_exit_code=$?\n", patched)
        self.assertIn(
            ': \'>>>>> End Test Output\'\n'
            'echo ">>>>> Test Exit Code: ${contextrepair_test_exit_code}"\n',
            patched,
        )
        self.assertEqual(patched.count(">>>>> End Test Output"), 1)

    def test_optimizes_non_packaging_evaluation_setup(self):
        script = (
            "set -uxo pipefail\n"
            "git status\n"
            "git show\n"
            "git -c core.fileMode=false diff abc123\n"
            "python -m pip install -e .\n"
            "pytest -q\n"
        )
        patched = _network_safe_eval_script(script)
        self.assertIn("set -uo pipefail", patched)
        self.assertIn("omitted slow worktree status diagnostic", patched)
        self.assertIn("git show -s --oneline HEAD", patched)
        self.assertIn("omitted slow worktree diff diagnostic", patched)
        self.assertNotIn("core.fileMode=false diff", patched)
        self.assertIn('CONTEXTREPAIR_REINSTALL:-1', patched)
        self.assertNotIn("if git diff --quiet HEAD", patched)
        self.assertIn("reusing image-provided editable install", patched)
        self.assertIn("pip install --no-build-isolation -e .", patched)

    def test_reinstall_is_limited_to_packaging_or_compiled_changes(self):
        self.assertFalse(_requires_reinstall_for_paths(["django/db/models/query.py"]))
        self.assertTrue(_requires_reinstall_for_paths(["pyproject.toml"]))
        self.assertTrue(_requires_reinstall_for_paths(["requirements/test.txt"]))
        self.assertTrue(_requires_reinstall_for_paths(["src/extension.pyx"]))

    def test_routes_single_read_only_git_commands_to_host(self):
        self.assertTrue(_is_read_only_git_command("git diff -- src/example.py"))
        self.assertTrue(_is_read_only_git_command("git log --oneline -5"))
        self.assertFalse(_is_read_only_git_command("git checkout main"))
        self.assertFalse(_is_read_only_git_command("git diff && pytest -q"))

    def test_ignores_reproducible_image_build_artifacts(self):
        artifacts = [
            "build/lib/django/__init__.py",
            "Django.egg-info/PKG-INFO",
            ".eggs/cython.egg/Cython/Compiler/Main.py",
            "package/__pycache__/module.cpython-311.pyc",
            ".tox/py/lib/site-packages/example.py",
            "package/generated/runtime.dat",
            "package/extension.so",
        ]
        self.assertEqual(
            _seedable_image_artifacts(artifacts),
            ["package/generated/runtime.dat", "package/extension.so"],
        )


if __name__ == "__main__":
    unittest.main()
