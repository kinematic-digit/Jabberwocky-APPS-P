# =====================================================================
# JABBERWOCKY APPS — REPORT FEATURE TESTS
# Location: tests/test_report_feature.py
# =====================================================================

import contextlib
import curses
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from software import curses_ui
from software.macro_manager import jws_core


class FakeScreen:
    """Minimal curses screen for deterministic UI tests."""

    def __init__(self, keys, height=24, width=100):
        self.keys = list(keys)
        self.height = height
        self.width = width
        self.drawn_text = []

    def getmaxyx(self):
        return self.height, self.width

    def clear(self):
        pass

    def refresh(self):
        pass

    def addstr(self, y, x, text, attr=0):
        self.drawn_text.append((y, x, str(text), attr))

    def getch(self):
        if not self.keys:
            raise AssertionError(
                "UI requested an unexpected additional key"
            )
        return self.keys.pop(0)


def snapshot_files(directory):
    """Capture existing file paths and bytes without following directories."""
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def run_report_cli(*args):
    """Run the real report entry point and capture both output streams."""
    stdout = io.StringIO()
    stderr = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            result = jws_core.main(list(args))

    return result, stdout.getvalue(), stderr.getvalue()


class TestReportMenuIntegration(unittest.TestCase):
    def test_enter_on_report_opens_report_without_changing_selections(self):
        ui = curses_ui.JabberwockyTerminalUI()
        screen = FakeScreen(
            [
                curses.KEY_DOWN,
                curses.KEY_DOWN,
                curses.KEY_DOWN,
                ord("\n"),
                ord("q"),
            ]
        )
        original_selections = list(ui.selections)

        with patch.object(curses, "curs_set"):
            with patch.object(ui, "run_report") as report:
                ui.draw_action_menu(screen)

        report.assert_called_once_with(screen)
        self.assertEqual(ui.selections, original_selections)

    def test_report_is_present_and_available(self):
        ui = curses_ui.JabberwockyTerminalUI()

        self.assertEqual(ui.options[3][0], "Report")
        self.assertTrue(ui.options[3][2])


class TestReportScreen(unittest.TestCase):
    def test_viewing_report_does_not_save_or_change_config_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)
            (config_dir / "printer.cfg").write_text(
                "[mcu]\nserial: /dev/null\n",
                encoding="utf-8",
            )
            before = snapshot_files(config_dir)

            screen = FakeScreen([ord("q")])
            completed = type(
                "Completed",
                (),
                {
                    "stdout": "Diagnostic report test output\n",
                    "returncode": 0,
                },
            )()

            with patch.dict(
                os.environ,
                {"PRINTER_CONFIG_DIR": str(config_dir)},
            ):
                with patch(
                    "subprocess.run",
                    return_value=completed,
                ) as run:
                    curses_ui.JabberwockyTerminalUI().run_report(screen)

            self.assertEqual(snapshot_files(config_dir), before)
            run.assert_called_once()

            command = run.call_args.args[0]
            self.assertIn("--report", command)
            self.assertIn("--config-dir", command)
            self.assertNotIn("--sync", command)

    def test_nonzero_report_exit_is_displayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)
            screen = FakeScreen([ord("q")])
            completed = type(
                "Completed",
                (),
                {
                    "stdout": "Diagnostic report failed\n",
                    "returncode": 7,
                },
            )()

            with patch.dict(
                os.environ,
                {"PRINTER_CONFIG_DIR": str(config_dir)},
            ):
                with patch(
                    "subprocess.run",
                    return_value=completed,
                ):
                    curses_ui.JabberwockyTerminalUI().run_report(screen)

            displayed = "\n".join(
                text for _y, _x, text, _attr in screen.drawn_text
            )
            self.assertIn("Report command exited with status 7.", displayed)
        
    def test_long_report_lines_indent_continuation_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)
            report_text = (
                "    What to do: Delete the line, or "
                "restore/rename the file and re-enable it. "
                "Report only; no dashboard row is created.\n"
            )

            completed = type(
                "Completed",
                (),
                {
                    "stdout": report_text,
                    "returncode": 0,
                },
            )()

            screen = FakeScreen([ord("q")], width=42)

            with patch.dict(
                os.environ,
                {"PRINTER_CONFIG_DIR": str(config_dir)},
            ):
                with patch(
                    "subprocess.run",
                    return_value=completed,
                ):
                    curses_ui.JabberwockyTerminalUI().run_report(screen)

            report_lines = [
                text
                for _y, x, text, _attr in screen.drawn_text
                if x == 2
            ]

            self.assertTrue(
                any(line.startswith("        ") for line in report_lines),
                f"Expected indented continuation lines: {report_lines!r}",
            )
    
    def test_save_uses_unused_filename_and_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)
            (config_dir / "printer.cfg").write_text(
                "# test configuration\n",
                encoding="utf-8",
            )

            timestamp = "20261011_120000"
            original_report = (
                config_dir / f"jws_diagnostic_report_{timestamp}.txt"
            )
            original_contents = "Existing report must remain untouched.\n"
            original_report.write_text(
                original_contents,
                encoding="utf-8",
            )

            report_text = "Diagnostic report test output\n"
            completed = type(
                "Completed",
                (),
                {
                    "stdout": report_text,
                    "returncode": 0,
                },
            )()

            # S saves; X dismisses the save result; Q returns to the menu.
            screen = FakeScreen([ord("s"), ord("x"), ord("q")])

            with patch.dict(
                os.environ,
                {"PRINTER_CONFIG_DIR": str(config_dir)},
            ):
                with patch(
                    "subprocess.run",
                    return_value=completed,
                ):
                    with patch.object(
                        curses_ui.time,
                        "strftime",
                        return_value=timestamp,
                    ):
                        curses_ui.JabberwockyTerminalUI().run_report(screen)

            self.assertEqual(
                original_report.read_text(encoding="utf-8"),
                original_contents,
            )

            saved_report = (
                config_dir / f"jws_diagnostic_report_{timestamp}_1.txt"
            )
            self.assertTrue(saved_report.is_file())
            self.assertEqual(
                saved_report.read_text(encoding="utf-8"),
                report_text,
            )


class TestCoreReportReadOnly(unittest.TestCase):
    def test_real_report_does_not_modify_config_or_create_dashboard(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)
            (config_dir / "printer.cfg").write_text(
                "[mcu]\nserial: /dev/null\n",
                encoding="utf-8",
            )
            dashboard = config_dir / "jwt_macro_manager.conf"
            before = snapshot_files(config_dir)

            result, stdout, stderr = run_report_cli(
                "--report",
                "--config-dir",
                str(config_dir),
            )

            self.assertEqual(result, 0, stderr)
            self.assertIn("(REPORT)", stdout)
            self.assertIn("Files in active tree:", stdout)
            self.assertEqual(snapshot_files(config_dir), before)
            self.assertFalse(dashboard.exists())

    def test_missing_printer_cfg_is_reported_instead_of_aborting(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)

            # A directory with the dashboard's name simulates an unusable
            # dashboard path. Report mode must not try to load or repair it.
            dashboard_path = config_dir / "jwt_macro_manager.conf"
            dashboard_path.mkdir()

            before = snapshot_files(config_dir)

            result, stdout, stderr = run_report_cli(
                "--report",
                "--config-dir",
                str(config_dir),
            )

            self.assertEqual(result, 0, stderr)
            self.assertIn("(REPORT)", stdout)
            self.assertIn("printer.cfg was not found", stdout)
            self.assertTrue(dashboard_path.is_dir())
            self.assertEqual(snapshot_files(config_dir), before)

    def test_normal_mode_still_errors_when_printer_cfg_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary)

            result, stdout, stderr = run_report_cli(
                "--config-dir",
                str(config_dir),
            )

            self.assertEqual(result, 1)
            self.assertIn("Master target config missing", stderr)
            self.assertNotIn("(REPORT)", stdout)
            self.assertEqual(snapshot_files(config_dir), {})


if __name__ == "__main__":
    unittest.main()

# EOF
