from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from software import jws_installer
from software.jwp_build import JabberwockyCompiler


ENTRY_FILES = (
    REPO_ROOT / "jabberwockyprobe" / "jwprobe_entry.cfg",
    REPO_ROOT / "software" / "jw_probe" / "jwprobe_entry.cfg",
    REPO_ROOT / "config" / "jabberwockyprobe" / "jwprobe_entry.cfg",
)
CANONICAL = "~/printer_data/config/jwprobe_runtime_vars.cfg"
LEGACY = "~/printer_data/config/jabberwockyprobe/jwprobe_vars.cfg"
MANDATORY_INCLUDES = (
    "jwprobe_globals.cfg",
    "jwprobe_profile.cfg",
    "jwprobe_hardware.cfg",
    "jwprobe_logic.cfg",
    "jwprobe_homing.cfg",
    "jwprobe_onboarding.cfg",
    "jwprobe_autoz.cfg",
)


def active_includes(entry_text: str) -> list[str]:
    return re.findall(r"^\s*\[include\s+([^\]]+)\]", entry_text, re.MULTILINE)


class JWPEntryTests(unittest.TestCase):
    def test_all_entries_use_canonical_persistence_and_include_existing_files(self):
        for entry in ENTRY_FILES:
            with self.subTest(entry=entry):
                text = entry.read_text(encoding="utf-8")
                self.assertEqual(jws_installer._save_variables_filename(text), CANONICAL)
                includes = active_includes(text)
                self.assertEqual(includes[:len(MANDATORY_INCLUDES)], list(MANDATORY_INCLUDES))
                for include in includes:
                    self.assertTrue((entry.parent / include).is_file(), include)

    def test_active_machine_wrapper_choices_are_preserved_in_managed_block(self):
        entry = ENTRY_FILES[2].read_text(encoding="utf-8")
        self.assertNotRegex(entry, r"(?m)^\[include jwprobe_(?:qgl|bed_mesh)\.cfg\]$")
        self.assertRegex(entry, r"(?m)^#\[include jwprobe_z_tilt\.cfg\]")
        printer_cfg = (REPO_ROOT / "config" / "printer.cfg").read_text(encoding="utf-8")
        self.assertIn(jws_installer.JWP_BLOCK_START, printer_cfg)
        self.assertIn("[include jabberwockyprobe/jwprobe_qgl.cfg]", printer_cfg)
        self.assertIn("[include jabberwockyprobe/jwprobe_bed_mesh.cfg]", printer_cfg)
        self.assertTrue((REPO_ROOT / "config" / "jabberwockyprobe" / "jwprobe_qgl.cfg").is_file())
        self.assertTrue((REPO_ROOT / "config" / "jabberwockyprobe" / "jwprobe_bed_mesh.cfg").is_file())


class JWPInstallerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "printer_data" / "config"
        self.entry = self.config / "jabberwockyprobe" / "jwprobe_entry.cfg"
        self.canonical = self.config / "jwprobe_runtime_vars.cfg"
        self.legacy = self.config / "jabberwockyprobe" / "jwprobe_vars.cfg"
        self.marker = self.config / ".jwprobe_runtime_vars.migration"
        self.entry.parent.mkdir(parents=True)
        jws_installer.INSTALL_NOTES.clear()
        self.addCleanup(jws_installer.INSTALL_NOTES.clear)
        self.config_patch = patch.object(jws_installer, "CONFIG_DIR", str(self.config))
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def write_entry(self, filename: str = LEGACY) -> None:
        self.entry.write_text(
            "[save_variables]\n"
            f"filename: {filename}\n"
            "[include jwprobe_globals.cfg]\n",
            encoding="utf-8",
        )

    def test_fresh_install_creates_empty_store_without_copying_seed_values(self):
        self.write_entry()
        seed = (
            b"# JABBERWOCKY PROBE VARIABLES (REPO SEED COPY ONLY)\n"
            b"[Variables]\nprobe_nozzle_z_offset = 0.0\n"
        )
        self.legacy.write_bytes(seed)

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), b"[Variables]\n")
        self.assertEqual(self.legacy.read_bytes(), seed)
        self.assertEqual(jws_installer._save_variables_filename(self.entry.read_text()), CANONICAL)
        self.assertNotEqual(self.canonical.read_bytes(), seed)

    def test_update_keeps_canonical_data_when_deployed_legacy_path_contains_seed(self):
        self.write_entry(CANONICAL)
        data = b"[Variables]\nprobe_nozzle_z_offset = 0.381\n"
        seed = b"# REPO SEED COPY ONLY\n[Variables]\nprobe_nozzle_z_offset = 0.0\n"
        self.canonical.write_bytes(data)
        self.legacy.write_bytes(seed)

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), data)
        self.assertEqual(self.legacy.read_bytes(), seed)
        self.assertFalse(self.marker.exists())

    def test_update_preserves_existing_runtime_bytes_and_is_idempotent(self):
        self.write_entry(CANONICAL)
        data = b"[Variables]\nprobe_nozzle_z_offset = 0.381\nuser_value = 'keep exactly'\n"
        self.canonical.write_bytes(data)

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), data)
        self.assertFalse(self.marker.exists())

    def test_legacy_only_data_is_copied_once_and_original_is_kept(self):
        self.write_entry()
        data = b"[Variables]\nprobe_nozzle_z_offset = 0.38\nlegacy_user_key = True\n"
        self.legacy.write_bytes(data)

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), data)
        self.assertEqual(self.legacy.read_bytes(), data)
        self.assertIn(hashlib.sha256(data).hexdigest(), self.marker.read_text())
        self.assertEqual(jws_installer._save_variables_filename(self.entry.read_text()), CANONICAL)

        # Simulate a Klipper save after migration; future updates must not copy
        # the preserved legacy snapshot back over the canonical file.
        updated = data + b"newly_saved_value = 2\n"
        self.canonical.write_bytes(updated)
        marker_bytes = self.marker.read_bytes()
        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), updated)
        self.assertEqual(self.legacy.read_bytes(), data)
        self.assertEqual(self.marker.read_bytes(), marker_bytes)

    def test_preexisting_dual_files_are_preserved_and_require_manual_resolution(self):
        self.write_entry()
        canonical_data = b"[Variables]\nsource = 'canonical'\n"
        legacy_data = b"[Variables]\nsource = 'legacy'\n"
        self.canonical.write_bytes(canonical_data)
        self.legacy.write_bytes(legacy_data)
        entry_before = self.entry.read_bytes()

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "conflict")
        self.assertEqual(jws_installer._prepare_jwp_persistence(), "conflict")
        self.assertEqual(self.canonical.read_bytes(), canonical_data)
        self.assertEqual(self.legacy.read_bytes(), legacy_data)
        self.assertEqual(self.entry.read_bytes(), entry_before)
        self.assertFalse(self.marker.exists())
        self.assertTrue(any("conflict" in note.lower() for note in jws_installer.INSTALL_NOTES))

    def test_interrupted_legacy_migration_resumes_without_overwriting(self):
        self.write_entry()
        data = b"[Variables]\nprobe_nozzle_z_offset = 0.42\n"
        self.legacy.write_bytes(data)
        self.marker.write_text(f"sha256={hashlib.sha256(data).hexdigest()}\n", encoding="ascii")

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "ready")
        self.assertEqual(self.canonical.read_bytes(), data)
        self.assertEqual(self.legacy.read_bytes(), data)
        self.assertEqual(jws_installer._save_variables_filename(self.entry.read_text()), CANONICAL)

    def test_migration_marker_does_not_hide_an_unresolved_runtime_conflict(self):
        self.write_entry()
        legacy_data = b"[Variables]\nprobe_nozzle_z_offset = 0.42\n"
        canonical_data = b"[Variables]\nprobe_nozzle_z_offset = 0.51\n"
        self.legacy.write_bytes(legacy_data)
        self.canonical.write_bytes(canonical_data)
        self.marker.write_text(
            f"sha256={hashlib.sha256(legacy_data).hexdigest()}\n",
            encoding="ascii",
        )
        entry_before = self.entry.read_bytes()

        self.assertEqual(jws_installer._prepare_jwp_persistence(), "conflict")
        self.assertEqual(self.canonical.read_bytes(), canonical_data)
        self.assertEqual(self.legacy.read_bytes(), legacy_data)
        self.assertEqual(self.entry.read_bytes(), entry_before)

    def test_macro_pipeline_stops_on_unresolved_persistence_conflict(self):
        self.write_entry()
        canonical_data = b"[Variables]\nsource = 'canonical'\n"
        legacy_data = b"[Variables]\nsource = 'legacy'\n"
        self.canonical.write_bytes(canonical_data)
        self.legacy.write_bytes(legacy_data)

        with patch.object(jws_installer, "_deploy_jwp_event_tracker") as deploy_tracker:
            with self.assertRaisesRegex(RuntimeError, "JWP persistence conflict"):
                jws_installer.run_installation_pipeline()

        deploy_tracker.assert_not_called()
        self.assertEqual(self.canonical.read_bytes(), canonical_data)
        self.assertEqual(self.legacy.read_bytes(), legacy_data)
        self.assertFalse((self.config / "printer_20261013_120000.bak").exists())

    def test_macro_pipeline_stops_on_custom_persistence_path_before_deployment(self):
        self.write_entry("~/custom/vars.cfg")
        printer_cfg = self.config / "printer.cfg"
        printer_cfg.write_bytes(b"[printer]\nkinematics: corexy\n")
        files_before = {
            path.relative_to(self.config): path.read_bytes()
            for path in self.config.rglob("*")
            if path.is_file()
        }

        with patch.object(jws_installer, "_deploy_jwp_event_tracker") as deploy_tracker:
            with self.assertRaisesRegex(RuntimeError, "custom path"):
                jws_installer.run_installation_pipeline()

        deploy_tracker.assert_not_called()
        files_after = {
            path.relative_to(self.config): path.read_bytes()
            for path in self.config.rglob("*")
            if path.is_file()
        }
        self.assertEqual(files_after, files_before)

    def test_pipeline_runs_persistence_preparation_for_deployed_jwp(self):
        self.write_entry(CANONICAL)
        runtime_data = b"[Variables]\nprobe_nozzle_z_offset = 0.391\nprofile_confirmed = True\n"
        self.canonical.write_bytes(runtime_data)
        printer_cfg = self.config / "printer.cfg"
        printer_cfg.write_text("[include jabberwockyprobe/jwprobe_entry.cfg]\n", encoding="utf-8")
        dist = self.config / "jabberwocky_dist"
        dist.mkdir()
        manager = self.config / "jwt_macro_manager.conf"
        hardware = dist / "jwt_hardware.cfg"

        patches = (
            patch.object(jws_installer, "PRINTER_CFG", str(printer_cfg)),
            patch.object(jws_installer, "MANAGER_PATH", str(manager)),
            patch.object(jws_installer, "TARGET_DIST_DIR", str(dist)),
            patch.object(jws_installer, "HARDWARE_CFG_PATH", str(hardware)),
            patch.object(jws_installer, "_deploy_jwp_event_tracker", return_value=False),
            patch.object(jws_installer, "_ensure_shell_command_extension", return_value=False),
            patch.object(jws_installer.time, "strftime", return_value="20261013_120000"),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            self.assertTrue(jws_installer.run_installation_pipeline())

        self.assertEqual(self.canonical.read_bytes(), runtime_data)
        self.assertEqual(jws_installer._save_variables_filename(self.entry.read_text()), CANONICAL)


class JWPBuildTests(unittest.TestCase):
    def test_release_excludes_variable_seed_and_runtime_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            output = root / "release"
            source.mkdir()
            (source / "jwprobe_entry.cfg").write_text("[include jwprobe_globals.cfg]\n")
            (source / "jwprobe_globals.cfg").write_text("ordinary_config = True\n")
            (source / "jwprobe_vars.cfg").write_text("seed_secret_value = 111\n")
            (source / "jwprobe_runtime_vars.cfg").write_text("runtime_secret_value = 222\n")
            (source / "jwp_calibration_profile.csv").write_text("user_telemetry,333\n")
            release = JabberwockyCompiler(str(source), str(output))

            self.assertTrue(release.compile_release_package("jwp.cfg"))
            artifact = (output / "jwp.cfg").read_text(encoding="utf-8")
            self.assertIn("ordinary_config = True", artifact)
            self.assertNotIn("seed_secret_value", artifact)
            self.assertNotIn("runtime_secret_value", artifact)
            self.assertNotIn("user_telemetry", artifact)


if __name__ == "__main__":
    unittest.main()
