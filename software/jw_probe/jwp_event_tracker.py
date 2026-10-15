# =====================================================================
# JABBERWOCKY PROBE 2.0 — READ-ONLY SWITCH EVENT TRACKER
# =====================================================================
import csv
import os
import time
from pathlib import Path


EVENT_HISTORY_SECONDS = 30.0
DEFAULT_TELEMETRY_FILE = "~/printer_data/config/jwp_calibration_profile.csv"


class JWPEventTracker:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.raw_pin = config.get("pin")
        self.clean_pin_name = (
            self.raw_pin.replace("^", "").replace("!", "").replace("~", "")
        )

        pins = self.printer.lookup_object("pins")
        pins.allow_multi_use_pin(self.clean_pin_name)

        buttons = self.printer.load_object(config, "buttons")
        buttons.register_buttons([self.raw_pin], self.button_callback)

        telemetry_file = config.get("telemetry_file", DEFAULT_TELEMETRY_FILE)
        self.telemetry_path = Path(os.path.expanduser(telemetry_file))

        self.event_count = 0
        self.probe_state = "unknown"
        self.last_trigger_time = None
        self.last_pulse_duration = None
        self.events_log = []

        self.gcode.register_command(
            "JWP_EVENT_STATUS", self.cmd_event_status, desc="Show captured JWP switch state"
        )
        self.gcode.register_command(
            "JWP_EVENT_LOG", self.cmd_event_log, desc="Show recent JWP switch events"
        )
        self.gcode.register_command(
            "JWP_COMMIT_POST_MORTEM",
            self.cmd_commit_post_mortem,
            desc="Append recent JWP events to the telemetry CSV",
        )

        self.gcode.respond_info(
            "JWP event tracker loaded in read-only capture mode; no printer response is enabled."
        )

    def _prune_event_history(self, eventtime):
        cutoff = eventtime - EVENT_HISTORY_SECONDS
        self.events_log[:] = [
            event for event in self.events_log if event["eventtime"] >= cutoff
        ]

    def button_callback(self, eventtime, state):
        self.event_count += 1
        state_is_valid = (
            type(state) in (int, float, bool)
            and state in (0, 1)
        )

        if not state_is_valid:
            self.probe_state = "unknown"
            self.last_trigger_time = None
            pulse_duration = None
        else:
            self.probe_state = "deployed" if not state else "retracted"
            pulse_duration = None
            if self.probe_state == "deployed":
                self.last_trigger_time = eventtime
            elif self.last_trigger_time is not None:
                pulse_duration = max(0.0, eventtime - self.last_trigger_time)
                self.last_pulse_duration = pulse_duration
                self.last_trigger_time = None

        self.events_log.append(
            {
                "eventtime": eventtime,
                "timestamp": time.strftime("%Y-%m-%d_%H:%M:%S"),
                "state": self.probe_state,
                "pulse_duration": pulse_duration,
                "response_executed": False,
                "telemetry_committed": False,
            }
        )
        self._prune_event_history(eventtime)

    def cmd_event_status(self, gcmd):
        self._prune_event_history(time.monotonic())
        gcmd.respond_info(
            "=== JWP EVENT TRACKER STATUS ===\n"
            "  Current Probe State: %s\n"
            "  Total Captured Events: %d\n"
            "  Recent In-Memory Events: %d\n"
            "  Automatic Response: disabled"
            % (self.probe_state.upper(), self.event_count, len(self.events_log))
        )

    def cmd_event_log(self, gcmd):
        self._prune_event_history(time.monotonic())
        if not self.events_log:
            gcmd.respond_info(
                "JWP event history is empty; recent events are held in memory for 30 seconds."
            )
            return

        lines = [
            "=== JWP RECENT EVENT HISTORY (VOLATILE, 30 SECONDS) ==="
        ]
        for event in self.events_log:
            pulse = event["pulse_duration"]
            pulse_text = "unknown" if pulse is None else "%.1f ms" % (pulse * 1000.0)
            lines.append(
                "%s state=%s pulse=%s response=not-executed"
                % (event["timestamp"], event["state"].upper(), pulse_text)
            )
        gcmd.respond_info("\n".join(lines))

    def cmd_commit_post_mortem(self, gcmd):
        self._prune_event_history(time.monotonic())
        user_label = gcmd.get_str("LABEL", "MANUAL_MARK")
        pending_events = [
            event for event in self.events_log if not event["telemetry_committed"]
        ]
        rows = [
            [
                event["timestamp"],
                "",
                "",
                (
                    ""
                    if event["pulse_duration"] is None
                    else "%.1f" % (event["pulse_duration"] * 1000.0)
                ),
                "",
                "PROBE_EVENT",
                "DETECTED_%s_NO_RESPONSE" % event["state"].upper(),
            ]
            for event in pending_events
        ]
        rows.append(
            [
                time.strftime("%Y-%m-%d_%H:%M:%S"),
                "",
                "",
                (
                    ""
                    if self.last_pulse_duration is None
                    else "%.1f" % (self.last_pulse_duration * 1000.0)
                ),
                "",
                "USER_MARK",
                user_label,
            ]
        )

        try:
            with self.telemetry_path.open(
                mode="a", encoding="utf-8", newline=""
            ) as telemetry_file:
                csv.writer(telemetry_file).writerows(rows)
        except (OSError, csv.Error) as exc:
            gcmd.error(
                "JWP telemetry write failed for %s: %s"
                % (self.telemetry_path, exc)
            )

        for event in pending_events:
            event["telemetry_committed"] = True
        gcmd.respond_info(
            "JWP: wrote %d captured events and manual mark to %s."
            % (len(pending_events), self.telemetry_path)
        )


def load_config(config):
    return JWPEventTracker(config)
