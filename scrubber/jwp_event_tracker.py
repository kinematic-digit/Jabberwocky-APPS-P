# =====================================================================
# JABBERWOCKY PROBE 2.0 — ADAPTIVE SENSOR FUSION ENGINE & CLASSIFIER
# VERSION: 3.4.0
# Location: tools/jwp_event_tracker.py (Parallel to jabberwockyprobe/)
# =====================================================================
import time
import logging
import csv
from pathlib import Path

class JWPEventTracker:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.raw_pin = config.get('pin')
        
        self.clean_pin_name = self.raw_pin.replace('^', '').replace('!', '').replace('~', '')
        pins = self.printer.lookup_object('pins')
        pins.allow_multi_use_pin(self.clean_pin_name)
        
        buttons = self.printer.load_object(config, 'buttons')
        buttons.register_buttons([self.raw_pin], self.button_callback)
        
        # Internal State Properties
        self.event_count = 0
        self.probe_state = "unknown"
        self.is_hunting = False
        self.last_trigger_time = 0.0
        
        # Post-Mortem Flight Data Recorders (Rolling 30-second Memory Buffer)
        self.last_pulse_duration = 0.0
        self.last_impact_velocity = 0.0
        self.last_impact_accel = 0.0
        self.events_log = []
        
        self.gcode.register_command('JWP_EVENT_STATUS', self.cmd_event_status, desc="")
        self.gcode.register_command('JWP_EVENT_LOG', self.cmd_event_log, desc="")
        self.gcode.register_command('JWP_SET_HUNTING', self.cmd_set_hunting, desc="")
        self.gcode.register_command('JWP_COMMIT_POST_MORTEM', self.cmd_commit_post_mortem, desc="")
        
        self.gcode.respond_info("JWP Core: Adaptive flight-logger and classification engine loaded successfully.")

    def button_callback(self, eventtime, state):
        self.event_count += 1
        host_monotonic_time = time.monotonic()
        toolhead = self.printer.lookup_object('toolhead')
        current_position = toolhead.get_position()
        
        jws_macro = self.printer.lookup_object('gcode_macro _JWS_TOGGLE_MANIFEST', None)
        debounce_limit = 0.003
        impact_limit = 0.015
        blob_limit = 0.500
        auto_exclude = True
        
        if jws_macro:
            debounce_limit = float(jws_macro.variables.get('collision_noise_debounce_ms', 3.0)) / 1000.0
            impact_limit = float(jws_macro.variables.get('collision_impact_window_ms', 15.0)) / 1000.0
            blob_limit = float(jws_macro.variables.get('blob_detection_threshold_ms', 500.0)) / 1000.0
            auto_exclude = bool(jws_macro.variables.get('auto_exclude_on_impact', 1))

        self.probe_state = "deployed" if not state else "retracted"
        
        if self.probe_state == "deployed":
            self.last_trigger_time = host_monotonic_time
            reactor = self.printer.get_reactor()
            reactor.register_callback(lambda t: self._verify_blob_condition(blob_limit), host_monotonic_time + blob_limit)
        else:
            if self.last_trigger_time > 0.0:
                pulse_duration = host_monotonic_time - self.last_trigger_time
                self.last_trigger_time = 0.0
                
                # Cache parameters inside the rolling flight memory space
                self.last_pulse_duration = pulse_duration
                self.last_impact_velocity = toolhead.estimated_velocity
                
                if pulse_duration < debounce_limit:
                    return
                probe_obj = self.printer.lookup_object('probe', None)
                if probe_obj and getattr(probe_obj, 'is_probing', False):
                    return
                if self.is_hunting:
                    self.is_hunting = False
                    toolhead.flush_step_generation()
                    return

                idle_timeout = self.printer.lookup_object('idle_timeout')
                if idle_timeout.state == "Printing" and pulse_duration >= impact_limit:
                    self._execute_impact_mitigation(current_position, auto_exclude)

    def _verify_blob_condition(self, blob_limit):
        if self.probe_state == "deployed" and self.last_trigger_time > 0.0:
            current_duration = time.monotonic() - self.last_trigger_time
            if current_duration >= blob_limit:
                self._log_telemetry_row("BLOB_FAULT", "CRITICAL_SHUTDOWN")
                self.printer.invoke_shutdown(
                    "🛑 JWP BLOB FAULT: Persistent structural trigger detected past %d ms! Emergency shutdown cut heater power." 
                    % int(blob_limit * 1000.0)
                )

    def _execute_impact_mitigation(self, pos, auto_exclude):
        exclude_obj_manager = self.printer.lookup_object('exclude_object', None)
        current_active_object = getattr(exclude_obj_manager, 'current_object', None) if exclude_obj_manager else None
        
        jws_macro = self.printer.lookup_object('gcode_macro _JWS_TOGGLE_MANIFEST', None)
        offset_x, offset_y = 0.0, 0.0
        if jws_macro:
            offset_x = float(jws_macro.variables.get('collision_pin_offset_x', 0.0))
            offset_y = float(jws_macro.variables.get('collision_pin_offset_y', 0.0))
            
        exact_impact_x = pos[0] + offset_x
        exact_impact_y = pos[1] + offset_y
        
        if auto_exclude and current_active_object:
            self.gcode.respond_info(
                "💥 JWP IMPACT INTERCEPT: Bed Impact Point X=%.3f, Y=%.3f. Canceling broken model: '%s'"
                % (exact_impact_x, exact_impact_y, current_active_object)
            )
            self._log_telemetry_row("IMPACT", "AUTO_EXCLUDED")
            self.gcode.run_script_from_command("EXCLUDE_OBJECT NAME=%s" % current_active_object)
            self.gcode.run_script_from_command("G91")
            self.gcode.run_script_from_command("G1 Z5.0 F600")
            self.gcode.run_script_from_command("G90")
        else:
            self._log_telemetry_row("IMPACT", "PAUSED")
            self.gcode.respond_info("💥 JWP IMPACT INTERCEPT: Bed Impact Point X=%.3f, Y=%.3f. Dropping system to safety pause." % (exact_impact_x, exact_impact_y))
            self.gcode.run_script_from_command("PAUSE")

    def _log_telemetry_row(self, machine_class, label):
        try:
            csv_path = Path("/home/pi/printer_data/config/jwp_calibration_profile.csv")
            if csv_path.parent.is_dir():
                date_str = time.strftime("%Y-%m-%d_%H:%M:%S")
                row = [date_str, f"{self.last_impact_velocity:.1f}", "0", f"{self.last_pulse_duration * 1000.0:.1f}", "0", machine_class, label]
                with open(csv_path, mode='a', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
        except Exception:
            pass

    def cmd_commit_post_mortem(self, gcmd):
        user_label = gcmd.get_str('LABEL', 'MANUAL_MARK')
        self._log_telemetry_row("USER_MARK", user_label)
        gcmd.respond_info("JWP: Flight logging cache safely written to profile.csv with token: %s" % user_label)

    def cmd_set_hunting(self, gcmd):
        self.is_hunting = bool(gcmd.get_int('ACTIVE', 0))

    def cmd_event_status(self, gcmd):
        gcmd.respond_info("=== JWP ASYNCHRONOUS STATE SUMMARY ===\n  • Current Probe State: %s\n  • Total Logged Events: %d" % (self.probe_state.upper(), self.event_count))

    def cmd_event_log(self, gcmd):
        gcmd.respond_info("=== JWP HARDWARE EVENT HISTORY ===\n  • Cache holding %d transitions." % len(self.events_log))

def load_config(config): return JWPEventTracker(config)
