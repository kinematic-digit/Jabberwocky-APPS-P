from __future__ import annotations

import csv
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from software.jw_probe.jwp_event_tracker import JWPEventTracker
from software import jws_installer
from software import curses_ui


class FakeGCode:
    def __init__(self):
        self.commands = {}
        self.messages = []

    def register_command(self, name, callback, desc=""):
        self.commands[name] = callback

    def respond_info(self, message):
        self.messages.append(message)


class FakePins:
    def __init__(self):
        self.shared_pins = []

    def allow_multi_use_pin(self, pin):
        self.shared_pins.append(pin)


class FakeButtons:
    def __init__(self):
        self.pin_sets = []
        self.callback = None

    def register_buttons(self, pins, callback):
        self.pin_sets.append(pins)
        self.callback = callback


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGCode()
        self.pins = FakePins()
        self.buttons = FakeButtons()

    def lookup_object(self, name):
        if name == "gcode":
            return self.gcode
        if name == "pins":
            return self.pins
        raise AssertionError(f"Unexpected printer object lookup: {name}")

    def load_object(self, _config, name):
        if name != "buttons":
            raise AssertionError(f"Unexpected Klipper module load: {name}")
        return self.buttons


class FakeConfig:
    def __init__(self, printer, **values):
        self.printer = printer
        self.values = values

    def get_printer(self):
        return self.printer

    def get(self, name, default=None):
        return self.values.get(name, default)


class FakeGcmd:
    def __init__(self, label="MANUAL_MARK"):
        self.label = label
        self.messages = []

    def get_str(self, _name, default=None):
        return self.label if self.label is not None else default

    def respond_info(self, message):
        self.messages.append(message)

    def error(self, message):
        raise RuntimeError(message)


class JWPEventTrackerTests(unittest.TestCase):
    def make_tracker(self, telemetry_file=None):
        printer = FakePrinter()
        values = {"pin": "^!nhk:gpio10"}
        if telemetry_file is not None:
            values["telemetry_file"] = str(telemetry_file)
        tracker = JWPEventTracker(FakeConfig(printer, **values))
        return tracker, printer

    def test_captures_transitions_without_executing_printer_responses(self):
        tracker, printer = self.make_tracker()
        now = time.monotonic()

        tracker.button_callback(now, 0.0)
        tracker.button_callback(now + 0.2, 1.0)

        self.assertEqual(tracker.probe_state, "retracted")
        self.assertEqual(tracker.event_count, 2)
        self.assertEqual(tracker.events_log[0]["state"], "deployed")
        self.assertAlmostEqual(tracker.events_log[1]["pulse_duration"], 0.2)
        self.assertFalse(tracker.events_log[0]["response_executed"])
        self.assertEqual(printer.pins.shared_pins, ["nhk:gpio10"])
        self.assertEqual(printer.buttons.pin_sets, [["^!nhk:gpio10"]])
        self.assertNotIn("JWP_SET_HUNTING", printer.gcode.commands)

        status = FakeGcmd()
        tracker.cmd_event_status(status)
        self.assertIn("Automatic Response: disabled", status.messages[0])

        history = FakeGcmd()
        tracker.cmd_event_log(history)
        self.assertIn("VOLATILE, 30 SECONDS", history.messages[0])
        self.assertIn("response=not-executed", history.messages[0])

    def test_invalid_sensor_state_remains_unknown_and_history_expires(self):
        tracker, _printer = self.make_tracker()
        now = time.monotonic()
        tracker.button_callback(now, None)

        self.assertEqual(tracker.probe_state, "unknown")
        self.assertEqual(tracker.events_log[0]["state"], "unknown")
        self.assertIsNone(tracker.last_trigger_time)

        tracker.button_callback(now + 31.0, 0)
        self.assertEqual(tracker.event_count, 2)
        self.assertEqual(len(tracker.events_log), 1)
        self.assertEqual(tracker.events_log[0]["state"], "deployed")

    def test_commit_persists_events_and_manual_mark(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            telemetry_file = Path(temp_dir) / "jwp_calibration_profile.csv"
            tracker, _printer = self.make_tracker(telemetry_file)
            now = time.monotonic()
            tracker.button_callback(now, 0)
            tracker.button_callback(now + 0.2, 1)

            gcmd = FakeGcmd(label="test mark")
            tracker.cmd_commit_post_mortem(gcmd)

            with telemetry_file.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][1:3], ["", ""])
            self.assertEqual(rows[0][5:], ["PROBE_EVENT", "DETECTED_DEPLOYED_NO_RESPONSE"])
            self.assertEqual(rows[1][5:], ["PROBE_EVENT", "DETECTED_RETRACTED_NO_RESPONSE"])
            self.assertEqual(rows[2][5:], ["USER_MARK", "test mark"])
            self.assertTrue(all(event["telemetry_committed"] for event in tracker.events_log))
            self.assertIn("wrote 2 captured events", gcmd.messages[0])

            tracker.cmd_commit_post_mortem(FakeGcmd())
            with telemetry_file.open(encoding="utf-8", newline="") as stream:
                self.assertEqual(len(list(csv.reader(stream))), 4)

    def test_telemetry_write_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            telemetry_file = Path(temp_dir) / "missing" / "history.csv"
            tracker, _printer = self.make_tracker(telemetry_file)

            with self.assertRaisesRegex(RuntimeError, "JWP telemetry write failed"):
                tracker.cmd_commit_post_mortem(FakeGcmd())


class JWPIntegrationTests(unittest.TestCase):
    def test_curses_module_imports_the_project_installer(self):
        self.assertIs(curses_ui.jws_installer, jws_installer)

    def test_entry_includes_exist_and_tracker_uses_existing_probe_pin_once(self):
        config_dir = REPO_ROOT / "config" / "jabberwockyprobe"
        entry = (config_dir / "jwprobe_entry.cfg").read_text(encoding="utf-8")
        includes = re.findall(r"^\s*\[include\s+([^\]]+)\]", entry, re.MULTILINE)
        self.assertTrue(includes)
        for include in includes:
            self.assertTrue((config_dir / include).is_file(), include)

        hardware = (config_dir / "jwprobe_hardware.cfg").read_text(encoding="utf-8")
        self.assertEqual(hardware.count("[jwp_event_tracker]"), 1)
        self.assertNotIn("[jwp_probe_accel_test]", hardware)
        self.assertIn("[jwp_event_tracker]\npin: ^!nhk:gpio10", hardware)
        self.assertEqual(hardware.count("pin: ^!nhk:gpio10"), 2)

    def test_installer_deploys_tracker_only_when_jwp_is_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            extras = root / "klipper" / "klippy" / "extras"
            (config_dir / "jabberwockyprobe").mkdir(parents=True)
            (config_dir / "jabberwockyprobe" / "jwprobe_entry.cfg").touch()
            extras.mkdir(parents=True)

            with (
                patch.object(jws_installer, "CONFIG_DIR", str(config_dir)),
                patch.object(jws_installer, "_klipper_extras_dir", return_value=str(extras)),
            ):
                self.assertTrue(jws_installer._deploy_jwp_event_tracker())

            deployed = extras / "jwp_event_tracker.py"
            source = REPO_ROOT / "software" / "jw_probe" / "jwp_event_tracker.py"
            self.assertEqual(deployed.read_bytes(), source.read_bytes())

    def test_installer_reports_missing_klipper_extras_for_active_jwp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            entry = config_dir / "jabberwockyprobe" / "jwprobe_entry.cfg"
            entry.parent.mkdir(parents=True)
            entry.touch()

            with (
                patch.object(jws_installer, "CONFIG_DIR", str(config_dir)),
                patch.object(
                    jws_installer, "_klipper_extras_dir",
                    return_value=str(Path(temp_dir) / "missing-extras"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "Klipper extras were not found"):
                    jws_installer._deploy_jwp_event_tracker()

    def test_installer_skips_tracker_when_jwp_config_is_absent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(jws_installer, "CONFIG_DIR", temp_dir):
                self.assertFalse(jws_installer._deploy_jwp_event_tracker())


if __name__ == "__main__":
    unittest.main()
