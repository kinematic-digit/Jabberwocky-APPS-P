from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from software import curses_ui, jws_installer
from software.macro_manager.jws_core import run_sync
from software.macro_manager.macro_manager import normalize_component_key
from software.macro_manager.jws_operator import apply_in_place_masking


class JWPInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = root / "printer_data" / "config"
        self.config.mkdir(parents=True)
        self.printer_cfg = self.config / "printer.cfg"
        self.extras = root / "klipper" / "klippy" / "extras"
        self.extras.mkdir(parents=True)
        self.write_printer(native=("quad_gantry_level", "bed_mesh"))

        self.patches = [
            patch.object(jws_installer, "CONFIG_DIR", str(self.config)),
            patch.object(jws_installer, "PRINTER_CFG", str(self.printer_cfg)),
            patch.dict(os.environ, {"JWS_KLIPPER_DIR": str(root / "klipper")}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        jws_installer.INSTALL_NOTES.clear()
        self.addCleanup(jws_installer.INSTALL_NOTES.clear)

    def write_printer(self, native=()):
        parts = [
            "# user-owned printer configuration comment mentioning SAVE_CONFIG only\n",
            "[printer]\nkinematics: corexy\n",
        ]
        for section in native:
            parts.append(f"\n[{section}]\n")
            if section == "quad_gantry_level":
                parts.append("gantry_corners: 0,0\n    1,1\n")
            if section == "bed_mesh":
                parts.append("mesh_min: 10,10\nmesh_max: 200,200\n")
        parts.extend(("\n# retain this user comment\n", "#*# <---------------------- SAVE_CONFIG ---------------------->\n"))
        self.printer_cfg.write_text("".join(parts), encoding="utf-8")

    def run_install(self):
        return jws_installer.run_jwp_installation_pipeline()

    def test_fresh_install_adds_only_configured_wrappers_after_native_sections(self):
        original = self.printer_cfg.read_text(encoding="utf-8")
        self.assertTrue(self.run_install())
        updated = self.printer_cfg.read_text(encoding="utf-8")

        self.assertIn("# user-owned printer configuration comment", updated)
        self.assertIn("# retain this user comment", updated)
        self.assertLess(updated.index("[quad_gantry_level]"), updated.index(jws_installer.JWP_BLOCK_START))
        self.assertLess(updated.index("[bed_mesh]"), updated.index(jws_installer.JWP_BLOCK_START))
        self.assertIn("[include jabberwockyprobe/jwprobe_entry.cfg]", updated)
        self.assertIn("[include jabberwockyprobe/jwprobe_qgl.cfg]", updated)
        self.assertIn("[include jabberwockyprobe/jwprobe_bed_mesh.cfg]", updated)
        self.assertEqual(updated.count("[include jabberwockyprobe/jwprobe_qgl.cfg]"), 1)
        self.assertEqual(updated.count("[include jabberwockyprobe/jwprobe_bed_mesh.cfg]"), 1)
        self.assertNotEqual(updated, original)
        self.assertTrue((self.config / "jwprobe_runtime_vars.cfg").is_file())
        self.assertEqual(
            (self.config / "jwprobe_runtime_vars.cfg").read_bytes(),
            b"[Variables]\n",
        )
        package = self.config / "jabberwockyprobe"
        self.assertFalse((package / "jwprobe_vars.cfg").exists())
        self.assertTrue((package / "jwprobe_hardware.cfg").is_file())
        hardware = (package / "jwprobe_hardware.cfg").read_text(encoding="utf-8")
        self.assertIn("[jwp_event_tracker]", hardware)
        self.assertIn("pin: ^!nhk:gpio10", hardware)
        self.assertTrue((self.extras / "jwp_event_tracker.py").is_file())
        backups = list((self.config / "jabberwocky_quarantine").glob("jwp_install_*"))
        self.assertTrue(any((backup / "printer.cfg").read_text() == original for backup in backups))

    def test_qgl_bed_mesh_or_neither_are_selected_from_native_sections(self):
        cases = (
            (("quad_gantry_level",), ("jwprobe_qgl.cfg",)),
            (("bed_mesh",), ("jwprobe_bed_mesh.cfg",)),
            ((), ()),
        )
        for native, expected in cases:
            with self.subTest(native=native):
                self.tearDown()
                self.setUp()
                self.write_printer(native)
                self.run_install()
                content = self.printer_cfg.read_text(encoding="utf-8")
                self.assertIn("[include jabberwockyprobe/jwprobe_entry.cfg]", content)
                for wrapper in ("jwprobe_qgl.cfg", "jwprobe_bed_mesh.cfg"):
                    expected_line = f"[include jabberwockyprobe/{wrapper}]"
                    self.assertEqual(expected_line in content, wrapper in expected)

    def test_repeat_install_is_idempotent_and_preserves_user_files_and_runtime_bytes(self):
        self.run_install()
        package = self.config / "jabberwockyprobe"
        hardware = package / "jwprobe_hardware.cfg"
        globals_file = package / "jwprobe_globals.cfg"
        hardware_bytes = hardware.read_bytes()
        globals_bytes = globals_file.read_bytes()
        runtime = self.config / "jwprobe_runtime_vars.cfg"
        runtime_bytes = b"[Variables]\ncalibrated_value = 'verbatim'\n"
        runtime.write_bytes(runtime_bytes)
        hardware.write_bytes(hardware_bytes + b"\n# user hardware note\n")
        globals_file.write_bytes(globals_bytes + b"\n# user globals note\n")
        hardware_updated = hardware.read_bytes()
        globals_updated = globals_file.read_bytes()
        printer_updated = self.printer_cfg.read_bytes()

        self.run_install()

        self.assertEqual(runtime.read_bytes(), runtime_bytes)
        self.assertEqual(hardware.read_bytes(), hardware_updated)
        self.assertEqual(globals_file.read_bytes(), globals_updated)
        self.assertEqual(self.printer_cfg.read_bytes(), printer_updated)

    def test_missing_tracker_registration_is_added_with_the_existing_probe_pin(self):
        self.run_install()
        hardware = self.config / "jabberwockyprobe" / "jwprobe_hardware.cfg"
        original = hardware.read_text(encoding="utf-8")
        without_tracker = jws_installer._without_section(original, "jwp_event_tracker")
        customized = without_tracker.replace("^!nhk:gpio10", "^!fixture:gpio9")
        hardware.write_text(customized, encoding="utf-8")

        self.run_install()

        updated = hardware.read_text(encoding="utf-8")
        self.assertIn("[jwp_event_tracker]", updated)
        self.assertIn("pin: ^!fixture:gpio9", updated)
        self.assertIn("# JABBERWOCKY PROBE 2.0 — HARDWARE BINDINGS", updated)
        self.assertEqual(updated.count("[jwp_event_tracker]"), 1)

    def test_legacy_only_data_migrates_with_recovery_copy_and_repeats_safely(self):
        package = self.config / "jabberwockyprobe"
        package.mkdir()
        entry = REPO_ROOT / "software" / "jw_probe" / "jwprobe_entry.cfg"
        entry_text = entry.read_text(encoding="utf-8").replace(
            "~/printer_data/config/jwprobe_runtime_vars.cfg",
            "~/printer_data/config/jabberwockyprobe/jwprobe_vars.cfg",
        )
        (package / "jwprobe_entry.cfg").write_text(entry_text, encoding="utf-8")
        legacy = package / "jwprobe_vars.cfg"
        data = b"[Variables]\nuser_calibration = 0.3875\n"
        legacy.write_bytes(data)

        self.run_install()

        canonical = self.config / "jwprobe_runtime_vars.cfg"
        marker = self.config / ".jwprobe_runtime_vars.migration"
        self.assertEqual(canonical.read_bytes(), data)
        self.assertEqual(legacy.read_bytes(), data)
        self.assertIn(hashlib.sha256(data).hexdigest(), marker.read_text())
        self.assertEqual(
            jws_installer._save_variables_filename(
                (package / "jwprobe_entry.cfg").read_text(encoding="utf-8")
            ),
            "~/printer_data/config/jwprobe_runtime_vars.cfg",
        )
        newer = data + b"saved_after_migration = True\n"
        canonical.write_bytes(newer)
        self.run_install()
        self.assertEqual(canonical.read_bytes(), newer)
        self.assertEqual(legacy.read_bytes(), data)

    def test_conflicting_runtime_files_stop_without_overwriting_either(self):
        package = self.config / "jabberwockyprobe"
        package.mkdir()
        entry = package / "jwprobe_entry.cfg"
        entry.write_text(
            "[save_variables]\nfilename: ~/printer_data/config/jabberwockyprobe/jwprobe_vars.cfg\n",
            encoding="utf-8",
        )
        canonical = self.config / "jwprobe_runtime_vars.cfg"
        legacy = package / "jwprobe_vars.cfg"
        canonical_bytes = b"[Variables]\nvalue = 1\n"
        legacy_bytes = b"[Variables]\nvalue = 2\n"
        canonical.write_bytes(canonical_bytes)
        legacy.write_bytes(legacy_bytes)
        printer_bytes = self.printer_cfg.read_bytes()
        entry_bytes = entry.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "conflict"):
            self.run_install()

        self.assertEqual(canonical.read_bytes(), canonical_bytes)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)
        self.assertEqual(entry.read_bytes(), entry_bytes)
        self.assertEqual(self.printer_cfg.read_bytes(), printer_bytes)

    def test_custom_persistence_path_stops_before_changes(self):
        package = self.config / "jabberwockyprobe"
        package.mkdir()
        entry = package / "jwprobe_entry.cfg"
        entry.write_text("[save_variables]\nfilename: ~/custom/vars.cfg\n", encoding="utf-8")
        before = self.printer_cfg.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "custom save_variables path"):
            self.run_install()

        self.assertEqual(self.printer_cfg.read_bytes(), before)
        self.assertFalse((self.config / "jwprobe_runtime_vars.cfg").exists())

    def test_user_override_and_third_party_include_stop_installation(self):
        self.write_printer(("quad_gantry_level", "bed_mesh"))
        self.printer_cfg.write_text(
            self.printer_cfg.read_text(encoding="utf-8")
            + "\n[gcode_macro QUAD_GANTRY_LEVEL]\ngcode:\n    RESPOND MSG=custom\n",
            encoding="utf-8",
        )
        before = self.printer_cfg.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Conflicting user or third-party wrapper"):
            self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)

        self.write_printer(("quad_gantry_level",))
        self.printer_cfg.write_text(
            self.printer_cfg.read_text(encoding="utf-8")
            + "\n[include jabberwockyprobe/jwprobe_qgl.cfg]\n",
            encoding="utf-8",
        )
        before = self.printer_cfg.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "outside the installer-owned block"):
            self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)

    def test_third_party_rename_existing_aliases_stop_before_install_changes(self):
        aliases = (
            ("_JWP_NATIVE_QUAD_GANTRY_LEVEL", "quad_gantry_level"),
            ("_JWP_NATIVE_BED_MESH_CALIBRATE", "bed_mesh"),
        )
        for alias, native_section in aliases:
            with self.subTest(alias=alias):
                self.tearDown()
                self.setUp()
                self.write_printer((native_section,))
                self.printer_cfg.write_text(
                    self.printer_cfg.read_text(encoding="utf-8")
                    + f"\n[gcode_macro THIRD_PARTY]\nrename_existing: {alias}\ngcode:\n    RESPOND MSG=custom\n",
                    encoding="utf-8",
                )
                package = self.config / "jabberwockyprobe"
                package.mkdir()
                package_sentinel = package / "preserve.cfg"
                package_sentinel.write_bytes(b"user package data\n")
                runtime = self.config / "jwprobe_runtime_vars.cfg"
                runtime.write_bytes(b"[Variables]\nuser_value = 1\n")
                tracker = self.extras / "jwp_event_tracker.py"
                tracker.write_bytes(b"user tracker data\n")
                quarantine = self.config / "jabberwocky_quarantine"
                quarantine_sentinel = quarantine / "prior" / "printer.cfg"
                quarantine_sentinel.parent.mkdir(parents=True)
                quarantine_sentinel.write_bytes(b"prior recovery data\n")

                def tree_snapshot(root):
                    return {
                        path.relative_to(root): (
                            "directory" if path.is_dir() else path.read_bytes()
                        )
                        for path in (root, *root.rglob("*"))
                    }

                config_before = tree_snapshot(self.config)
                extras_before = tree_snapshot(self.extras)

                with self.assertRaisesRegex(RuntimeError, "Conflicting rename_existing alias"):
                    self.run_install()

                self.assertEqual(tree_snapshot(self.config), config_before)
                self.assertEqual(tree_snapshot(self.extras), extras_before)
                self.assertEqual(self.printer_cfg.read_bytes(), config_before[Path("printer.cfg")])
                self.assertEqual(package_sentinel.read_bytes(), b"user package data\n")
                self.assertEqual(runtime.read_bytes(), b"[Variables]\nuser_value = 1\n")
                self.assertEqual(tracker.read_bytes(), b"user tracker data\n")
                self.assertEqual(
                    quarantine_sentinel.read_bytes(), b"prior recovery data\n"
                )

    def test_malformed_markers_stop_without_rewriting_printer_cfg(self):
        self.printer_cfg.write_text(
            self.printer_cfg.read_text(encoding="utf-8")
            + f"\n{jws_installer.JWP_BLOCK_START}\n",
            encoding="utf-8",
        )
        before = self.printer_cfg.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "markers are duplicated or malformed"):
            self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)

    def test_duplicate_markers_stop_without_rewriting_printer_cfg(self):
        self.printer_cfg.write_text(
            self.printer_cfg.read_text(encoding="utf-8")
            + f"\n{jws_installer.JWP_BLOCK_START}\n{jws_installer.JWP_BLOCK_END}\n"
            + f"\n{jws_installer.JWP_BLOCK_START}\n{jws_installer.JWP_BLOCK_END}\n",
            encoding="utf-8",
        )
        before = self.printer_cfg.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "markers are duplicated or malformed"):
            self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)

    def test_backup_and_atomic_replace_failures_leave_printer_cfg_recoverable(self):
        before = self.printer_cfg.read_bytes()
        with patch.object(jws_installer.shutil, "copy2", side_effect=OSError("backup failed")):
            with self.assertRaisesRegex(RuntimeError, "JWP backup failed"):
                self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)
        self.assertFalse((self.config / "jwprobe_runtime_vars.cfg").exists())

        real_replace = os.replace

        def fail_printer_replace(source, destination):
            if Path(destination) == self.printer_cfg:
                raise OSError("atomic replacement failed")
            return real_replace(source, destination)

        with patch.object(jws_installer.os, "replace", side_effect=fail_printer_replace):
            with self.assertRaisesRegex(OSError, "atomic replacement failed"):
                self.run_install()
        self.assertEqual(self.printer_cfg.read_bytes(), before)
        backups = list((self.config / "jabberwocky_quarantine").glob("jwp_install_*"))
        self.assertTrue(backups)
        self.assertTrue(any((backup / "printer.cfg").is_file() for backup in backups))

    def test_curses_exposes_and_runs_jwp_action(self):
        ui = curses_ui.JabberwockyTerminalUI()
        self.assertEqual(ui.options[2][0], "Install / Update JWP")
        ui.selections = [False, False, True]
        with patch.object(jws_installer, "run_jwp_installation_pipeline") as install:
            self.assertIsNone(ui.run_pipeline(None))
        install.assert_called_once()
        with patch.object(
            jws_installer, "run_jwp_installation_pipeline",
            side_effect=RuntimeError("conflict reported"),
        ):
            self.assertEqual(ui.run_pipeline(None), "conflict reported")


class MacroManagerJWPProtectionTests(unittest.TestCase):
    def test_sync_cannot_disable_or_mask_the_installer_owned_wrapper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "jabberwockyprobe"
            package.mkdir()
            printer = root / "printer.cfg"
            printer.write_text(
                "[printer]\nkinematics: corexy\n"
                f"{jws_installer.JWP_BLOCK_START}\n"
                "[include jabberwockyprobe/jwprobe_qgl.cfg]\n"
                f"{jws_installer.JWP_BLOCK_END}\n",
                encoding="utf-8",
            )
            wrapper = package / "jwprobe_qgl.cfg"
            original = (
                "[gcode_macro QUAD_GANTRY_LEVEL]\n"
                "rename_existing: _JWP_NATIVE_QUAD_GANTRY_LEVEL\n"
                "gcode:\n    RESPOND MSG=JWP\n"
            )
            wrapper.write_text(original, encoding="utf-8")
            manifest = {
                normalize_component_key("file", "jabberwockyprobe/jwprobe_qgl.cfg"): 0,
                normalize_component_key("macro", "QUAD_GANTRY_LEVEL", "jwprobe_qgl.cfg"): 0,
            }

            self.assertEqual(run_sync(root, printer, manifest), [])
            self.assertIn(
                "[include jabberwockyprobe/jwprobe_qgl.cfg]",
                printer.read_text(encoding="utf-8"),
            )
            self.assertEqual(wrapper.read_text(encoding="utf-8"), original)

    def test_macro_manager_cannot_mask_jwp_installer_owned_includes_or_wrappers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            printer = root / "printer.cfg"
            printer.write_text(
                f"{jws_installer.JWP_BLOCK_START}\n"
                "[include jabberwockyprobe/jwprobe_qgl.cfg]\n"
                f"{jws_installer.JWP_BLOCK_END}\n",
                encoding="utf-8",
            )
            manifest = {
                "file_jabberwockyprobe%2Fjwprobe_qgl_cfg": 0,
            }
            self.assertFalse(
                apply_in_place_masking(
                    printer, manifest, "file",
                    "jabberwockyprobe/jwprobe_qgl.cfg",
                    config_dir=root,
                )
            )
            self.assertIn("[include jabberwockyprobe/jwprobe_qgl.cfg]", printer.read_text())

            wrapper = root / "jabberwockyprobe" / "jwprobe_qgl.cfg"
            wrapper.parent.mkdir()
            original = "[gcode_macro QUAD_GANTRY_LEVEL]\nrename_existing: _JWP_NATIVE_QUAD_GANTRY_LEVEL\ngcode:\n    RESPOND MSG=JWP\n"
            wrapper.write_text(original, encoding="utf-8")
            self.assertFalse(
                apply_in_place_masking(
                    wrapper, {"macro_quad_gantry_level": 0},
                    "macro", "QUAD_GANTRY_LEVEL", config_dir=root,
                )
            )
            self.assertEqual(wrapper.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
