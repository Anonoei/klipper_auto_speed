# Find your printers max speed before losing steps
#
# Copyright (C) 2023 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.
import math
from time import perf_counter

class AutoSpeed:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()

        self.z = config.getfloat('z', default=50)
        self.margin = config.getfloat('margin', default=20.0, above=0.0)
        self.pattern_margin = config.getfloat('pattern_margin', default=20.0, above=0.0)

        self.settling_home = config.getboolean('settling_home', default=True)
        self.max_missed = config.getfloat('max_missed', default=1.0)
        self.endstop_samples = config.getint('endstop_samples', default=3, minval=2)

        self.test_iterations = config.getint('test_iterations', default=2, minval=1)
        self.test_attempts   = config.getint('test_attempts', default=2, minval=0)
        self.stress_iterations = config.getint('stress_iterations', default=50, minval=1)

        self.accel_start = config.getfloat('accel_start', default=1000.0, above=0.0)
        self.accel_stop = config.getfloat('accel_stop', default=50000.0, above=self.accel_start)
        self.accel_step = config.getfloat('accel_step', default=1000.0, above=0.0, below=self.accel_stop)

        self.veloc_start = config.getfloat('velocity_start', default=100.0, above=0.0)
        self.veloc_stop = config.getfloat('velocity_stop',   default=5000.0, above=self.veloc_start)
        self.veloc_step = config.getfloat('velocity_step',   default=50.0, above=0.0, below=self.veloc_stop)

        self.toolhead = None
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("homing:home_rails_end", self.handle_home_rails_end)

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('AUTO_SPEED',
                                    self.cmd_AUTO_SPEED,
                                    desc=self.cmd_AUTO_SPEED_help)
        
        self.level = None
        
        self.steppers = {}
        self.axes = {}
    
    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.th_accel = self.toolhead.max_accel
        self.th_veloc = self.toolhead.max_velocity

        # Find and define leveling method
        if self.printer.lookup_object("quad_gantry_level", None) is not None:
            self.level = "QGL"
        elif self.printer.lookup_object("screw_tilt_adjust", None) is not None:
            self.level = "STA"
        else:
            self.level = None

    def handle_home_rails_end(self, homing_state, rails):
        # Get rail min and max values
        # Get x/y stepper microsteps
        if not len(self.steppers.keys()) == 3:
            for rail in rails:
                pos_min, pos_max = rail.get_range()
                for stepper in rail.get_steppers():
                    name = stepper._name
                    #microsteps = (stepper._steps_per_rotation / full_steps / gearing)
                    if name in ["stepper_x", "stepper_y", "stepper_z"]:
                        config = self.printer.lookup_object('configfile').status_raw_config[name]
                        microsteps = int(config["microsteps"])
                        self.steppers[name[-1]] = [pos_min, pos_max, microsteps]

            if self.steppers.get("x", None) is not None:
                self.axes["x"] = {
                    "min": self.steppers["x"][0],
                    "max": self.steppers["x"][1],
                    "center": (self.steppers["x"][0] + self.steppers["x"][1]) / 2
                }
            if self.steppers.get("y", None) is not None:
                self.axes["y"] = {
                    "min": self.steppers["y"][0],
                    "max": self.steppers["y"][1],
                    "center": (self.steppers["y"][0] + self.steppers["y"][1]) / 2
                }

    cmd_AUTO_SPEED_help = ("Automatically calculate your printer's maximum acceleration/velocity")
    def cmd_AUTO_SPEED(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        z = gcmd.get_float("Z", self.z)
        margin = gcmd.get_float("MARGIN", self.margin, above=0.0)
        pattern_margin = gcmd.get_float('PATTERN_MARGIN', self.pattern_margin, above=0.0)

        settling_home = gcmd.get_int("SETTLING_HOME", default=self.settling_home, minval=0, maxval=1)
        max_missed = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)
        endstop_samples = gcmd.get_int('ENDSTOP_SAMPLES', self.endstop_samples, minval=2)

        test_iterations = gcmd.get_int("TEST_ITERATIONS", self.test_iterations, minval=1)
        test_attempts = gcmd.get_int("TEST_ATTEMPTS", self.test_attempts, minval=0)
        stress_iterations = gcmd.get_int("STRESS_ITERATIONS", self.stress_iterations, minval=1)

        accel_start = gcmd.get_float('ACCEL_START', self.accel_start, above=0.0)
        accel_stop = gcmd.get_float('ACCEL_STOP', self.accel_stop, above=accel_start)
        accel_step = gcmd.get_float('ACCEL_STEP', self.accel_step, above=0.0, below=accel_stop)

        veloc_start = gcmd.get_float('VELOCITY_START', self.veloc_start, above=0.0)
        veloc_stop = gcmd.get_float('VELOCITY_STOP', self.veloc_stop, above=veloc_start)
        veloc_step = gcmd.get_float('VELOCITY_STEP', self.veloc_step, above=0.0, below=veloc_stop)

        # Level the printer if it's not leveled
        if self.level is not None:
            lookup = None
            name = None
            if self.level == "QGL":
                lookup = "quad_gantry_level"
                name = "QUAD_GANTRY_LEVEL"
            elif self.level == "STA":
                lookup = "screw_tilt_adjust"
                name = "Z_TILT_ADJUST"
            else:
                raise gcmd.error(f"Unknown leveling method '{self.level}'.")
            level = self.printer.lookup_object(lookup)
            if level.z_status.applied is False:
                self.gcode.respond_info(f"AUTO SPEED leveling with {name}...")
                self.gcode._process_commands([name], False)
                if level.z_status.applied is False:
                    raise gcmd.error(f"Failed to level printer! Please manually ensure your printer is level.")
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], z], self.th_veloc)

        if settling_home:
            self.toolhead.wait_moves()
            self._home(True, True, False)

        # Check endstop variance
        endstops = {
            "x": [],
            "y": [],
            "steps": {
                "x": None,
                "y": None
            }
        }
        self.gcode.respond_info(f"AUTO SPEED checking endstop variance over {endstop_samples} samples")
        for step in range(0, endstop_samples):
            #self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], veloc_start)
            self.toolhead.wait_moves()
            self._home(True, True, False)
            steps = self._get_steps()
            #self.gcode.respond_info(f"Got {steps = }")

            if endstops["steps"]["x"] is not None:
                x_dif = abs(endstops["steps"]["x"] - steps["x"])
                y_dif = abs(endstops["steps"]["y"] - steps["y"])

                missed_x = x_dif/self.steppers['x'][2]
                missed_y = y_dif/self.steppers['y'][2]
                endstops["x"].append(missed_x)
                endstops["y"].append(missed_y)
                #self.gcode.respond_info(f"AUTO SPEED endstop variance measurement {step + 1}\nMissed X:{missed_x:.2f} steps, Y:{missed_y:.2f} steps")
            endstops["steps"]["x"] = steps["x"]
            endstops["steps"]["y"] = steps["y"]

        x_max = max(endstops["x"])
        y_max = max(endstops["y"])
        self.gcode.respond_info(f"AUTO SPEED endstop variance:\nMissed X:{x_max:.2f} steps, Y:{y_max:.2f} steps")
        
        del endstops
        if x_max >= max_missed or y_max >= max_missed:
            raise gcmd.error(f"Please increase MAX_MISSED (currently {max_missed}), or tune your steppers/homing macro.")

        # Perform tests
        accel_count = int((accel_stop - accel_start) / accel_step) + 1
        veloc_count = int((veloc_stop - veloc_start) / veloc_step) + 1

        positions = {
            "x": {
                "min": self.axes["x"]["min"] + margin,
                "max": self.axes["x"]["max"] - margin,
                "center_min": self.axes["x"]["center"] - (pattern_margin/2),
                "center_max": self.axes["x"]["center"] + (pattern_margin/2),
            },
            "y": {
                "min": self.axes["y"]["min"] + margin,
                "max": self.axes["y"]["max"] - margin,
                "center_min": self.axes["y"]["center"] - (pattern_margin/2),
                "center_max": self.axes["y"]["center"] + (pattern_margin/2),
            }
        }

        pos_travel = self._calc_travel(x=(positions["x"]["max"] - positions["x"]["min"]),
                                       y=(positions["y"]["max"] - positions["y"]["min"]))

        # Find acceleration maximum
        measured_accel = None
        measured_accel_veloc = None
        attempt = 1
        for step in range(0, accel_count):
            accel = accel_start + (accel_step * step)
            veloc = self._calc_velocity(accel, pos_travel)/math.log10(accel)
            while attempt < test_attempts:
                valid, duration, missed_x, missed_y = self._test(veloc, accel, positions, test_iterations, max_missed)
                respond = f"AUTO SPEED acceleleration measurement {step+1} attempt {attempt}\n"
                respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f} at a{accel:.0f}/v{veloc:.0f} over {duration:.2f}s"
                self.gcode.respond_info(respond)
                if valid:
                    break
                if missed_x > max_missed*10 or missed_y > max_missed*10:
                    attempt = test_attempts
                    break
                attempt += 1
            if attempt == test_attempts:
                break
            measured_accel = step
            measured_accel_veloc = veloc
        accel_max = accel_start + (accel_step * measured_accel)
        self.gcode.respond_info(f"AUTO SPEED found maximum acceleration {accel_max:.0f}, at velocity {measured_accel_veloc:.0f}")

        # Find velocity maximum
        measured_veloc = None
        measured_veloc_accel = None
        attempt = 1
        for step in range(0, veloc_count):
            veloc = veloc_start + (veloc_step * step)
            accel = self._calc_accel(veloc, pos_travel)*4
            while attempt < test_attempts:
                valid, duration, missed_x, missed_y = self._test(veloc, accel, positions, test_iterations, max_missed)
                respond = f"AUTO SPEED velocity measurement {step+1} attempt {attempt}\n"
                respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f} at v{veloc:.0f}/a{accel:.0f} over {duration:.2f}s"
                self.gcode.respond_info(respond)
                if valid:
                    break
                if missed_x > max_missed*10 or missed_y > max_missed*10:
                    attempt = test_attempts
                    break
                attempt += 1
            if attempt == test_attempts:
                break
            measured_veloc = step
            measured_veloc_accel = accel
        veloc_max = veloc_start + (veloc_step * measured_veloc)
        self.gcode.respond_info(f"AUTO SPEED found maximum velocity {veloc_max:.0f}, at accel {measured_veloc_accel:.0f}")

        # Perform stress test
        for step in range(0, 100, 1):
            accel = accel_start + (accel_step * measured_accel)
            veloc = veloc_start + (veloc_step * measured_veloc)
            valid, duration, missed_x, missed_y = self._test(veloc, accel, positions, stress_iterations, max_missed)
            
            respond = f"AUTO SPEED stress measurement {step + 1}\n"
            respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f} at a{accel:.0f}/v{veloc:.0f} over {duration:.2f}s"
            self.gcode.respond_info(respond)
            
            measured_accel -= step
            measured_veloc -= step
            
            if valid:
                break

        accel_used = accel_start + (accel_step * (measured_accel))
        veloc_used = veloc_start + (veloc_step * (measured_veloc))

        results = "AUTO SPEED Results:\n"
        results += f"Recomended maximum acceleration: {accel_used:.0f}\n"
        results += f"Recomended maximum velocity: {veloc_used:.0f}\n"
        self.gcode.respond_info(results)
        return
    
    def _test(self, veloc: float, accel: float, positions, iterations: int, max_missed: float):
        self._set_velocity(veloc, accel)
        #self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], veloc)

        self.toolhead.wait_moves()
        self._home(True, True, False)
        start_steps = self._get_steps()
        start = perf_counter()
        for _ in range(iterations):
            self._pattern_move(positions, veloc)
        #self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], veloc)
        self.toolhead.wait_moves()
        duration = perf_counter() - start

        self._home(True, True, False)
        stop_steps = self._get_steps()


        step_dif = {
            "x": abs(start_steps["x"] - stop_steps["x"]),
            "y": abs(start_steps["y"] - stop_steps["y"])
        }

        #self.gcode.respond_info(f"AUTO SPEED got pos\nStart: {start_steps}\nStop: {stop_steps}\nDifference: {step_dif}")

        missed_x = step_dif['x']/self.steppers['x'][2]
        missed_y = step_dif['y']/self.steppers['y'][2]
        valid = True
        if missed_x > max_missed:
            valid = False
        if missed_y > max_missed:
            valid = False
        return valid, duration, missed_x, missed_y

    def _pattern_move(self, pos, speed):
        # Large pattern diagonals
        self._move([pos["x"]["min"], pos["y"]["min"], None], speed)
        self._move([pos["x"]["max"], pos["y"]["max"], None], speed)
        self._move([pos["x"]["min"], pos["y"]["min"], None], speed)
        self._move([pos["x"]["max"], pos["y"]["min"], None], speed)
        self._move([pos["x"]["min"], pos["y"]["max"], None], speed)
        self._move([pos["x"]["max"], pos["y"]["min"], None], speed)

        # Large pattern box
        self._move([pos["x"]["min"], pos["y"]["min"], None], speed)
        self._move([pos["x"]["min"], pos["y"]["max"], None], speed)
        self._move([pos["x"]["max"], pos["y"]["max"], None], speed)
        self._move([pos["x"]["max"], pos["y"]["min"], None], speed)

        # Small pattern diagonals
        self._move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
        self._move([pos["x"]["center_max"], pos["y"]["center_max"], None], speed)
        self._move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
        self._move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)
        self._move([pos["x"]["center_min"], pos["y"]["center_max"], None], speed)
        self._move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)

        # Small pattern box
        self._move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
        self._move([pos["x"]["center_min"], pos["y"]["center_max"], None], speed)
        self._move([pos["x"]["center_max"], pos["y"]["center_max"], None], speed)
        self._move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)

    def _move(self, coord, speed):
        self.toolhead.manual_move(coord, speed)

    def _home(self, x=True, y=True, z=True):
        command = ["G28"]
        if x:
            command[-1] += " X0"
        if y:
            command[-1] += " Y0"
        if z:
            command[-1] += " Z0"
        #self.gcode.respond_info(f"AUTO SPEED running {command[-1]}")
        self.gcode._process_commands(command, False)
        self.toolhead.wait_moves()

    def _get_steps(self):
        kin = self.toolhead.get_kinematics()
        steppers = kin.get_steppers()
        pos = {}
        for s in steppers:
            s_name = s.get_name()
            if s_name in ["stepper_x", "stepper_y"]:
                pos[s_name[-1]] = s.get_mcu_position()
        return pos
    
    def _set_velocity(self, velocity: float, accel: float):
        #self.gcode.respond_info(f"AUTO SPEED setting limits to VELOCITY={velocity} ACCEL={accel}")
        self.toolhead.max_velocity = velocity
        self.toolhead.max_accel = accel
        self.toolhead.requested_accel_to_decel = accel/2
        self.toolhead._calc_junction_deviation()

    def _calc_velocity(self, accel: float, travel: float):
        #self.gcode.respond_info(f"Calculating velocity using accel {accel:.2f} over {travel:.2f} distance")
        return math.sqrt(travel/accel)*accel
    
    def _calc_accel(self, veloc: float, travel: float):
        #self.gcode.respond_info(f"Calculating accel using velocity {veloc:.2f} over {travel:.2f} distance")
        return veloc**2/travel
    
    def _calc_travel(self, x: float, y: float):
        return math.sqrt(x**2 + y**2)


def load_config(config):
    return AutoSpeed(config)