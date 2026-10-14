"""v5.9.0 scanner / adoption / sync / restart tests (all inside temp directories)."""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scrubber import jws_core
from scrubber.jws_analyzers import run_all
from scrubber.jws_observer import build_inventory
from scrubber.jws_operator import apply_in_place_masking
from scrubber.macro_manager import MacroManager
from software import jws_installer

REAL_CONFIG = REPO_ROOT / "config"


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class Env:
    """Temp printer config tree plus installer patching."""

    def __init__(self, tmp: str):
        self.root = Path(tmp) / "printer_data" / "config"
        (self.root / "jabberwocky_dist").mkdir(parents=True)

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    @property
    def dashboard(self) -> Path:
        return self.root / "jwt_macro_manager.conf"

    def install(self):
        r = self.root
        with contextlib.ExitStack() as stack:
            for name, value in (
                ("CONFIG_DIR", str(r)),
                ("PRINTER_CFG", str(r / "printer.cfg")),
                ("MANAGER_PATH", str(self.dashboard)),
                ("TARGET_DIST_DIR", str(r / "jabberwocky_dist")),
                ("HARDWARE_CFG_PATH", str(r / "jabberwocky_dist" / "jwt_hardware.cfg")),
                ("QUARANTINE_DIR", str(r / "jabberwocky_quarantine")),
            ):
                stack.enter_context(patch.object(jws_installer, name, value))
            stack.enter_context(patch.object(jws_installer, "_ensure_shell_command_extension", return_value=False))
            stack.enter_context(patch.object(jws_installer.time, "strftime", return_value="20261010_120000"))
            return jws_installer.run_installation_pipeline()

    def sync(self, *extra, **env):
        argv = ["--config-dir", str(self.root), "--sync", *extra]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = jws_core.main(argv)
        return code, out.getvalue()

    def set_state(self, key_fragment: str, value: int):
        lines = self.dashboard.read_text(encoding="utf-8").splitlines(True)
        done = False
        for i, line in enumerate(lines):
            if key_fragment in line and "[ " in line:
                lines[i] = line.replace("[ 0 ]", f"[ {value} ]", 1).replace("[ 1 ]", f"[ {value} ]", 1)
                done = True
                break
        assert done, key_fragment
        self.dashboard.write_text("".join(lines), encoding="utf-8")


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env = Env(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        e = self.env
        e.write("printer.cfg",
                "[include live.cfg]\n"
                "#[include parked.cfg]\n"
                "# [include manual.cfg] keep manual comment\n"
                "#[include nowhere.cfg]\n"
                "[stepper_x]\nstep_pin: PA1\n")
        e.write("live.cfg",
                "[gcode_macro KEEP]\ngcode:\n  M117 keep\n\n"
                "#[gcode_macro PARKED_MACRO]\n#gcode:\n#  M117 parked\n")
        e.write("parked.cfg", "[gcode_macro FROM_PARKED]\ngcode:\n  M117 x\n")
        e.write("manual.cfg", "[gcode_macro MANUAL]\ngcode:\n  M117 m\n")

    def test_plain_hash_entries_are_adopted_as_off_and_backed_up(self):
        self.env.install()
        text = (self.env.root / "printer.cfg").read_text(encoding="utf-8")
        self.assertIn("#💤#[include parked.cfg]", text)
        self.assertIn("# [include manual.cfg] keep manual comment", text)
        self.assertIn("#[include nowhere.cfg]", text)
        states = MacroManager(self.env.dashboard).states
        self.assertEqual(states["file_parked_cfg"], 0)
        self.assertEqual(states["macro_parked_macro@live.cfg"], 0)
        self.assertEqual(states["macro_keep@live.cfg"], 1)
        self.assertNotIn("file_nowhere_cfg", states)
        self.assertTrue(list((self.env.root / "jabberwocky_quarantine").glob("adopt_backup_*/printer.cfg")))
        live = (self.env.root / "live.cfg").read_text(encoding="utf-8")
        self.assertIn("TO RE-ENABLE", live)

    def test_dashboard_one_restores_plain_comment_and_repeat_sync_is_quiet(self):
        e = self.env
        e.install()
        _, first = e.sync()
        self.assertIn("0 item(s) changed", first)
        e.set_state("PARKED_MACRO", 1)
        _, out = e.sync()
        self.assertIn("1 item(s) changed", out)
        live = (e.root / "live.cfg").read_text(encoding="utf-8")
        self.assertIn("[gcode_macro PARKED_MACRO]\ngcode:\n  M117 parked", live)
        self.assertNotIn("TO RE-ENABLE", live)
        _, again = e.sync()
        self.assertIn("0 item(s) changed", again)
        e.set_state("PARKED_MACRO", 0)
        e.sync()
        self.assertIn("#💤#[gcode_macro PARKED_MACRO]", (e.root / "live.cfg").read_text(encoding="utf-8"))

    def test_nested_include_row_toggles_by_relative_path(self):
        e = self.env
        e.write("printer.cfg", "[include sub/inner.cfg]\n")
        e.write("sub/inner.cfg", "[include sibling.cfg]\n")
        e.write("sub/sibling.cfg", "[gcode_macro SIB]\ngcode:\n  M117 s\n")
        e.install()
        states = MacroManager(e.dashboard).states
        self.assertIn("file_sub%2Finner_cfg", states)
        self.assertIn("file_sub%2Fsibling_cfg", states)
        e.set_state("SUB/SIBLING.CFG (MASTER", 0)
        e.sync()
        self.assertIn("#💤#[include sibling.cfg]", (e.root / "sub" / "inner.cfg").read_text(encoding="utf-8"))
        e.set_state("SUB/SIBLING.CFG (MASTER", 1)
        e.sync()
        self.assertEqual((e.root / "sub" / "inner.cfg").read_text(encoding="utf-8"), "[include sibling.cfg]\n")

    def test_normal_run_without_sync_changes_nothing(self):
        self.env.install()
        before = tree_hash(self.env.root)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            jws_core.main(["--config-dir", str(self.env.root)])
            jws_core.main(["--config-dir", str(self.env.root), "--report"])
        self.assertEqual(before, tree_hash(self.env.root))


class FindingsTests(unittest.TestCase):
    def test_blockers_hardware_duplicates_and_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            e = Env(tmp)
            e.write("printer.cfg", "[include a.cfg]\n[include gone.cfg]\n[extruder]\nrun_current: 1\n")
            e.write("a.cfg", "[extruder]\nrun_current: 2\n[tmc2209 extruder]\n[gcode_macro DUP]\ngcode:\n  M117\n")
            e.write("b.cfg", "[gcode_macro DUP]\ngcode:\n  M117\n")  # mentioned nowhere: complete orphan
            e.write("c.cfg", "# unloaded\n")
            e.write("notes.cfg", "# see c.cfg for details\n")
            e.write("printer.cfg.bak", "x")
            inv = build_inventory(e.root / "printer.cfg", e.root)
            codes = {f.code: f for f in run_all(inv)}
            self.assertEqual(codes["INCLUDE_MISSING"].category, "BLOCKER")
            self.assertTrue(codes["INCLUDE_MISSING"].remedy)
            self.assertIn("HARDWARE_DUPLICATE", codes)
            self.assertIn("b.cfg", [f for x in run_all(inv) if x.code == "FILE_ORPHAN" for f in x.files])
            self.assertIn("BACKUPS", codes)
            self.assertNotIn("a.cfg", [f for x in run_all(inv) if x.code == "FILE_ORPHAN" for f in x.files])

    def test_sweep_moves_only_backups_and_orphans_then_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            e = Env(tmp)
            e.write("printer.cfg", "[include a.cfg]\n")
            e.write("a.cfg", "[gcode_macro A]\ngcode:\n  M117\n")
            e.write("orphan.cfg", "# nobody\n")
            e.write("old.cfg.bak", "x")
            e.install()
            self.assertTrue((e.root / "orphan.cfg").exists())  # sweep is off by default
            e.set_state("SWEEP TO QUARANTINE", 1)
            e.install()
            self.assertFalse((e.root / "orphan.cfg").exists())
            self.assertFalse((e.root / "old.cfg.bak").exists())
            self.assertTrue((e.root / "a.cfg").exists())
            self.assertTrue(list((e.root / "jabberwocky_quarantine").glob("sweep_*/orphan.cfg")))
            self.assertEqual(MacroManager(e.dashboard).states["action_sweep_to_quarantine"], 0)
            self.assertTrue(list(e.root.glob("printer_*.bak")))  # fresh safety copy is not swept


class RestartTests(unittest.TestCase):
    def test_restart_only_when_changed_and_respects_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            e = Env(tmp)
            e.write("printer.cfg", "[include a.cfg]\n")
            e.write("a.cfg", "[gcode_macro A]\ngcode:\n  M117\n")
            e.install()
            with patch.object(jws_core, "request_restart", return_value=True) as restart:
                e.sync("--restart-if-changed")
                restart.assert_not_called()
                e.set_state("A.CFG (MASTER", 0)
                e.sync("--restart-if-changed")
                self.assertEqual(restart.call_count, 1)
                e.set_state("A.CFG (MASTER", 1)
                e.sync("--restart-if-changed")  # change again inside the cooldown
                self.assertEqual(restart.call_count, 1)
            self.assertTrue((e.root / "printer.cfg").read_text(encoding="utf-8").startswith("[include a.cfg]\n"))


class RealConfigCopyTests(unittest.TestCase):
    @unittest.skipUnless(REAL_CONFIG.is_dir(), "real config/ copy not present")
    def test_installer_and_sync_on_copy_of_real_config(self):
        before = tree_hash(REAL_CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            e = Env(tmp)
            shutil.rmtree(e.root)
            shutil.copytree(REAL_CONFIG, e.root,
                            ignore=shutil.ignore_patterns("*.zip", "*.csv", "__pycache__"))
            e.install()
            first = e.dashboard.read_text(encoding="utf-8")
            self.assertIn("🔩 [H!] [extruder]", first)
            self.assertIn("(MASTER INCLUDE MAP)", first)
            e.install()
            states_a = MacroManager(e.dashboard).states
            e.install()
            self.assertEqual(states_a, MacroManager(e.dashboard).states)
            printer_before = tree_hash(e.root)
            _, out = e.sync()
            self.assertIn("0 item(s) changed", out)
            self.assertEqual(printer_before, tree_hash(e.root))
            # Duplicate PAUSE: switch off the overridden copy only.
            e.set_state("PAUSE (🛑", 0)
            _, out = e.sync()
            self.assertIn("1 item(s) changed", out)
            main_text = (e.root / "mainsail.cfg").read_text(encoding="utf-8")
            edit_text = (e.root / "mainsail_edit.cfg").read_text(encoding="utf-8")
            self.assertIn("#💤#[gcode_macro PAUSE]", main_text)
            self.assertNotIn("#💤#[gcode_macro PAUSE]", edit_text)
        self.assertEqual(before, tree_hash(REAL_CONFIG), "real config/ must never be modified")


class OperatorEdgeTests(unittest.TestCase):
    def test_indented_jinja_list_does_not_truncate_macro_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "m.cfg"
            f.write_text("[gcode_macro X]\ngcode:\n  {% set a = [1, 2] %}\n  M117\n[gcode_macro Y]\ngcode:\n  M117\n", encoding="utf-8")
            self.assertTrue(apply_in_place_masking(f, {"macro_x@m.cfg": 0}, "macro", "X", "m.cfg"))
            text = f.read_text(encoding="utf-8")
            self.assertIn("#💤#  M117", text)
            self.assertIn("\n[gcode_macro Y]\ngcode:\n  M117\n", text)
            self.assertTrue(apply_in_place_masking(f, {"macro_x@m.cfg": 1}, "macro", "X", "m.cfg"))
            self.assertEqual(f.read_text(encoding="utf-8").count("💤"), 0)

    def test_masked_block_gets_spacer_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "m.cfg"
            original = "[gcode_macro X]\ngcode:\n  M117\n[gcode_macro Y]\ngcode:\n  M117\n"
            f.write_text(original, encoding="utf-8")
            apply_in_place_masking(f, {"macro_x@m.cfg": 0}, "macro", "X", "m.cfg")
            self.assertIn("\n\n[gcode_macro Y]", f.read_text(encoding="utf-8"))
            apply_in_place_masking(f, {"macro_x@m.cfg": 1}, "macro", "X", "m.cfg")
            self.assertEqual(f.read_text(encoding="utf-8"), original)

    def test_disabled_include_without_file_is_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "printer.cfg").write_text("#[include ghost.cfg]\n[printer]\nkinematics: none\n", encoding="utf-8")
            inv = build_inventory(Path(tmp) / "printer.cfg", Path(tmp))
            hits = [f for f in run_all(inv) if f.code == "COMMENTED_MISSING"]
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].category, "WARNING")


if __name__ == "__main__":
    unittest.main()
