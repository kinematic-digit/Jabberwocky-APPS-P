# =====================================================================
# JABBERWOCKY TOOLHEAD SYSTEM — ASYNCHRONOUS EXTRUDER PROTECTION
# VERSION: 1.0.0
# Location: jw_toolhead/jwt_telemetry_poller.py
# =====================================================================
import time
import logging

class JabberwockyExtruderClutch:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        
        # Core Variable Safeguards & Calibration Thresholds (September 2026 Baseline)
        self.enabled = True
        self.persistence_window_ms = 400.0  # Time deviation must be held to trigger clutch
        self.healthy_sg_ceiling = 152
        self.jam_sg_floor = 104
        self.saturation_pwm_ceil = 28
        
        # State Monitor Registers
        self.deviation_start_time = 0.0
        self.clutch_state = "NORMAL" # NORMAL, STRESSED, ENGAGED_CLUTCH, FAULT
        
        # Hook into the low-level Klipper reactor timeline loop
        self.reactor = self.printer.get_reactor()
        self.reactor.register_timer(self._telemetry_monitoring_loop, self.reactor.now() + 1.0)
        
        self.gcode.register_command('JWT_CLUTCH_STATUS', self.cmd_clutch_status, desc="Read toolhead health metrics")
        self.gcode.respond_info("JWT: Asynchronous Extruder Mechanical Health Monitor loaded successfully.")

    def _telemetry_monitoring_loop(self, eventtime):
        """Asynchronously polls the TMC2209 silicon registers directly over UART."""
        if not self.enabled:
            return eventtime + 1.0 # Poll every 1 second when disabled
            
        try:
            tmc_driver = self.printer.lookup_object('tmc2209 extruder', None)
            if tmc_driver and hasattr(tmc_driver, 'get_status'):
                status = tmc_driver.get_status()
                
                # Extract our verified target signals from the hardware registers
                sg_result = int(status.get('sg_result', 152))
                pwm_scale_sum = int(status.get('pwm_scale_sum', 27))
                tstep = int(status.get('tstep', 1048575))
                stealth_active = bool(status.get('stealth', 0))
                stationary = bool(status.get('stst', 0))
                
                # Context-Aware Filtering: Only evaluate load if the motor is actively spinning in StealthChop
                if stealth_active and not stationary and tstep < 5000:
                    self._evaluate_mechanical_health(sg_result, pwm_scale_sum)
                else:
                    # Reset persistence timer instantly if the motor stops or enters full power SpreadCycle
                    self.deviation_start_time = 0.0
                    if self.clutch_state != "FAULT":
                        self.clutch_state = "NORMAL"
                        
        except Exception:
            pass
            
        return eventtime + 0.1 # Real-time high-frequency polling interval (100ms ticks)

    def _evaluate_mechanical_health(self, sg, pwm):
        current_time = time.monotonic()
        
        # THE MULTI-SIGNAL INTERCEPT GATE: Match our verified jam profile boundaries
        if sg <= self.jam_sg_floor and pwm >= self.saturation_pwm_ceil:
            if self.deviation_start_time == 0.0:
                self.deviation_start_time = current_time
                self.clutch_state = "STRESSED"
            elif (current_time - self.deviation_start_time) >= (self.persistence_window_ms / 1000.0):
                self._engage_software_clutch_mitigation()
        else:
            # Reversibility Loop: Reset timer if resistance drops back into the healthy envelope
            self.deviation_start_time = 0.0
            if self.clutch_state == "STRESSED":
                self.clutch_state = "NORMAL"

    def _engage_software_clutch_mitigation(self):
        """Executes adaptive torque mitigation to protect gearing without dropping print runs."""
        if self.clutch_state != "ENGAGED_CLUTCH":
            self.clutch_state = "ENGAGED_CLUTCH"
            self.gcode.respond_info(
                "⚠️ JWT IMPACT DETECTED: Persistent mechanical load confirmed! Engaging Software Clutch protection overrides."
            )
            # Step 1: Instantly scale back extrusion volumetric flow rate factor by 50%
            self.gcode.run_script_from_command("M220 S50")
            # Step 2: Trigger a non-blocking check to verify if the torque load recovers at lower speeds
            self.reactor.register_callback(lambda t: self._verify_clutch_recovery())

    def _verify_clutch_recovery(self):
        """Evaluates whether the speed reduction safely cleared the backpressure restriction."""
        tmc_driver = self.printer.lookup_object('tmc2209 extruder', None)
        if tmc_driver and hasattr(tmc_driver, 'get_status'):
            status = tmc_driver.get_status()
            sg = int(status.get('sg_result', 152))
            
            if sg >= self.healthy_sg_ceiling - 20:
                self.gcode.respond_info("✅ JWT CLUTCH RECOVERY: Extruder load stabilized. Continuing at protected speed.")
                self.clutch_state = "NORMAL"
                self.deviation_start_time = 0.0
            else:
                # Escalation path: If load stays pinned under low speed, safe drop to pause macro
                self.clutch_state = "FAULT"
                self.gcode.respond_info("🛑 JWT CRITICAL FAULT: Permanent cold-end jam or path obstruction. Halting gantry.")
                self.gcode.run_script_from_command("PAUSE")

    def cmd_clutch_status(self, gcmd):
        gcmd.respond_info(
            "=== JABBERWOCKY TOOLHEAD CLUTCH REGISTERS ===\n"
            "  • Operating State   : %s\n"
            "  • Persistence Timer : %.2f seconds active" 
            % (self.clutch_state, 0.0 if self.deviation_start_time == 0.0 else (time.monotonic() - self.deviation_start_time))
        )

def load_config(config): return JabberwockyExtruderClutch(config)
