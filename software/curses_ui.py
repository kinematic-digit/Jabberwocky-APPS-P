# =====================================================================
# JABBERWOCKY APPS Suite — FRIENDLY SETUP SCREEN (curses)
# VERSION: 5.9.1 [Plain-language menu, paced progress, honest verification]
# Location: software/curses_ui.py
# =====================================================================
import os, sys, curses, time, textwrap
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from software import jws_installer
# Seconds to pause between on-screen steps so people can read them.
# JWS_UI_PACE=0 disables.
PACE = float(os.environ.get("JWS_UI_PACE", "0.7"))

class JabberwockyTerminalUI:
    def __init__(self):
        # (title, description lines, available)
        self.options = (
            (
                "Check my printer setup and create the dashboard",
                (
                    "Reads your printer.cfg and the files it loads. Builds a dashboard page where you",
                    "switch files and macros ON (1) or OFF (0). Your files are never deleted, and a",
                    "safety copy is made first. This is the only step you need today.",
                ),
                True,
            ),
            (
                "Extruder tuning tools",
                ("Not available yet. Planned for a future release.",),
                False,
            ),
            (
                "Install / Update JWP",
                (
                    "Deploys or updates the Jabberwocky Probe package and read-only event tracker.",
                    "Preserves calibration data, hardware bindings, and user globals. Manages QGL",
                    "and bed-mesh dashboard wrappers only when the matching native sections exist.",
                    "Review the probe pin and offsets before restarting Klipper after a fresh install.",
                ),
                True,
            ),
            (
                "Report",
                (
                    "Creates and displays a read-only diagnostic report.",
                    "This can help diagnose problems even when Klipper is not running.",
                    "Press ENTER to view the report. Press S in the report to save a timestamped copy",
                    "in your configured Klipper config directory. Existing reports are never overwritten.",
                ),
                True,
            ),
        )
        self.selections = [True, False, False]
        self.version_string = "v5.9.1"
        self.stage_lines = []
        self._scr = None

    def safe_addstr(self, stdscr, y, x, text, attr=0):
        try:
            h, w = stdscr.getmaxyx()
            if 0 <= y < h - 1 and 0 <= x < w:
                stdscr.addstr(y, x, text[:w - x - 1], attr)
        except Exception:
            pass

    def pause(self, factor=1.0):
        if PACE > 0:
            time.sleep(PACE * factor)

    def header(self, stdscr, w, text):
        self.safe_addstr(
            stdscr,
            0,
            0,
            f" {text} ".ljust(w),
            curses.A_REVERSE | curses.A_BOLD,
        )

    def wrapped(self, stdscr, y, x, text, width, attr=0):
        for part in textwrap.wrap(text, max(20, width)) or [""]:
            self.safe_addstr(stdscr, y, x, part, attr)
            y += 1
        return y

    def progress(self, stage, message=""):
        """Called by the installer at the start of each stage."""
        stdscr = self._scr
        self.stage_lines.append(message or stage)
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        self.header(stdscr, w, f"SETTING UP — JABBERWOCKY APPS {self.version_string}")
        self.safe_addstr(
            stdscr,
            2,
            2,
            "Working through your printer setup. Nothing is deleted.",
            curses.A_BOLD,
        )
        for i, line in enumerate(self.stage_lines):
            last = i == len(self.stage_lines) - 1
            self.safe_addstr(
                stdscr,
                4 + i,
                4,
                ("...  " if last else "OK   ") + line,
                curses.A_BOLD if last else 0,
            )
        stdscr.refresh()
        self.pause()

    def run_pipeline(self, stdscr):
        self._scr = stdscr
        self.stage_lines = []
        notes = []
        try:
            if self.selections[0]:
                jws_installer.run_installation_pipeline(progress=self.progress)
                notes.extend(jws_installer.INSTALL_NOTES)
            if self.selections[2]:
                jws_installer.run_jwp_installation_pipeline(progress=self.progress)
                notes.extend(jws_installer.INSTALL_NOTES)
            jws_installer.INSTALL_NOTES[:] = notes
            return None
        except Exception as exc:
            if notes:
                jws_installer.INSTALL_NOTES[:] = notes + jws_installer.INSTALL_NOTES
            return str(exc) or exc.__class__.__name__

    def toggle_selection(self, index):
        self.selections[index] = not self.selections[index]
        if self.selections[index] and index in (0, 2):
            self.selections[2 if index == 0 else 0] = False

    def run_report(self, stdscr):
        """Display the existing read-only diagnostic report."""
        import subprocess
        from pathlib import Path

        config_dir = Path(
            os.path.expanduser(
                os.environ.get("PRINTER_CONFIG_DIR")
                or jws_installer.CONFIG_DIR
            )
        )
        core_script = Path(REPO_ROOT) / "software" / "macro_manager" / "jws_core.py"

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(core_script),
                    "--report",
                    "--config-dir",
                    str(config_dir),
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=60,
                check=False,
            )
            report_text = result.stdout or "(The report returned no output.)"
            if result.returncode != 0:
                report_text += (
                    f"\n\nReport command exited with status "
                    f"{result.returncode}.\n"
                )
        except Exception as exc:
            report_text = (
                "REPORT GENERATION FAILED\n\n"
                f"Could not run the diagnostic report:\n{exc}\n\n"
                "Check the repository path and Python environment."
            )

        lines = []
        width = max(20, stdscr.getmaxyx()[1] - 4)

        for raw_line in report_text.splitlines() or ["(Empty report.)"]:
            if not raw_line.strip():
                lines.append("")
                continue

            # Preserve the original indentation and indent wrapped lines.
            indent = raw_line[:len(raw_line) - len(raw_line.lstrip())]
            content = raw_line[len(indent):]

            wrapper = textwrap.TextWrapper(
                width=width,
                initial_indent=indent,
                subsequent_indent=indent + "    ",
                replace_whitespace=False,
                drop_whitespace=True,
                break_long_words=True,
                break_on_hyphens=False,
            )

            lines.extend(wrapper.wrap(content) or [indent])
            
        top = 0
        while True:
            h, w = stdscr.getmaxyx()
            page_height = max(1, h - 5)
            max_top = max(0, len(lines) - page_height)
            top = max(0, min(top, max_top))

            stdscr.clear()
            self.header(stdscr, w, "READ-ONLY DIAGNOSTIC REPORT")

            for row, line in enumerate(lines[top:top + page_height], start=2):
                self.safe_addstr(stdscr, row, 2, line)

            self.safe_addstr(
                stdscr,
                h - 2,
                1,
                "UP/DOWN: scroll | PgUp/PgDn: page | S: save | Q: return",
                curses.A_BOLD,
            )
            stdscr.refresh()

            key = stdscr.getch()

            if key in (ord("q"), ord("Q"), 27):
                return
            elif key in (curses.KEY_UP, ord("k")):
                top = max(0, top - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                top = min(max_top, top + 1)
            elif key == curses.KEY_PPAGE:
                top = max(0, top - page_height)
            elif key == curses.KEY_NPAGE:
                top = min(max_top, top + page_height)
            elif key == curses.KEY_HOME:
                top = 0
            elif key == curses.KEY_END:
                top = max_top
            elif key in (ord("s"), ord("S")):
                saved_path = None
                error_message = None
                created_path = None

                try:
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    for suffix in range(10000):
                        extra = "" if suffix == 0 else f"_{suffix}"
                        target = config_dir / (
                            f"jws_diagnostic_report_{stamp}{extra}.txt"
                        )
                        try:
                            with target.open("x", encoding="utf-8") as stream:
                                created_path = target
                                stream.write(report_text.rstrip("\n") + "\n")
                            saved_path = target
                            break
                        except FileExistsError:
                            continue

                    if saved_path is None:
                        raise FileExistsError(
                            "Could not find an unused report filename."
                        )
                except OSError as exc:
                    error_message = str(exc)
                    if created_path is not None and saved_path is None:
                        try:
                            created_path.unlink()
                        except OSError:
                            pass

                stdscr.clear()
                h, w = stdscr.getmaxyx()

                if saved_path is not None:
                    self.header(stdscr, w, "REPORT SAVED")
                    message = f"Saved report to:\n{saved_path}"
                else:
                    self.header(stdscr, w, "REPORT SAVE FAILED")
                    message = (
                        "Could not save the report:\n"
                        f"{error_message or 'An unexpected error occurred.'}"
                    )

                y = self.wrapped(stdscr, 2, 2, message, w - 4)
                self.safe_addstr(
                    stdscr,
                    min(y + 1, h - 2),
                    2,
                    "Press any key to return to the report.",
                    curses.A_BOLD,
                )
                stdscr.refresh()
                stdscr.getch()

    def draw_error_screen(self, stdscr, w, h, message):
        stdscr.clear()
        self.header(stdscr, w, "SETUP STOPPED — REVIEW DETAILS")
        y = self.wrapped(
            stdscr, 2, 2,
            "Something prevented setup from finishing:", w - 6, curses.A_BOLD
        )
        y = self.wrapped(stdscr, y + 1, 4, message, w - 8)
        y = self.wrapped(
            stdscr, y + 1, 2,
            "Preflight conflicts stop before deployment. If a later write failed, earlier "
            "atomic file updates may already be in place; backups are in jabberwocky_quarantine. "
            "Resolve the issue above before retrying.",
            w - 6,
        )
        self.safe_addstr(stdscr, y + 1, 2, "Press any key to exit.", curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()

    def draw_jwp_complete(self, stdscr, w, h):
        stdscr.clear()
        self.header(stdscr, w, "JWP INSTALL / UPDATE COMPLETE")
        y = self.wrapped(
            stdscr, 2, 2,
            "Local configuration files were updated. This does not verify Klipper startup "
            "or printer behavior; review the hardware pin and offsets before restarting.",
            w - 4,
        )
        y += 1
        for note in jws_installer.INSTALL_NOTES:
            y = self.wrapped(stdscr, y, 4, "- " + note, w - 8)
        self.safe_addstr(stdscr, min(y + 1, h - 2), 2, "Press any key to return.", curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()

    def draw_verification_pass(self, stdscr, w, h):
        stdscr.clear()
        self.header(stdscr, w, "DOUBLE-CHECKING THE RESULT")
        bridge = os.path.join(jws_installer.TARGET_DIST_DIR, jws_installer.BRIDGE_FILE)
        checks = (
            ("Dashboard page was created", os.path.isfile(jws_installer.MANAGER_PATH)),
            (
                "Sync tool is in place",
                os.path.isfile(
                    os.path.join(REPO_ROOT, "software", "macro_manager", "jws_core.py")
                ),
            ),
            ("Sync button (JABBERWOCKY_SYNC_NOW) installed", os.path.isfile(bridge)),
            ("printer.cfg still exists", os.path.isfile(jws_installer.PRINTER_CFG)),
        )
        self.safe_addstr(stdscr, 2, 2, "Checking each item:", curses.A_BOLD)
        for idx, (label, ok) in enumerate(checks):
            self.safe_addstr(
                stdscr, 4 + idx, 4,
                f"{label:<52}" + ("[ OK ]" if ok else "[ NOT DONE ]"),
                curses.A_BOLD if not ok else 0,
            )
            stdscr.refresh()
            self.pause(1.6)
        if not os.path.isfile(bridge):
            self.safe_addstr(
                stdscr, 9, 4,
                "The sync button is optional. You can still apply changes over SSH (see next pages)."
            )
        self.pause(1.5)
        self.safe_addstr(stdscr, 11, 2, "Press any key to see what was found...", curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()

    def draw_summary_screen(self, stdscr, w, h):
        s = jws_installer.LAST_SUMMARY
        stdscr.clear()
        self.header(stdscr, w, "WHAT WAS FOUND")
        rows = (
            ("Config files checked", s.get("files", 0)),
            ("Macros found", s.get("macros", 0)),
            ("Hardware sections listed (view only)", s.get("hardware", 0)),
            ("Switched-off lines taken over by the dashboard", s.get("adopted", 0)),
            ("Backup files found in your config folder", s.get("backups", 0)),
            ("Items to look at (warnings)", s.get("warnings", 0)),
            ("Problems that stop Klipper", s.get("blockers", 0)),
        )
        for i, (label, value) in enumerate(rows):
            self.safe_addstr(stdscr, 2 + i, 4, f"{label:<52}{value}")
            stdscr.refresh()
            self.pause(1.0)
        if s.get("blockers", 0):
            msg = (
                "Klipper will not start until the problems above are fixed. Open jwt_macro_manager.conf; "
                "the report at the bottom explains each one and what to do."
            )
        else:
            msg = (
                "Good news: nothing found that would stop Klipper from starting. "
                "The full report is at the bottom of jwt_macro_manager.conf."
            )
        y = self.wrapped(stdscr, 11, 2, msg, w - 6, curses.A_BOLD)
        self.safe_addstr(stdscr, y + 1, 2, "Press any key for the next steps...", curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()

    def draw_post_install_screen(self, stdscr, w, h):
        bridge = os.path.isfile(os.path.join(jws_installer.TARGET_DIST_DIR, jws_installer.BRIDGE_FILE))
        while True:
            stdscr.clear()
            self.header(stdscr, w, f"ALL DONE — NEXT STEPS (version {self.version_string})")
            steps = [
                "1. Press Q to leave this screen.",
                "2. In Mainsail, click RESTART (or type FIRMWARE_RESTART in the console).",
                "3. Open jwt_macro_manager.conf in the Mainsail config list. This is your dashboard.",
            ]
            if bridge:
                steps.append(
                    "4. To turn something off or on: change its 1 or 0, save, then type JABBERWOCKY_SYNC_NOW "
                    "in the console. Klipper restarts by itself if anything changed. "
                    "Saved changes are also picked up a few seconds after Klipper starts."
                )
            else:
                steps.append(
                    "4. To turn something off or on: change its 1 or 0, save, then run "
                    "python3 ~/Jabberwocky-APPS/software/macro_manager/jws_core.py "
                    "--sync over SSH and restart Klipper."
                )
            steps.append(
                "If Klipper will not start: read the report at the bottom of the dashboard, or run "
                "python3 ~/Jabberwocky-APPS/software/macro_manager/jws_core.py "
                "--report over SSH."
            )
            y = 2
            for step in steps:
                y = self.wrapped(stdscr, y, 2, step, w - 6) + 1
            notes = jws_installer.INSTALL_NOTES[:3]
            if notes:
                self.safe_addstr(stdscr, y, 2, "Notes:", curses.A_BOLD)
                y += 1
                for note in notes:
                    y = self.wrapped(stdscr, y, 4, "- " + note, w - 8)
            self.safe_addstr(
                stdscr, y + 1, 2,
                "Press Q to exit, or B to go back to the menu.", curses.A_BOLD
            )
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("b"), ord("B")):
                return "BACK"
            if key in (ord("q"), ord("Q"), 27):
                return "QUIT"

    def draw_action_menu(self, stdscr):
        curses.curs_set(0)
        current_row = 0
        message = ""
        run_row = len(self.options)
        report_row = 3
        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            bw = max(30, min(w - 6, 96))
            self.header(stdscr, w, f"JABBERWOCKY APPS SETUP {self.version_string}")
            self.safe_addstr(
                stdscr, 2, 2,
                "Welcome! This tool makes a simple on/off page for your printer's files and macros.",
                curses.A_BOLD,
            )
            self.safe_addstr(
                stdscr, 3, 2,
                "Use the arrow keys to move, SPACE to tick a choice, ENTER on START to begin."
            )
            for idx, (title, _desc, available) in enumerate(self.options):
                prefix = "> " if idx == current_row else "  "
                if idx == report_row:
                    # Report is an action, not a selectable setup option.
                    label = f"{prefix}    {idx + 1}. {title}"
                    attr = curses.A_BOLD if idx == current_row else 0
                else:
                    box = "[X]" if self.selections[idx] else "[ ]"
                    tail = "" if available else "  (coming soon)"
                    label = f"{prefix}{box} {idx + 1}. {title}{tail}"
                    attr = (
                        curses.A_BOLD if idx == current_row
                        else (curses.A_DIM if not available else 0)
                    )
                self.safe_addstr(stdscr, 5 + idx, 2, label, attr)
            self.safe_addstr(
                stdscr, 10, 2,
                ("> " if current_row == run_row else "  ") + "[ START ]",
                curses.A_REVERSE if current_row == run_row else curses.A_BOLD,
            )
            card = self.options[min(current_row, run_row - 1)][1]
            self.safe_addstr(stdscr, 12, 2, "About this choice:", curses.A_BOLD)
            y = 13
            for line in card:
                y = self.wrapped(stdscr, y, 4, line, bw - 4)
            if message:
                self.safe_addstr(stdscr, y + 1, 2, message, curses.A_BOLD)
            self.safe_addstr(
                stdscr, y + 3, 2,
                "Press Q to quit at any time. Nothing changes until you choose START."
            )
            stdscr.refresh()
            key = stdscr.getch()
            message = ""
            if key in (curses.KEY_UP, ord("k")):
                current_row = (current_row - 1) % (run_row + 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                current_row = (current_row + 1) % (run_row + 1)
            elif key == ord(" "):
                if current_row < run_row:
                    if current_row == report_row:
                        message = "Press ENTER to open the report."
                    elif self.options[current_row][2]:
                        self.toggle_selection(current_row)
                    else:
                        message = "That option is not available yet."
            elif key in (ord("\n"), curses.KEY_ENTER):
                if current_row == report_row:
                    self.run_report(stdscr)
                    continue
                if current_row < run_row:
                    if self.options[current_row][2]:
                        self.toggle_selection(current_row)
                    else:
                        message = "That option is not available yet."
                    continue
                if not (self.selections[0] or self.selections[2]):
                    message = "Select Macro Manager or Install / Update JWP before starting."
                    continue
                error = self.run_pipeline(stdscr)
                if error:
                    self.draw_error_screen(stdscr, w, h, error)
                    break
                if self.selections[0]:
                    self.draw_verification_pass(stdscr, w, h)
                    self.draw_summary_screen(stdscr, w, h)
                    if self.draw_post_install_screen(stdscr, w, h) == "QUIT":
                        break
                else:
                    self.draw_jwp_complete(stdscr, w, h)
            elif key in (ord("q"), ord("Q"), 27):
                break


def main():
    curses.wrapper(lambda s: JabberwockyTerminalUI().draw_action_menu(s))


if __name__ == "__main__":
    main()

# EOF
