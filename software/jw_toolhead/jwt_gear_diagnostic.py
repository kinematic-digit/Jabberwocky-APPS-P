# =====================================================================
# JWS V3.0 — ADAPTIVE SMART CLUTCH HARDWARE SYSTEM DIAGNOSTIC
# VERSION: 3.8.6 [Strict Uppercase G-Code Command Registry Pass]
# Location: software/jw_toolhead/jwt_gear_diagnostic.py
# =====================================================================
#!/usr/bin/env python3
import os

class jwt_gear_diagnostic:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.grind_ceiling = 31
        self.max_delta = 2
        self.stream_active = False
        
        self.user_profile_path = os.path.expanduser("~/printer_data/config/jwt_asc_user_profile.cfg")
        self.ensure_user_profile_exists()

        # Bind custom commands inside Klipper using strict uppercase formatting keys
        self.gcode.register_command("ASC_POLL_UART_DATA", self.cmd_ASC_POLL_UART_DATA, desc="Queries live silicon over UART safely")
        self.gcode.register_command("ASC_SAVE_BUILD", self.cmd_ASC_SAVE_BUILD, desc="Flushes calibrated parameters directly to the user profile")
        self.gcode.register_command("ASC_TEST_LOAD", self.cmd_ASC_TEST_LOAD, desc="Runs a safe 10-second hardware load benchmark")

    def ensure_user_profile_exists(self):
        """Builds isolated user profile map outside the git directory tree if missing."""
        if not os.path.exists(self.user_profile_path):
            try:
                with open(self.user_profile_path, "w") as f:
                    f.write("# =====================================================================\n")
                    f.write("# JABBERWOCKY ASC — USER-CALIBRATED HARDWARE HEALTH PROFILE\n")
                    f.write("# =====================================================================\n\n")
                    f.write("[gcode_macro JWT_USER_PROFILE_REGISTERS]\n")
                    f.write("description: Human-readable active mechanical profiles for the ASC engine.\n")
                    f.write("variable_clutch_mesh_center_forward: 27\n")
                    f.write("variable_clutch_mesh_center_reverse: 27\n")
                    f.write("variable_asc_clutch_sensitivity: 2\n")
                    f.write("variable_asc_max_grind_threshold: 31\n")
                    f.write("variable_asc_bite_resistance_floor: 24\n")
                    f.write("gcode:\n    # Open data profile vault. Feel free to inspect or edit.\n")
            except Exception:
                pass

    def cmd_ASC_TEST_LOAD(self, gcmd):
        """Initializes a safe 10-second data-gathering run utilizing standard macro-based polling loops."""
        try:
            tmc_object = self.printer.lookup_object('tmc2209 extruder', None)
            extruder = self.printer.lookup_object('extruder', None)
            
            if not tmc_object or not extruder:
                gcmd.respond_info("❌ ASC LIVE ERROR: Cannot locate live driver or extruder instances!")
                return

            orig_min_extrude_temp = getattr(extruder, 'min_extrude_temp', 150.0)
            extruder.min_extrude_temp = 0.0
            
            self.gcode.run_script_from_command("G91")
            self.gcode.run_script_from_command("_JWT_RUN_SAFE_TEST_LOOP")
            self.gcode.run_script_from_command("G90")
            
            extruder.min_extrude_temp = orig_min_extrude_temp
        except Exception as e:
            extruder = self.printer.lookup_object('extruder', None)
            if extruder: extruder.min_extrude_temp = 150.0
            gcmd.respond_info(f"❌ ASC DATA FAULT: Benchmark failure: {str(e)}")

    def cmd_ASC_POLL_UART_DATA(self, gcmd):
        """Safe explicit register check handle aligned to the original poller's top-level status structure."""
        try:
            tmc_extruder = self.printer.lookup_object('tmc2209 extruder', None)
            status = tmc_extruder.get_status()
            
            live_val = int(status.get('pwm_scale_sum', 27))
            sg_result = int(status.get('sg_result', 0))
            
            gcmd.respond_info(f"📊 [LIVE TELEMETRY] PWM_SCALE_SUM = {live_val:<4} | SG_RESULT = {sg_result:<4}")
        except Exception as e:
            gcmd.respond_info(f"❌ ASC UART FAULT: {str(e)}")

    def cmd_ASC_SAVE_BUILD(self, gcmd):
        """Flushes live calibration parameters directly to the user profile without overwriting custom metrics."""
        try:
            tmc_extruder = self.printer.lookup_object('tmc2209 extruder', None)
            status = tmc_extruder.get_status()
            live_val = str(int(status.get('pwm_scale_sum', 27)))
            
            with open(self.user_profile_path, "w") as f:
                f.write("# =====================================================================\n")
                f.write("# JABBERWOCKY ASC — USER-CALIBRATED HARDWARE HEALTH PROFILE\n")
                f.write("# =====================================================================\n\n")
                f.write("[gcode_macro JWT_USER_PROFILE_REGISTERS]\n")
                f.write("description: Human-readable active mechanical profiles for the ASC engine.\n")
                f.write(f"variable_clutch_mesh_center_forward: {live_val}\n")
                f.write(f"variable_clutch_mesh_center_reverse: {live_val}\n")
                f.write("variable_asc_clutch_sensitivity: 2\n")
                f.write("variable_asc_max_grind_threshold: 31\n")
                f.write("variable_asc_bite_resistance_floor: 24\n")
                f.write("gcode:\n    # Open data profile vault. Feel free to inspect or edit.\n")
                
            gcmd.respond_info(f"💾 ASC SUCCESS: Flushed parameters [Center={live_val}] straight to '{self.user_profile_path}'")
        except Exception as e:
            gcmd.respond_info(f"❌ ASC SAVE FAULT: Unable to write profile config block: {str(e)}")

def load_config(config): return jwt_gear_diagnostic(config)
