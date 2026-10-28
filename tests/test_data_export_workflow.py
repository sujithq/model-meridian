from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from tests.helpers import ROOT


def bash_path() -> str | None:
    if os.name == "nt":
        git = shutil.which("git")
        if git is not None:
            candidate = Path(git).parent.parent / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
        return None
    return shutil.which("bash")


@unittest.skipUnless(bash_path(), "Bash is not installed")
class RefreshRetryTests(unittest.TestCase):
    def test_diagnostic_branches_do_not_publish_csv_changes(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "data-export.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("ref: ${{ github.ref }}", workflow)
        commit_step = workflow.split("      - name: Commit refreshed CSV\n", 1)[1]
        self.assertTrue(
            commit_step.startswith(
                "        if: github.ref == 'refs/heads/main' && !inputs.compare_viewports\n"
            )
        )
        upload_step = workflow.split("      - name: Upload export diagnostics\n", 1)[1]
        self.assertTrue(upload_step.startswith("        if: always()\n"))

    def test_viewport_comparison_only_writes_separate_snapshots(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "data-export.yml").read_text(
            encoding="utf-8"
        )
        comparison_step = workflow.split("      - name: Compare chart viewports\n", 1)[1]
        self.assertTrue(comparison_step.startswith("        if: inputs.compare_viewports\n"))
        body = comparison_step.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("ExportOptions(output_dir=output)", body)
        self.assertNotIn("output_path=", body)
        self.assertIn('("large", 2560, 1440)', body)
        self.assertIn('("ultrawide", 3840, 2160)', body)
        self.assertIn("default_points = source.extract_points()", body)
        self.assertIn("source._chart().scroll_into_view_if_needed()", body)
        export_step = workflow.split("      - name: Export source chart data to CSV\n", 1)[1]
        self.assertTrue(export_step.startswith("        if: ${{ !inputs.compare_viewports }}\n"))
        script = textwrap.dedent(body).split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        compile(script, "<viewport-comparison>", "exec")

    def test_refresh_explicitly_bypasses_the_retained_removal_guard(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "data-export.yml").read_text(
            encoding="utf-8"
        )
        step = workflow.split("      - name: Export source chart data to CSV\n", 1)[1]
        body = step.split("\n      - name:", 1)[0]
        self.assertIn("--allow-large-removals", body)

    def run_export_step(self, statuses: str) -> subprocess.CompletedProcess[str]:
        workflow = (ROOT / ".github" / "workflows" / "data-export.yml").read_text(
            encoding="utf-8"
        )
        step = workflow.split("      - name: Export source chart data to CSV\n", 1)[1]
        body = step.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
        script = textwrap.dedent(body)
        harness = """
set -e -o pipefail
calls=0
read -r -a statuses <<< "$TEST_STATUSES"
python() {
  calls=$((calls + 1))
  return "${statuses[$((calls - 1))]:-99}"
}
sleep() { echo "sleep=$1"; }
trap 'echo "calls=$calls"' EXIT
"""
        executable = bash_path()
        self.assertIsNotNone(executable)
        return subprocess.run(
            [executable, "-c", harness + script],
            env={**os.environ, "TEST_STATUSES": statuses},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_success_is_not_retried(self) -> None:
        result = self.run_export_step("0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("calls=1", result.stdout)
        self.assertNotIn("sleep=", result.stdout)

    def test_transient_failure_is_retried_once(self) -> None:
        result = self.run_export_step("75 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("calls=2", result.stdout)
        self.assertEqual(result.stdout.count("sleep=30"), 1)

    def test_persistent_transient_failure_stays_failed(self) -> None:
        result = self.run_export_step("75 75")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("calls=2", result.stdout)
        self.assertEqual(result.stdout.count("sleep=30"), 1)

    def test_structural_failure_is_not_retried(self) -> None:
        result = self.run_export_step("1")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("calls=1", result.stdout)
        self.assertNotIn("sleep=", result.stdout)

    def test_other_exit_statuses_are_preserved(self) -> None:
        result = self.run_export_step("2")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("calls=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
