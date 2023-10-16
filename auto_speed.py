# Find your printers max speed before losing steps
#
# Copyright (C) 2023 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.
import math
from time import perf_counter

class AttemptWrapper:
    def __init__(self):
        self.min: float = None
        self.max: float = None
        self.accuracy: float = None
        self.iterations: int = 1
        self.max_missed: int = None
        self.travel: float = None
        self.dist: float = None
        self.func: callable = None
        self.axis: str = ""
        self.accel: float = None
        self.veloc: float = None

class ResultsWrapper:
    def __init__(self):
        self.name: str = ""
        self.duration: float = None
        self.vals: dict = {}

    def derate(self, derate):
        vList = []
        newVals = {}
        for k, v in self.vals.items():
            newVals[f"max_{k}"] = v
            newVals[k] = v * derate
            vList.append(newVals[k])
        self.vals = newVals
        self.vals["rec"] = min(vList)

class AutoSpeed:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()

        self.x = config.getboolean('x',   default=False)
        self.y = config.getboolean('y',   default=False)
        self.diag_x = config.getboolean('diag_x',   default=True)
        self.diag_y = config.getboolean('diag_y',   default=True)

        self.z              = config.getfloat('z', default=None)
        self.margin         = config.getfloat('margin', default=20.0, above=0.0)

        self.settling_home   = config.getboolean('settling_home',   default=True)
        self.max_missed      = config.getfloat(  'max_missed',      default=1.0)
        self.endstop_samples = config.getint(    'endstop_samples', default=3, minval=2)

        self.accel_min  = config.getfloat('accel_min',  default=1000.0, above=0.0)
        self.accel_max  = config.getfloat('accel_max',  default=50000.0, above=self.accel_min)
        self.accel_dist = config.getfloat('accel_dist', default=0.0, above=0.0)
        self.accel_ittr = config.getint(  'accel_ittr', default=1)
        self.accel_accu = config.getfloat('accel_accu', default=500.0, above=0.0)

        self.veloc_min  = config.getfloat('velocity_min',  default=50.0, above=0.0)
        self.veloc_max  = config.getfloat('velocity_max',  default=5000.0, above=self.veloc_min)
        self.veloc_dist = config.getfloat('velocity_dist', default=0.0, above=0.0)
        self.veloc_ittr = config.getint(  'velocity_ittr', default=1)
        self.veloc_accu = config.getfloat('velocity_accu', default=50.0, above=0.0)

        self.derate = config.getfloat('derate', default=0.8, above=0.0, below=1.0)
        self.derate_accel = config.getfloat('derate_accel', self.derate, above=0.0, below=1.0)
        self.derate_veloc = config.getfloat('derate_velocity', self.derate, above=0.0, below=1.0)

        self.validate_margin       = config.getfloat('validate_margin', default=self.margin, above=0.0)
        self.validate_inner_margin = config.getfloat('validate_inner_margin', default=20.0, above=0.0)
        self.validate_iterations   = config.getint(  'validate_iterations', default=50, minval=1)

        self.toolhead = None
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("homing:home_rails_end", self.handle_home_rails_end)

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('AUTO_SPEED',
                                    self.cmd_AUTO_SPEED,
                                    desc=self.cmd_AUTO_SPEED_help)
        self.gcode.register_command('AUTO_SPEED_VELOCITY',
                                    self.cmd_AUTO_SPEED_VELOCITY,
                                    desc=self.cmd_AUTO_SPEED_VELOCITY_help)
        self.gcode.register_command('AUTO_SPEED_ACCEL',
                                    self.cmd_AUTO_SPEED_ACCEL,
                                    desc=self.cmd_AUTO_SPEED_ACCEL_help)
        
        self.gcode.register_command('AUTO_SPEED_VALIDATE',
                                    self.cmd_AUTO_SPEED_VALIDATE,
                                    desc=self.cmd_AUTO_SPEED_VALIDATE_help)
        
        self.level = None
        
        self.steppers = {}
        self.axes = {}
    
    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.th_accel = self.toolhead.max_accel
        self.th_veloc = self.toolhead.max_velocity

        # Find and define leveling method
        if self.printer.lookup_object("screw_tilt_adjust", None) is not None:
            self.level = "STA"
        elif self.printer.lookup_object("z_tilt", None) is not None:
            self.level= "ZT"
        elif self.printer.lookup_object("quad_gantry_level", None) is not None:
            self.level = "QGL"
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
            if self.steppers.get("z", None) is not None:
                if self.z is None: # If z isn't defined, use 10% of the maximum z height
                    self.z = self.steppers["z"][1] * .1

    cmd_AUTO_SPEED_help = ("Automatically find your printer's maximum acceleration/velocity")
    def cmd_AUTO_SPEED(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        validate = gcmd.get_int('VALIDATE', 1, minval=0, maxval=1)

        self._prepare(gcmd)
        start = perf_counter()
        accel_results = self.cmd_AUTO_SPEED_ACCEL(gcmd)
        veloc_results = self.cmd_AUTO_SPEED_VELOCITY(gcmd)

        respond = f"AUTO SPEED found recommended acceleration and velocity after {perf_counter() - start:.2f}s\n"
        for axis in ["x", "y", "diag_x", "diag_y"]:
            aR = accel_results.vals.get(axis, None)
            vR = veloc_results.vals.get(axis, None)
            if aR is not None or vR is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max:"
                if aR is not None:
                    respond += f" a{aR:.0f}"
                if vR is not None:
                    respond += f" v{vR:.0f}"
                respond += "\n"

        respond += f"Recommended accel: {accel_results.vals['rec']:.0f}\n"
        respond += f"Recommended velocity: {veloc_results.vals['rec']:.0f}\n"
        self.gcode.respond_info(respond)
        
        if validate:
            gcmd._params["ACCEL"] = accel_results.vals['rec']
            gcmd._params["VELOCITY"] = veloc_results.vals['rec']
            self.cmd_AUTO_SPEED_VALIDATE(gcmd)
    
    cmd_AUTO_SPEED_ACCEL_help = ("Automatically find your printer's maximum acceleration")
    def cmd_AUTO_SPEED_ACCEL(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        x    = gcmd.get_int("X",    self.x, minval=0, maxval=1)
        y    = gcmd.get_int("Y",    self.y, minval=0, maxval=1)
        diag_x = gcmd.get_int("DIAG_X", self.diag_x, minval=0, maxval=1)
        diag_y = gcmd.get_int("DIAG_Y", self.diag_y, minval=0, maxval=1)

        margin         = gcmd.get_float("MARGIN", self.margin, above=0.0)
        derate         = gcmd.get_float('DERATE', self.derate, above=0.0, below=1.0)
        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)

        accel_min  = gcmd.get_float('ACCEL_MIN', self.accel_min, above=0.0)
        accel_max  = gcmd.get_float('ACCEL_MAX', self.accel_max, above=accel_min)
        accel_dist = gcmd.get_float('ACCEL_DIST', self.accel_dist, above=0.0)
        accel_ittr = gcmd.get_int(  'ACCEL_ITTR', self.accel_ittr, minval=0)
        accel_accu = gcmd.get_float('ACCEL_ACCU', self.accel_accu, above=0.0)

        veloc = gcmd.get_float('VELOCITY', 0.0, above=0.0)

        respond = "AUTO SPEED finding maximum acceleration on"
        if x == 1:
            respond += " X,"
        if y == 1:
            respond += " Y,"
        if diag_x == 1:
            respond += " DIAG X,"
        if diag_y == 1:
            respond += " DIAG Y,"
        self.gcode.respond_info(respond[:-1])

        aw = AttemptWrapper()
        aw.max_missed = max_missed
        aw.iterations = accel_ittr
        aw.min = accel_min
        aw.max  = accel_max
        aw.dist  = accel_dist
        aw.accuracy = accel_accu
        aw.veloc = veloc
        accel_results = self.find_max(aw, margin, self._attempt_accel, x, y, diag_x, diag_y)
        accel_results.name = "acceleration"
        respond = f"AUTO SPEED found maximum acceleration after {accel_results.duration:.2f}s\n"
        for axis in ["x", "y", "diag_x", "diag_y"]:
            if accel_results.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {accel_results.vals[axis]:.0f}\n"
        respond += f"\n"

        accel_results.derate(derate)
        respond += f"Recommended values:\n"
        for axis in ["x", "y", "diag_x", "diag_y"]:
            if accel_results.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {accel_results.vals[axis]:.0f}\n"
        respond += f"Reommended acceleration: {accel_results.vals['rec']:.0f}\n"

        self.gcode.respond_info(respond)
        return accel_results

    cmd_AUTO_SPEED_VELOCITY_help = ("Automatically find your printer's maximum velocity")
    def cmd_AUTO_SPEED_VELOCITY(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        x    = gcmd.get_int("X",    self.x, minval=0, maxval=1)
        y    = gcmd.get_int("Y",    self.y, minval=0, maxval=1)
        diag_x = gcmd.get_int("DIAG_X", self.diag_x, minval=0, maxval=1)
        diag_y = gcmd.get_int("DIAG_Y", self.diag_y, minval=0, maxval=1)

        margin         = gcmd.get_float("MARGIN", self.margin, above=0.0)
        derate         = gcmd.get_float('DERATE', self.derate, above=0.0, below=1.0)
        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)

        veloc_min  = gcmd.get_float('VELOCITY_MIN', self.veloc_min, above=0.0)
        veloc_max  = gcmd.get_float('VELOCITY_MAX', self.veloc_max, above=veloc_min)
        veloc_dist = gcmd.get_float('VELOCITY_DIST', self.veloc_dist, above=0.0)
        veloc_ittr = gcmd.get_int(  'VELOCITY_ITTR', self.accel_ittr, minval=0)
        veloc_accu = gcmd.get_float('VELOCITY_ACCU', self.veloc_accu, above=0.0)

        accel = gcmd.get_float('ACCEL', 0.0, above=0.0)

        respond = "AUTO SPEED finding maximum velocity on"
        if x == 1:
            respond += " X,"
        if y == 1:
            respond += " Y,"
        if diag_x == 1:
            respond += " DIAG X,"
        if diag_y == 1:
            respond += " DIAG Y,"
        self.gcode.respond_info(respond[:-1])

        aw = AttemptWrapper()
        aw.max_missed = max_missed
        aw.iterations = veloc_ittr
        aw.min = veloc_min
        aw.max  = veloc_max
        aw.dist  = veloc_dist
        aw.accuracy  = veloc_accu
        aw.accel = accel
        veloc_results = self.find_max(aw, margin, self._attempt_veloc, x, y, diag_x, diag_y)
        veloc_results.name = "velocity"
        respond = f"AUTO SPEED found maximum velocity after {veloc_results.duration:.2f}s\n"
        for axis in ["x", "y", "diag_x", "diag_y"]:
            if veloc_results.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {veloc_results.vals[axis]:.0f}\n"
        respond += "\n"

        veloc_results.derate(derate)
        respond += f"Recommended values\n"
        for axis in ["x", "y", "diag_x", "diag_y"]:
            if veloc_results.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {veloc_results.vals[axis]:.0f}\n"
        respond += f"Recommended velocity: {veloc_results.vals['rec']:.0f}\n"

        self.gcode.respond_info(respond)
        return veloc_results
    
    cmd_AUTO_SPEED_VALIDATE_help = ("Validate your printer's maximum acceleration/velocity don't miss steps")
    def cmd_AUTO_SPEED_VALIDATE(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        
        max_missed   = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)
        margin       = gcmd.get_float('VALIDATE_MARGIN', default=self.validate_margin, above=0.0)
        small_margin = gcmd.get_float('VALIDATE_INNER_MARGIN', default=self.validate_inner_margin, above=0.0)
        iterations   = gcmd.get_int('VALIDATE_ITERATIONS', default=self.validate_iterations, minval=1)
        
        accel = gcmd.get_float('ACCEL', default=self.toolhead.max_accel, above=0.0) 
        veloc = gcmd.get_float('VELOCITY', default=self.toolhead.max_velocity, above=0.0)
        
        respond = f"AUTO SPEED validating over {iterations} iterations\n"
        respond += f"Acceleration: {accel:.0f}\n"
        respond += f"Velocity: {veloc:.0f}"
        self.gcode.respond_info(respond)
        self._set_velocity(veloc, accel)
        valid, duration, missed_x, missed_y = self._validate(veloc, iterations, margin, small_margin, max_missed)

        respond = f"AUTO SPEED validated results after {duration:.2f}s\n"
        respond += f"Valid: {valid}\n"
        respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f}"
        self.gcode.respond_info(respond)
        return valid

    # -------------------------------------------------------
    #
    #     Internal Methods
    #
    # -------------------------------------------------------

    def _prepare(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        z               = gcmd.get_float("Z", self.z)

        start = perf_counter()
        # Level the printer if it's not leveled
        self._level(gcmd)
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], z], self.th_veloc)

        self._variance(gcmd)
       
        return perf_counter() - start
    
    def _level(self, gcmd):
        level = gcmd.get_int('LEVEL', 1, minval=0, maxval=1)

        if level == 0:
            return
        if self.level is None:
            return
        
        lookup = None
        name = None
        if self.level == "STA":
            lookup = "screw_tilt_adjust"
            name = "SCREWS_TILT_CALCULATE"
        elif self.level == "ZT":
            lookup = "z_tilt"
            name = "Z_TILT_ADJUST"
        elif self.level == "QGL":
            lookup = "quad_gantry_level"
            name = "QUAD_GANTRY_LEVEL"
        else:
            raise gcmd.error(f"Unknown leveling method '{self.level}'.")
        lm = self.printer.lookup_object(lookup)
        if lm.z_status.applied is False:
            self.gcode.respond_info(f"AUTO SPEED leveling with {name}...")
            self.gcode._process_commands([name], False)
            if lm.z_status.applied is False:
                raise gcmd.error(f"Failed to level printer! Please manually ensure your printer is level.")
                
    def _variance(self, gcmd):
        variance        = gcmd.get_int('VARIANCE', 1, minval=0, maxval=1)

        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)
        endstop_samples = gcmd.get_int('ENDSTOP_SAMPLES', self.endstop_samples, minval=2)

        settling_home   = gcmd.get_int("SETTLING_HOME", default=self.settling_home, minval=0, maxval=1)

        if variance == 0:
            return
        
        self.gcode.respond_info(f"AUTO SPEED checking endstop variance over {endstop_samples} samples")
        
        if settling_home:
            self.toolhead.wait_moves()
            self._home(True, True, False)

        # Check endstop variance
        endstops = self._endstop_variance(endstop_samples, x=True, y=True)

        x_max = max(endstops["x"])
        y_max = max(endstops["y"])
        self.gcode.respond_info(f"AUTO SPEED endstop variance:\nMissed X:{x_max:.2f} steps, Y:{y_max:.2f} steps")
        
        if x_max >= max_missed or y_max >= max_missed:
            raise gcmd.error(f"Please increase MAX_MISSED (currently {max_missed}), or tune your steppers/homing macro.")


    def find_max(self, aw: AttemptWrapper, margin, func: callable, x=True, y=True, diag_x=True, diag_y = True):
        rw = ResultsWrapper()
        start = perf_counter()
        if diag_x:
            if aw.dist == 0.0:
                aw.dist = min([self.axes["y"]["center"] - margin, self.axes["x"]["center"] - margin])
            aw.axis = "diag_x"
            aw.travel = self._calc_travel(aw.dist, aw.dist)
            aw.func = self._check_diag_x
            rw.vals[aw.axis] = func(aw)
        if diag_y:
            if aw.dist == 0.0:
                aw.dist = min([self.axes["y"]["center"] - margin, self.axes["x"]["center"] - margin])
            aw.axis = "diag_y"
            aw.travel = self._calc_travel(aw.dist, aw.dist)
            aw.func = self._check_diag_y
            rw.vals[aw.axis] = func(aw)
        if x:
            if aw.dist == 0.0:
                aw.dist = (self.axes["x"]["center"] - margin)
            aw.axis = "x"
            aw.travel = aw.dist * 2
            aw.func = self._check_x
            rw.vals[aw.axis] = func(aw)
        if y:
            if aw.dist == 0.0:
                aw.dist = (self.axes["y"]["center"] - margin)
            aw.axis = "y"
            aw.travel = aw.dist * 2
            aw.func = self._check_y
            rw.vals[aw.axis] = func(aw)
        rw.duration = perf_counter() - start
        return rw
    
    def _attempt_accel(self, aw: AttemptWrapper):
        #self.gcode.respond_info("AUTO SPEED checking accel...")
        measured_accel = None
        tries = 0
        measuring = True
        m_min = aw.min
        m_max = aw.max
        accel = m_min + (m_max-m_min) // 3
        veloc = aw.veloc
        while measuring:
            start = perf_counter()
            tries += 1
            if aw.veloc == 0.0:
                veloc = self._calc_velocity(accel, aw.travel)/2.5
            self._set_velocity(veloc, accel)
            #self.gcode.respond_info(f"Trying min: {m_min:.0f}, max:{m_max:.0f} at {accel:.0f}")
            start_steps = self._pretest(x=True, y=True)
            check_start = perf_counter()
            aw.func(veloc, aw.dist, aw.iterations)
            self.toolhead.wait_moves()
            duration = perf_counter() - check_start
            valid, missed_x, missed_y = self._posttest(start_steps, aw.max_missed, x=True, y=True)
            respond = f"AUTO SPEED acceleration {aw.axis} measurement {tries} ({perf_counter() - start:.2f}s)\n"
            respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f} at a{accel:.0f}/v{veloc:.0f} over {duration:.2f}s"
            self.gcode.respond_info(respond)
            if measured_accel is not None:
                if accel > measured_accel - aw.accuracy and accel < measured_accel + aw.accuracy:
                    measuring = False
            measured_accel = accel
            if valid:
                m_min = accel - aw.accuracy
            else:
                m_max = accel
            accel = (m_min + m_max)/2
        return measured_accel
    
    def _attempt_veloc(self, aw: AttemptWrapper):
        #self.gcode.respond_info("AUTO SPEED checking velocity...")
        measured_veloc = None
        tries = 0
        measuring = True
        m_min = aw.min
        m_max = aw.max
        veloc = m_min + (m_max-m_min) // 3
        accel = aw.accel
        while measuring:
            start = perf_counter()
            tries += 1
            if aw.accel == 0.0:
                accel = self._calc_accel(veloc, aw.travel)*2.5
            self._set_velocity(veloc, accel)
            #self.gcode.respond_info(f"Trying min: {m_min:.0f}, max:{m_max:.0f} at {accel:.0f}")
            start_steps = self._pretest(x=True, y=True)
            check_start = perf_counter()
            aw.func(veloc, aw.dist, aw.iterations)
            self.toolhead.wait_moves()
            duration = perf_counter() - check_start
            valid, missed_x, missed_y = self._posttest(start_steps, aw.max_missed, x=True, y=True)
            respond = f"AUTO SPEED velocity {aw.axis} measurement {tries} ({perf_counter() - start:.2f}s)\n"
            respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f} at v{veloc:.0f}/a{accel:.0f} over {duration:.2f}s"
            self.gcode.respond_info(respond)
            if measured_veloc is not None:
                if veloc > measured_veloc - aw.accuracy and veloc < measured_veloc + aw.accuracy:
                    measuring = False
            measured_veloc = veloc
            if valid:
                m_min = veloc - aw.accuracy
            else:
                m_max = veloc
            veloc = (m_min + m_max)/2
        return measured_veloc

    def _pretest(self, x=True, y=True):
        self.toolhead.wait_moves()
        self._home(x, y, False)
        self.toolhead.wait_moves()

        start_steps = self._get_steps()
        return start_steps
    
    def _posttest(self, start_steps, max_missed, x=True, y=True):
        self.toolhead.wait_moves()
        self._home(x, y, False)
        self.toolhead.wait_moves()

        stop_steps = self._get_steps()

        step_dif = {
            "x": abs(start_steps["x"] - stop_steps["x"]),
            "y": abs(start_steps["y"] - stop_steps["y"])
        }

        missed_x = step_dif['x']/self.steppers['x'][2]
        missed_y = step_dif['y']/self.steppers['y'][2]
        valid = True
        if missed_x > max_missed:
            valid = False
        if missed_y > max_missed:
            valid = False
        return valid, missed_x, missed_y
    
    def _check_x(self, speed: float, dist: float, iterations: int = 1):
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
        for _ in range(iterations):
            self._move([self.axes["x"]["center"] + dist, None, None], speed)
            self._move([self.axes["x"]["center"], None, None], speed)
            self._move([self.axes["x"]["center"] - dist, None, None], speed)

    def _check_y(self, speed: float, dist: float, iterations: int = 1):
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
        for _ in range(iterations):
            self._move([None, self.axes["y"]["center"]  + dist, None], speed)
            self._move([None, self.axes["y"]["center"], None], speed)
            self._move([None, self.axes["y"]["center"]  - dist, None], speed)

    def _check_diag_x(self, speed: float, dist: float, iterations: int = 1): # B stepper
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
        for _ in range(iterations):
            self._move([self.axes["x"]["center"] + dist, self.axes["y"]["center"] + dist, None], speed)
            self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
            self._move([self.axes["x"]["center"] - dist, self.axes["y"]["center"] - dist, None], speed)
    
    def _check_diag_y(self, speed: float, dist: float, iterations: int = 1): # A stepper
        self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
        for _ in range(iterations):
            self._move([self.axes["x"]["center"] + dist, self.axes["y"]["center"] - dist, None], speed)
            self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], speed)
            self._move([self.axes["x"]["center"] - dist, self.axes["y"]["center"] + dist, None], speed)

    def _validate(self, speed, iterations, margin, small_margin, max_missed):
        pos = {
            "x": {
                "min": self.axes["x"]["min"] + margin,
                "max": self.axes["x"]["max"] - margin,
                "center_min": self.axes["x"]["center"] - (small_margin/2),
                "center_max": self.axes["x"]["center"] + (small_margin/2),
            },
            "y": {
                "min": self.axes["y"]["min"] + margin,
                "max": self.axes["y"]["max"] - margin,
                "center_min": self.axes["y"]["center"] - (small_margin/2),
                "center_max": self.axes["y"]["center"] + (small_margin/2),
            }
        }
        self.toolhead.wait_moves()
        self._home(True, True, False)
        start_steps = self._get_steps()
        start = perf_counter()
        for _ in range(iterations):
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

        self.toolhead.wait_moves()
        duration = perf_counter() - start

        self._home(True, True, False)
        stop_steps = self._get_steps()


        step_dif = {
            "x": abs(start_steps["x"] - stop_steps["x"]),
            "y": abs(start_steps["y"] - stop_steps["y"])
        }

        missed_x = step_dif['x']/self.steppers['x'][2]
        missed_y = step_dif['y']/self.steppers['y'][2]
        valid = True
        if missed_x > max_missed:
            valid = False
        if missed_y > max_missed:
            valid = False
        return valid, duration, missed_x, missed_y

    def _endstop_variance(self, samples: int, x=True, y=True):
        variance = {
            "x": [],
            "y": [],
            "steps": {
                "x": None,
                "y": None
            }
        }
        for _ in range(0, samples):
            #self._move([self.axes["x"]["center"], self.axes["y"]["center"], None], veloc_start)
            self.toolhead.wait_moves()
            self._home(x, y, False)
            steps = self._get_steps()
            #self.gcode.respond_info(f"Got {steps = }")

            if x:
                if variance["steps"]["x"] is not None:
                    x_dif = abs(variance["steps"]["x"] - steps["x"])
                    missed_x = x_dif/self.steppers['x'][2]
                    variance["x"].append(missed_x)
                variance["steps"]["x"] = steps["x"]
            if y:
                if variance["steps"]["y"] is not None:
                    y_dif = abs(variance["steps"]["y"] - steps["y"])
                    missed_y = y_dif/self.steppers['y'][2]
                    variance["y"].append(missed_y)
                variance["steps"]["y"] = steps["y"]
        return variance

    def _move(self, coord, speed):
        self.toolhead.manual_move(coord, speed)

    def _home(self, x=True, y=True, z=True):
        prevAccel = self.toolhead.max_accel
        prevVeloc = self.toolhead.max_velocity
        self._set_velocity(self.th_veloc, self.th_accel)
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
        self._set_velocity(prevVeloc, prevAccel)

    def _get_steps(self):
        kin = self.toolhead.get_kinematics()
        steppers = kin.get_steppers()
        pos = {}
        for s in steppers:
            s_name = s.get_name()
            if s_name in ["stepper_x", "stepper_y", "stepper_z"]:
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