from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scrubber import jws_core
from scrubber.jws_observer import scan
from scrubber.jws_operator import apply_in_place_masking
from scrubber.macro_manager import (
    MacroManager,
    decode_component_key,
    iter_dashboard_rows,
    normalize_component_key,
    parse_dashboard_line,
)
from software import jws_installer


class MacroManagerTests(unittest.TestCase):
    def test_dashboard_rows_have_distinct_file_macro_and_action_keys(self):
        rows = (
            "[ 0 ] 📂 alpha-beta.cfg (MASTER INCLUDE MAP)",
            "  ├── [ 1 ] ▶ [D!] alpha_macro (ACTIVE OVERRIDE)",
            "[ 0 ] ⚙️ SYSTEM ACTION: SNAPSHOT BACKUP",
            "[ 1 ] ⚙️ SYSTEM ACTION: SNAPSHOT RESTORE",
            "[ 0 ] ⚙️ SYSTEM ACTION: SWEEP TO QUARANTINE",
        )
        parsed = [parsed for _line, parsed in iter_dashboard_rows(rows)]
        self.assertEqual(
            parsed,
            [
                ("file_alpha-beta_cfg", 0),
                ("macro_alpha_macro@alpha-beta.cfg", 1),
                ("action_snapshot_backup", 0),
                ("action_snapshot_restore", 1),
                ("action_sweep_to_quarantine", 0),
            ],
        )
        self.assertEqual(decode_component_key("file_alpha-beta_cfg"), ("file", "alpha-beta.cfg"))
        self.assertIsNone(parse_dashboard_line("# [ 0 ] 📂 example.cfg (MASTER INCLUDE MAP)"))
        self.assertEqual(
            normalize_component_key("file", "sub/alpha-beta.cfg"),
            "file_sub%2Falpha-beta_cfg",
        )

    def test_persist_updates_states_without_rewriting_other_dashboard_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dashboard = Path(temp_dir) / "jwt_macro_manager.conf"
            original = (
                "# Keep this heading and note.\n"
                "[ 0 ] 📂 alpha.cfg (MASTER INCLUDE MAP)\n"
                "  ├── [ 1 ] ▶ alpha_macro\n"
                "[ 0 ] ⚙️ SYSTEM ACTION: SNAPSHOT BACKUP\n"
                "custom user note\n"
            )
            dashboard.write_text(original, encoding="utf-8")
            manager = MacroManager(dashboard)
            manager.set_state("file_alpha_cfg", 1)
            manager.set_state("macro_alpha_macro@alpha.cfg", 0)
            manager.set_state("action_snapshot_backup", 1)
            manager.persist()

            updated = dashboard.read_text(encoding="utf-8")
            self.assertIn("[ 1 ] 📂 alpha.cfg", updated)
            self.assertIn("[ 0 ] ▶ alpha_macro", updated)
            self.assertIn("[ 1 ] ⚙️ SYSTEM ACTION: SNAPSHOT BACKUP", updated)
            self.assertTrue(updated.endswith("custom user note\n"))
            self.assertEqual(MacroManager(dashboard).states, {
                "file_alpha_cfg": 1,
                "macro_alpha_macro@alpha.cfg": 0,
                "action_snapshot_backup": 1,
            })
            with self.assertRaises(ValueError):
                manager.set_state("file_alpha_cfg", 2)
            with self.assertRaises(KeyError):
                manager.set_state("macro_not_present", 0)
                manager.persist()


class MaskingTests(unittest.TestCase):
    def test_include_mask_and_restore_preserve_comments_and_user_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "printer.cfg"
            original = (
                "[include alpha-beta.cfg] # retain this comment\n"
                "# [include manually-disabled.cfg] user-owned\n"
                "[include keep.cfg] # unrelated\n"
            )
            config.write_text(original, encoding="utf-8")

            self.assertTrue(apply_in_place_masking(
                config, {"file_alpha-beta_cfg": 0}, "file", "alpha-beta.cfg"
            ))
            masked = config.read_text(encoding="utf-8")
            self.assertIn("#💤#[include alpha-beta.cfg] # retain this comment", masked)
            self.assertIn("# [include manually-disabled.cfg] user-owned", masked)
            self.assertIn("[include keep.cfg] # unrelated", masked)
            self.assertFalse(apply_in_place_masking(
                config, {"file_alpha-beta_cfg": 0}, "file", "alpha-beta.cfg"
            ))

            self.assertTrue(apply_in_place_masking(
                config, {"file_alpha-beta_cfg": 1}, "file", "alpha-beta.cfg"
            ))
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertFalse(apply_in_place_masking(
                config, {"file_alpha-beta_cfg": 1}, "file", "alpha-beta.cfg"
            ))

    def test_macro_mask_stops_at_next_section_and_restores_exact_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "macros.cfg"
            original = (
                "[gcode_macro alpha_macro]\n"
                "gcode:\n"
                "    RESPOND MSG=\"alpha\"\n"
                "# retain this macro comment\n"
                "\n"
                "[gcode_macro beta_macro]\n"
                "gcode:\n"
                "    RESPOND MSG=\"beta\"\n"
            )
            config.write_text(original, encoding="utf-8")

            self.assertTrue(apply_in_place_masking(
                config, {"macro_alpha_macro": 0}, "macro", "alpha_macro"
            ))
            masked = config.read_text(encoding="utf-8")
            self.assertIn("#💤#    RESPOND MSG=\"alpha\"", masked)
            self.assertIn("[gcode_macro beta_macro]\ngcode:\n    RESPOND MSG=\"beta\"", masked)
            self.assertNotIn("#💤#[gcode_macro beta_macro]", masked)
            self.assertFalse(apply_in_place_masking(
                config, {"macro_alpha_macro": 0}, "macro", "alpha_macro"
            ))

            self.assertTrue(apply_in_place_masking(
                config, {"macro_alpha_macro": 1}, "macro", "alpha_macro"
            ))
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertFalse(apply_in_place_masking(
                config, {"macro_alpha_macro": 1}, "macro", "alpha_macro"
            ))

    def test_scanner_does_not_follow_plain_commented_includes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "printer.cfg").write_text(
                "# [include manual.cfg]\n"
                "[include active.cfg]\n"
                "#💤#[include masked.cfg]\n",
                encoding="utf-8",
            )
            for filename in ("manual.cfg", "active.cfg", "masked.cfg"):
                (root / filename).write_text("", encoding="utf-8")
            _, registry, _ = scan(root / "printer.cfg", root)
            names = {Path(path).name for path in registry["files"]}
            self.assertEqual(names, {"printer.cfg", "active.cfg", "masked.cfg"})


class SynchronizationTests(unittest.TestCase):
    @staticmethod
    def _fixture(config_dir: Path) -> tuple[str, str, str]:
        (config_dir / "printer.cfg").write_text(
            "[include alpha-beta.cfg] # preserve alpha comment\n"
            "[include stable.cfg] # preserve stable comment\n"
            "# [include manual.cfg] keep manual comment\n",
            encoding="utf-8",
        )
        (config_dir / "alpha-beta.cfg").write_text(
            "[gcode_macro alpha_macro]\n"
            "gcode:\n"
            "    RESPOND MSG=\"alpha\"\n"
            "[gcode_macro stable_macro]\n"
            "gcode:\n"
            "    RESPOND MSG=\"stable\"\n",
            encoding="utf-8",
        )
        (config_dir / "stable.cfg").write_text(
            "[gcode_macro other_macro]\n"
            "gcode:\n"
            "    RESPOND MSG=\"other\"\n",
            encoding="utf-8",
        )
        (config_dir / "manual.cfg").write_text("# must not be followed\n", encoding="utf-8")
        (config_dir / "unrelated.txt").write_text("leave unchanged\n", encoding="utf-8")
        (config_dir / "jwt_macro_manager.conf").write_text(
            "[ 0 ] 📂 alpha-beta.cfg (MASTER INCLUDE MAP)\n"
            "  ├── [ 0 ] ▶ alpha_macro\n"
            "[ 1 ] 📂 stable.cfg (MASTER INCLUDE MAP)\n"
            "  ├── [ 1 ] ▶ stable_macro\n"
            "[ 0 ] ⚙️ SYSTEM ACTION: SNAPSHOT BACKUP\n"
            "[ 1 ] ⚙️ SYSTEM ACTION: SNAPSHOT RESTORE\n"
            "[ 0 ] ⚙️ SYSTEM ACTION: SWEEP TO QUARANTINE\n",
            encoding="utf-8",
        )
        hardware = config_dir / "jabberwocky_dist" / "jwt_hardware.cfg"
        hardware.parent.mkdir()
        hardware.write_text(
            "[gcode_macro _ASC_SETUP_VARIABLES]\n"
            "variable_asc_hardware_run_current: 0.77\n"
            "variable_asc_stealthchop_threshold: 5.0\n"
            "variable_asc_rotation_distance: 33.3\n",
            encoding="utf-8",
        )
        return (
            (config_dir / "jwt_macro_manager.conf").read_text(encoding="utf-8"),
            hardware.read_text(encoding="utf-8"),
            (config_dir / "unrelated.txt").read_text(encoding="utf-8"),
        )

    def test_sync_disable_enable_is_repeatable_and_preserves_unrelated_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "home" / "printer_data" / "config"
            config_dir.mkdir(parents=True)
            dashboard_before, hardware_before, unrelated_before = self._fixture(config_dir)

            with patch.dict(os.environ, {
                "HOME": str(config_dir.parents[1]),
                "PRINTER_CONFIG_DIR": str(config_dir),
            }), patch.object(sys, "argv", ["jws_core.py", "--sync"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    jws_core.main()

                after_first = {
                    path.relative_to(config_dir): path.read_bytes()
                    for path in config_dir.rglob("*") if path.is_file()
                }
                printer_text = (config_dir / "printer.cfg").read_text(encoding="utf-8")
                macro_text = (config_dir / "alpha-beta.cfg").read_text(encoding="utf-8")
                self.assertIn("#💤#[include alpha-beta.cfg] # preserve alpha comment", printer_text)
                self.assertIn("# [include manual.cfg] keep manual comment", printer_text)
                self.assertIn("#💤#=== JABBERWOCKY COMPLIANCE ISOLATION BLOCK START ===#💤# alpha_macro", macro_text)
                self.assertIn("[gcode_macro stable_macro]", macro_text)
                self.assertEqual((config_dir / "stable.cfg").read_text(encoding="utf-8").count("#💤#"), 0)
                self.assertEqual((config_dir / "jwt_macro_manager.conf").read_text(encoding="utf-8"), dashboard_before)
                self.assertEqual((config_dir / "jabberwocky_dist/jwt_hardware.cfg").read_text(encoding="utf-8"), hardware_before)
                self.assertEqual((config_dir / "unrelated.txt").read_text(encoding="utf-8"), unrelated_before)

                with contextlib.redirect_stdout(io.StringIO()):
                    jws_core.main()
                after_second = {
                    path.relative_to(config_dir): path.read_bytes()
                    for path in config_dir.rglob("*") if path.is_file()
                }
                self.assertEqual(after_second, after_first)

                manager = MacroManager(config_dir / "jwt_macro_manager.conf")
                manager.set_state("file_alpha-beta_cfg", 1)
                manager.set_state("macro_alpha_macro@alpha-beta.cfg", 1)
                manager.persist()
                with contextlib.redirect_stdout(io.StringIO()):
                    jws_core.main()
                restored_printer = (config_dir / "printer.cfg").read_text(encoding="utf-8")
                restored_macro = (config_dir / "alpha-beta.cfg").read_text(encoding="utf-8")
                self.assertIn("[include alpha-beta.cfg] # preserve alpha comment", restored_printer)
                self.assertIn("[gcode_macro alpha_macro]\ngcode:\n    RESPOND MSG=\"alpha\"", restored_macro)

                after_enable = {
                    path.relative_to(config_dir): path.read_bytes()
                    for path in config_dir.rglob("*") if path.is_file()
                }
                with contextlib.redirect_stdout(io.StringIO()):
                    jws_core.main()
                self.assertEqual(
                    {
                        path.relative_to(config_dir): path.read_bytes()
                        for path in config_dir.rglob("*") if path.is_file()
                    },
                    after_enable,
                )

    def test_installer_regeneration_preserves_old_rows_and_hardware_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            config_dir = home / "printer_data" / "config"
            target_dist = config_dir / "jabberwocky_dist"
            target_dist.mkdir(parents=True)
            (config_dir / "printer.cfg").write_text(
                "[extruder]\n"
                "run_current: 0.77\n"
                "stealthchop_threshold: 5.0\n"
                "rotation_distance: 33.3\n"
                "[include alpha-beta.cfg]\n"
                "[include fresh.cfg]\n",
                encoding="utf-8",
            )
            (config_dir / "alpha-beta.cfg").write_text(
                "[gcode_macro alpha_macro]\ngcode:\n    RESPOND MSG=\"alpha\"\n",
                encoding="utf-8",
            )
            (config_dir / "fresh.cfg").write_text(
                "[gcode_macro newly_discovered]\ngcode:\n    RESPOND MSG=\"new\"\n",
                encoding="utf-8",
            )
            dashboard = config_dir / "jwt_macro_manager.conf"
            dashboard.write_text(
                "[ 0 ] 📂 alpha-beta.cfg (MASTER INCLUDE MAP)\n"
                "  ├── [ 0 ] ▶ alpha_macro\n"
                "  ├── [ 0 ] ⚙️ SYSTEM ACTION: SNAPSHOT RESTORE\n"
                "[ 0 ] 📂 retired.cfg (MASTER INCLUDE MAP)\n",
                encoding="utf-8",
            )
            hardware = target_dist / "jwt_hardware.cfg"
            hardware_before = (
                "[gcode_macro _ASC_SETUP_VARIABLES]\n"
                "variable_asc_hardware_run_current: 0.77\n"
                "variable_asc_stealthchop_threshold: 5.0\n"
                "variable_asc_rotation_distance: 33.3\n"
            )
            hardware.write_text(hardware_before, encoding="utf-8")

            with (
                patch.object(jws_installer, "CONFIG_DIR", str(config_dir)),
                patch.object(jws_installer, "PRINTER_CFG", str(config_dir / "printer.cfg")),
                patch.object(jws_installer, "MANAGER_PATH", str(dashboard)),
                patch.object(jws_installer, "TARGET_DIST_DIR", str(target_dist)),
                patch.object(jws_installer, "HARDWARE_CFG_PATH", str(hardware)),
                patch.object(jws_installer, "QUARANTINE_DIR", str(config_dir / "jabberwocky_quarantine")),
                patch.object(jws_installer.time, "strftime", return_value="20261010_120000"),
                patch.object(jws_installer, "_ensure_shell_command_extension", return_value=False),
            ):
                self.assertTrue(jws_installer.run_installation_pipeline())
                self.assertTrue(jws_installer.run_installation_pipeline())

            manager = MacroManager(dashboard)
            self.assertEqual(manager.get_state("file_alpha-beta_cfg"), 0)
            self.assertEqual(manager.get_state("macro_alpha_macro@alpha-beta.cfg"), 0)
            self.assertEqual(manager.get_state("action_snapshot_restore"), 0)
            self.assertEqual(manager.get_state("file_fresh_cfg"), 1)
            self.assertEqual(manager.get_state("macro_newly_discovered@fresh.cfg"), 1)
            self.assertEqual(manager.get_state("file_retired_cfg"), 0)
            self.assertEqual(hardware.read_text(encoding="utf-8"), hardware_before)


class DuplicateMacroScopeTests(unittest.TestCase):
    def _run_sync(self, root: Path) -> None:
        with patch.dict(os.environ, {"PRINTER_CONFIG_DIR": str(root)}), \
             patch.object(sys, "argv", ["jws_core.py", "--sync"]), \
             contextlib.redirect_stdout(io.StringIO()):
            jws_core.main()

    def test_duplicate_macro_rows_toggle_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "printer.cfg").write_text("[include mainsail.cfg]\n[include mainsail_edit.cfg]\n", encoding="utf-8")
            body = "[gcode_macro PAUSE]\ngcode:\n  M117 {}\n"
            (root / "mainsail.cfg").write_text(body.format("a"), encoding="utf-8")
            (root / "mainsail_edit.cfg").write_text(body.format("b"), encoding="utf-8")
            dash = root / "jwt_macro_manager.conf"
            dash.write_text(
                "[ 1 ] 📂 MAINSAIL.CFG (MASTER INCLUDE MAP)\n"
                "  ├── [ 0 ] ▶ [D?] PAUSE (x)\n"
                "[ 1 ] 📂 MAINSAIL_EDIT.CFG (MASTER INCLUDE MAP)\n"
                "  ├── [ 1 ] ▶ [D!] PAUSE (y)\n",
                encoding="utf-8",
            )
            states = MacroManager(dash).states
            self.assertEqual(states["macro_pause@mainsail.cfg"], 0)
            self.assertEqual(states["macro_pause@mainsail_edit.cfg"], 1)

            self._run_sync(root)
            self.assertIn("#💤#[gcode_macro PAUSE]", (root / "mainsail.cfg").read_text(encoding="utf-8"))
            self.assertEqual((root / "mainsail_edit.cfg").read_text(encoding="utf-8"), body.format("b"))

            snapshot = (root / "mainsail.cfg").read_text(encoding="utf-8")
            self._run_sync(root)
            self.assertEqual((root / "mainsail.cfg").read_text(encoding="utf-8"), snapshot)

            dash.write_text(dash.read_text(encoding="utf-8").replace("[ 0 ] ▶", "[ 1 ] ▶"), encoding="utf-8")
            self._run_sync(root)
            self.assertEqual((root / "mainsail.cfg").read_text(encoding="utf-8"), body.format("a"))


class SyncBridgeInstallTests(unittest.TestCase):
    def test_bridge_is_rendered_with_local_paths_only_when_extension_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir, target_dist = root / "cfg", root / "cfg" / "jabberwocky_dist"
            extras = root / "klipper" / "klippy" / "extras"
            target_dist.mkdir(parents=True)
            extras.mkdir(parents=True)
            printer = config_dir / "printer.cfg"
            printer.write_text("[include a.cfg]\n", encoding="utf-8")
            patches = (
                patch.object(jws_installer, "CONFIG_DIR", str(config_dir)),
                patch.object(jws_installer, "PRINTER_CFG", str(printer)),
                patch.object(jws_installer, "TARGET_DIST_DIR", str(target_dist)),
                patch.dict(os.environ, {"JWS_KLIPPER_DIR": str(root / "klipper")}),
            )
            with contextlib.ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                with patch.object(jws_installer, "_ensure_shell_command_extension", return_value=False):
                    jws_installer._inject_and_link()
                self.assertNotIn("jwt_sync_bridge.cfg", printer.read_text(encoding="utf-8"))
                self.assertFalse((target_dist / "jwt_sync_bridge.cfg").exists())

                (extras / "gcode_shell_command.py").write_text("def load_config_prefix(c): pass\n", encoding="utf-8")
                jws_installer._inject_and_link()
                self.assertIn("[include jabberwocky_dist/jwt_sync_bridge.cfg]", printer.read_text(encoding="utf-8"))
                bridge = (target_dist / "jwt_sync_bridge.cfg").read_text(encoding="utf-8")
                self.assertNotIn("__JWS_", bridge)
                self.assertNotIn("/home/tlam", bridge)
                self.assertIn(str(config_dir), bridge)
                self.assertIn(str(REPO_ROOT / "scrubber" / "jws_core.py"), bridge)


if __name__ == "__main__":
    unittest.main()
