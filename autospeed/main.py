# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

import os
from time import perf_counter
import datetime as dt

from .funcs import calculate_graph, calculate_accel, calculate_velocity
from .move import Move, MoveX, MoveY, MoveZ, MoveDiagX, MoveDiagY
from .wrappers import ResultsWrapper, AttemptWrapper

class AutoSpeed:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.load_object(config, 'gcode_move')

        self.printer_kinematics = self.config.getsection("printer").get("kinematics")
        self.isolate_xy = self.printer_kinematics == 'cartesian' or self.printer_kinematics == 'corexz'

        self.valid_axes = ["x", "y", "diag_x", "diag_y", "z"]
        self.axes = self._parse_axis(config.get('axis', 'x, y' if self.isolate_xy else 'diag_x, diag_y'))

        self.default_axes = ''
        
        for axis in self.axes:
            self.default_axes += f"{axis},"
        self.default_axes = self.default_axes[:-1]

        self.margin          = config.getfloat(  'margin',          default=20.0, above=0.0)
        self.settling_home   = config.getboolean('settling_home',   default=True)
        self.max_missed      = config.getfloat(  'max_missed',      default=1.0)
        self.endstop_samples = config.getint(    'endstop_samples', default=3, minval=2)

        self.accel_min  = config.getfloat('accel_min',  default=1000.0, above=1.0)
        self.accel_max  = config.getfloat('accel_max',  default=100000.0, above=self.accel_min)
        self.accel_accu = config.getfloat('accel_accu', default=0.05, above=0.0, below=1.0)
        self.scv        = config.getfloat('scv', default=5, above=1.0, below=50)

        self.veloc_min  = config.getfloat('velocity_min',  default=50.0, above=1.0)
        self.veloc_max  = config.getfloat('velocity_max',  default=5000.0, above=self.veloc_min)
        self.veloc_accu = config.getfloat('velocity_accu', default=0.05, above=0.0, below=1.0)

        self.derate = config.getfloat('derate', default=0.8, above=0.0, below=1.0)

        self.validate_margin       = config.getfloat('validate_margin', default=self.margin, above=0.0)
        self.validate_inner_margin = config.getfloat('validate_inner_margin', default=20.0, above=0.0)
        self.validate_iterations   = config.getint(  'validate_iterations', default=50, minval=1)

        for path in ( # Could be problematic if neither of these paths work
            os.path.dirname(self.printer.start_args['log_file']),
            os.path.expanduser('~/printer_data/config')
            ):
            if os.path.exists(path):
                results_default = path
        self.results_dir = config.get('results_dir',default=results_default)

        self.toolhead = None
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("homing:home_rails_end", self.handle_home_rails_end)

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
        self.gcode.register_command('AUTO_SPEED_GRAPH',
                                    self.cmd_AUTO_SPEED_GRAPH,
                                    desc=self.cmd_AUTO_SPEED_GRAPH_help)
        self.gcode.register_command('X_ENDSTOP_ACCURACY',
                                    self.cmd_X_ENDSTOP_ACCURACY,
                                    desc=self.cmd_AUTO_SPEED_GRAPH_help)
        self.gcode.register_command('Y_ENDSTOP_ACCURACY',
                                    self.cmd_Y_ENDSTOP_ACCURACY,
                                    desc=self.cmd_AUTO_SPEED_GRAPH_help)
        self.gcode.register_command('Z_ENDSTOP_ACCURACY',
                                    self.cmd_Z_ENDSTOP_ACCURACY,
                                    desc=self.cmd_AUTO_SPEED_GRAPH_help)
        
        self.level = None
        
        self.steppers = {}
        self.axis_limits = {}
    
    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        # Reduce speed/acceleration for positioning movement
        self.th_accel = self.toolhead.max_accel/2
        self.th_veloc = self.toolhead.max_velocity/2
        self.th_scv = self.toolhead.square_corner_velocity

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
        # Get axis min/max values
        # Get stepper microsteps
        if not len(self.steppers.keys()) == 3:
            for rail in rails:
                pos_min, pos_max = rail.get_range()
                for stepper in rail.get_steppers():
                    name = stepper._name
                    # microsteps = (stepper._steps_per_rotation / full_steps / gearing)
                    if name in ["stepper_x", "stepper_y", "stepper_z"]:
                        config = self.printer.lookup_object('configfile').status_raw_config[name]
                        microsteps = int(config["microsteps"])
                        homing_retract_dist = float (config["homing_retract_dist"])
                        second_homing_speed = float(config["second_homing_speed"])
                        self.steppers[name[-1]] = [pos_min, pos_max, microsteps, homing_retract_dist, second_homing_speed]
            
            if self.steppers.get("x", None) is not None:
                self.axis_limits["x"] = {
                    "min": self.steppers["x"][0],
                    "max": self.steppers["x"][1],
                    "center": (self.steppers["x"][0] + self.steppers["x"][1]) / 2,
                    "dist": self.steppers["x"][1] - self.steppers["x"][0],
                    "home": self.gcode_move.homing_position[0]
                }
            if self.steppers.get("y", None) is not None:
                self.axis_limits["y"] = {
                    "min": self.steppers["y"][0],
                    "max": self.steppers["y"][1],
                    "center": (self.steppers["y"][0] + self.steppers["y"][1]) / 2,
                    "dist": self.steppers["y"][1] - self.steppers["y"][0],
                    "home": self.gcode_move.homing_position[1]
                }
            if self.steppers.get("z", None) is not None:
                self.axis_limits["z"] = {
                    "min": self.steppers["z"][0],
                    "max": self.steppers["z"][1],
                    "center": (self.steppers["z"][0] + self.steppers["z"][1]) / 2,
                    "dist": self.steppers["z"][1] - self.steppers["z"][0],
                    "home": self.gcode_move.homing_position[2]
                }

    cmd_AUTO_SPEED_help = ("Automatically find your printer's maximum acceleration/velocity")
    def cmd_AUTO_SPEED(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        validate = gcmd.get_int('VALIDATE', 0, minval=0, maxval=1)

        self._prepare(gcmd) # Make sure the printer is level, [check endstop variance]

        move_z = gcmd.get_int('Z', None)
        if move_z is not None:
            self._move([None, None, move_z], self.th_veloc)

        start = perf_counter()
        accel_results = self.cmd_AUTO_SPEED_ACCEL(gcmd)
        veloc_results = self.cmd_AUTO_SPEED_VELOCITY(gcmd)

        respond = f"AUTO SPEED found recommended acceleration and velocity after {perf_counter() - start:.2f}s\n"
        for axis in self.valid_axes:
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
        axes = self._parse_axis(gcmd.get("AXIS", self._axis_to_str(self.axes)))

        margin         = gcmd.get_float("MARGIN", self.margin, above=0.0)
        derate         = gcmd.get_float('DERATE', self.derate, above=0.0, below=1.0)
        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)

        accel_min  = gcmd.get_float('ACCEL_MIN', self.accel_min, above=1.0)
        accel_max  = gcmd.get_float('ACCEL_MAX', self.accel_max, above=accel_min)
        accel_accu = gcmd.get_float('ACCEL_ACCU', self.accel_accu, above=0.0, below=1.0)

        veloc = gcmd.get_float('VELOCITY', 1.0, above=1.0)
        scv =   gcmd.get_float('SCV', self.scv, above=1.0)

        respond = "AUTO SPEED finding maximum acceleration on"
        for axis in axes:
            respond += f" {axis.upper().replace('_', ' ')},"
        self.gcode.respond_info(respond[:-1])
        
        rw = ResultsWrapper()
        start = perf_counter()
        for axis in axes:
            aw = AttemptWrapper()
            aw.type = "accel"
            aw.accuracy = accel_accu
            aw.max_missed = max_missed
            aw.margin = margin

            aw.min = accel_min
            aw.max  = accel_max
            aw.veloc = veloc
            aw.scv = scv
            self.init_axis(aw, axis)
            rw.vals[aw.axis] = self.binary_search(aw)
        rw.duration = perf_counter() - start

        rw.name = "acceleration"
        respond = f"AUTO SPEED found maximum acceleration after {rw.duration:.2f}s\n"
        for axis in self.valid_axes:
            if rw.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {rw.vals[axis]:.0f}\n"
        respond += f"\n"

        rw.derate(derate)
        respond += f"Recommended values:\n"
        for axis in self.valid_axes:
            if rw.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {rw.vals[axis]:.0f}\n"
        respond += f"Recommended acceleration: {rw.vals['rec']:.0f}\n"

        self.gcode.respond_info(respond)
        return rw

    cmd_AUTO_SPEED_VELOCITY_help = ("Automatically find your printer's maximum velocity")
    def cmd_AUTO_SPEED_VELOCITY(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        axes = self._parse_axis(gcmd.get("AXIS", self._axis_to_str(self.axes)))

        margin         = gcmd.get_float("MARGIN", self.margin, above=0.0)
        derate         = gcmd.get_float('DERATE', self.derate, above=0.0, below=1.0)
        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)

        veloc_min  = gcmd.get_float('VELOCITY_MIN', self.veloc_min, above=1.0)
        veloc_max  = gcmd.get_float('VELOCITY_MAX', self.veloc_max, above=veloc_min)
        veloc_accu = gcmd.get_float('VELOCITY_ACCU', self.veloc_accu, above=0.0, below=1.0)

        accel = gcmd.get_float('ACCEL', 1.0, above=1.0)
        scv =   gcmd.get_float('SCV', self.scv, above=1.0)

        respond = "AUTO SPEED finding maximum velocity on"
        for axis in axes:
            respond += f" {axis.upper().replace('_', ' ')},"
        self.gcode.respond_info(respond[:-1])

        rw = ResultsWrapper()
        start = perf_counter()
        for axis in axes:
            aw = AttemptWrapper()
            aw.type = "velocity"
            aw.accuracy  = veloc_accu
            aw.max_missed = max_missed
            aw.margin = margin

            aw.min = veloc_min
            aw.max  = veloc_max
            aw.accel = accel
            aw.scv = scv
            self.init_axis(aw, axis)
            rw.vals[aw.axis] = self.binary_search(aw)
        rw.duration = perf_counter() - start

        rw.name = "velocity"
        respond = f"AUTO SPEED found maximum velocity after {rw.duration:.2f}s\n"
        for axis in self.valid_axes:
            if rw.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {rw.vals[axis]:.0f}\n"
        respond += "\n"

        rw.derate(derate)
        respond += f"Recommended values\n"
        for axis in self.valid_axes:
            if rw.vals.get(axis, None) is not None:
                respond += f"| {axis.replace('_', ' ').upper()} max: {rw.vals[axis]:.0f}\n"
        respond += f"Recommended velocity: {rw.vals['rec']:.0f}\n"

        self.gcode.respond_info(respond)
        return rw
    
    cmd_AUTO_SPEED_VALIDATE_help = ("Validate your printer's acceleration/velocity don't miss steps")
    def cmd_AUTO_SPEED_VALIDATE(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        
        max_missed   = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)
        margin       = gcmd.get_float('VALIDATE_MARGIN', default=self.validate_margin, above=0.0)
        small_margin = gcmd.get_float('VALIDATE_INNER_MARGIN', default=self.validate_inner_margin, above=0.0)
        iterations   = gcmd.get_int('VALIDATE_ITERATIONS', default=self.validate_iterations, minval=1)
        
        accel = gcmd.get_float('ACCEL', default=self.toolhead.max_accel, above=0.0) 
        veloc = gcmd.get_float('VELOCITY', default=self.toolhead.max_velocity, above=0.0)
        scv =   gcmd.get_float('SCV', default=self.toolhead.square_corner_velocity, above=1.0)

        respond = f"AUTO SPEED validating over {iterations} iterations\n"
        respond += f"Acceleration: {accel:.0f}\n"
        respond += f"Velocity: {veloc:.0f}\n"
        respond += f"SCV: {scv:.0f}"
        self.gcode.respond_info(respond)
        self._set_velocity(veloc, accel, scv)
        valid, duration, missed_x, missed_y = self._validate(veloc, iterations, margin, small_margin, max_missed)

        respond = f"AUTO SPEED validated results after {duration:.2f}s\n"
        respond += f"Valid: {valid}\n"
        respond += f"Missed X {missed_x:.2f}, Y {missed_y:.2f}"
        self.gcode.respond_info(respond)
        return valid
    
    cmd_AUTO_SPEED_GRAPH_help = ("Graph your printer's maximum acceleration at given velocities")
    def cmd_AUTO_SPEED_GRAPH(self, gcmd):
        import matplotlib.pyplot as plt # this may fail if matplotlib isn't installed
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")
        axes = self._parse_axis(gcmd.get("AXIS", self._axis_to_str(self.axes)))

        margin         = gcmd.get_float("MARGIN", self.margin, above=0.0)
        derate         = gcmd.get_float('DERATE', self.derate, above=0.0, below=1.0)
        max_missed      = gcmd.get_float('MAX_MISSED', self.max_missed, above=0.0)

        veloc_min  = gcmd.get_float('VELOCITY_MIN', 200.0, above=0.0)
        veloc_max  = gcmd.get_float('VELOCITY_MAX', 700.0, above=veloc_min)
        veloc_div  = gcmd.get_int(  'VELOCITY_DIV', 5, minval=0)

        accel_accu = gcmd.get_float('ACCEL_ACCU', 0.05, above=0.0, below=1.0)

        accel_min_slope = gcmd.get_int('ACCEL_MIN_SLOPE', 100, minval=0)
        accel_max_slope = gcmd.get_int('ACCEL_MAX_SLOPE', 1800, minval=accel_min_slope)

        veloc_step = (veloc_max - veloc_min)//(veloc_div - 1)
        velocs = [round((v * veloc_step) + veloc_min) for v in range(0, veloc_div)]
        respond = "AUTO SPEED graphing maximum accel from velocities on"
        for axis in axes:
            respond += f" {axis.upper().replace('_', ' ')},"
        respond = respond[:-1] + "\n"
        respond += f"V_MIN: {veloc_min}, V_MAX: {veloc_max}, V_STEP: {veloc_step}\n"
        self.gcode.respond_info(respond)

        aw = AttemptWrapper()
        aw.type = "graph"
        aw.accuracy = accel_accu
        aw.max_missed = max_missed
        aw.margin = margin
        for axis in axes:
            start = perf_counter()
            self.init_axis(aw, axis)
            accels = []
            accel_mins = []
            accel_maxs = []
            for veloc in velocs:
                self.gcode.respond_info(f"AUTO SPEED graph {aw.axis} - v{veloc}")
                aw.veloc = veloc
                aw.min = round(calculate_graph(veloc, accel_min_slope))
                aw.max = round(calculate_graph(veloc, accel_max_slope))
                accel_mins.append(aw.min)
                accel_maxs.append(aw.max)
                accels.append(self.binary_search(aw))
            plt.plot(velocs, accels, 'go-', label='measured')
            plt.plot(velocs, [a*derate for a in accels], 'g-', label='derated')
            plt.plot(velocs, accel_mins, 'b--', label='min')
            plt.plot(velocs, accel_maxs, 'r--', label='max')
            plt.legend(loc='upper right')
            plt.title(f"Max accel at velocity on {aw.axis} to {int(accel_accu*100)}% accuracy")
            plt.xlabel("Velocity")
            plt.ylabel("Acceleration")
            filepath = os.path.join(
                self.results_dir,
                f"AUTO_SPEED_GRAPH_{dt.datetime.now():%Y-%m-%d_%H:%M:%S}_{aw.axis}.png"
            )
            self.gcode.respond_info(f"Velocs: {velocs}")
            self.gcode.respond_info(f"Accels: {accels}")
            self.gcode.respond_info(f"AUTO SPEED graph found max accel on {aw.axis} after {perf_counter() - start:.0f}s\nSaving graph to {filepath}")
            os.makedirs(self.results_dir, exist_ok=True)
            plt.savefig(filepath, bbox_inches='tight')
            plt.close()

    # -------------------------------------------------------
    #
    #     Internal Helpers
    #
    # -------------------------------------------------------
    def _prepare(self, gcmd):
        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        start = perf_counter()
        # Level the printer if it's not leveled
        self._level(gcmd)
        self._move([self.axis_limits["x"]["center"], self.axis_limits["y"]["center"], self.axis_limits["z"]["center"]], self.th_veloc)

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

        axes = self._parse_axis(gcmd.get("AXIS", self._axis_to_str(self.axes)))

        check_x = 'x' in axes if self.isolate_xy else True
        check_y = 'y' in axes if self.isolate_xy else True

        # Check endstop variance
        endstops = self._endstop_variance(endstop_samples, x=check_x, y=check_y)

        x_max = max(endstops["x"]) if check_x else 0
        y_max = max(endstops["y"]) if check_y else 0
        self.gcode.respond_info(f"AUTO SPEED endstop variance:\nMissed X:{x_max:.2f} steps, Y:{y_max:.2f} steps")
        
        if x_max >= max_missed or y_max >= max_missed:
            raise gcmd.error(f"Please increase MAX_MISSED (currently {max_missed}), or tune your steppers/homing macro.")

    # -------------------------------------------------------
    #
    #     Internal Methods
    #
    # -------------------------------------------------------
    def _parse_axis(self, raw_axes):
        raw_axes = raw_axes.lower()
        raw_axes = raw_axes.replace(" ", "")
        raw_axes = raw_axes.split(',')
        axes = []
        for axis in raw_axes:
            if axis in self.valid_axes:
                axes.append(axis)
        return axes
    
    def _axis_to_str(self, raw_axes):
        axes = ""
        for axis in raw_axes:
            axes += f"{axis},"
        axes = axes[:-1]
        return axes

    def init_axis(self, aw: AttemptWrapper, axis):
        aw.axis = axis
        if axis == "diag_x":
            aw.move = MoveDiagX()
        elif axis == "diag_y":
            aw.move = MoveDiagY()
        elif axis == "x":
            aw.move = MoveX()
        elif axis == "y":
            aw.move = MoveY()
        elif axis == "z":
            aw.move = MoveZ()
        aw.move.Init(self.axis_limits, aw.margin, self.isolate_xy)

    def binary_search(self, aw: AttemptWrapper):
        aw.time_start = perf_counter()
        m_min = aw.min
        m_max = aw.max
        m_var = m_min + (m_max-m_min) // 3

        if aw.veloc == 0.0:
            aw.veloc = 1.0
        if aw.accel == 0.0:
            aw.accel = 1.0

        if aw.type in ("accel", "graph"): # stat is velocity, var is accel
            m_stat = aw.veloc
            o_veloc = aw.veloc
            if o_veloc == 1.0:
                aw.accel = calculate_accel(aw.veloc, aw.move.max_dist)
            aw.move.Calc(self.axis_limits, m_stat, m_var, aw.margin)
            
        elif aw.type in ("velocity"): # stat is accel, var is velocity
            m_stat = aw.accel
            o_accel = aw.accel
            if o_accel == 1.0:
                aw.veloc = calculate_velocity(aw.accel, aw.move.max_dist)
            aw.move.Calc(self.axis_limits, m_var, m_stat, aw.margin)
        
        measuring = True
        measured_val = None
        aw.tries = 0
        aw.home_steps, aw.move_time_prehome = self._prehome(aw.move.home)
        while measuring:
            aw.tries += 1
            if aw.type in ("accel", "graph"):
                if o_veloc == 1.0:
                    m_stat = aw.veloc = calculate_velocity(m_var, aw.move.dist)/2.5
                aw.accel = m_var
                aw.move.Calc(self.axis_limits, m_stat, m_var, aw.margin)
            elif aw.type == "velocity":
                if o_accel == 1.0:
                    m_stat = aw.accel = calculate_accel(m_var, aw.move.dist)*2.5
                aw.veloc = m_var
                aw.move.Calc(self.axis_limits, m_var, m_stat, aw.margin)
            #self.gcode.respond_info(str(aw))

            valid = self._attempt(aw)

            if aw.type in ("accel", "graph"):
                veloc = m_stat
                accel = m_var
            elif aw.type in ("velocity"):
                veloc = m_var
                accel = m_stat
            respond = f"AUTO SPEED {aw.type} on {aw.axis} try {aw.tries} ({aw.time_last:.2f}s)\n"
            respond += f"Moved {aw.move_dist - aw.margin:.2f}mm at a{accel:.0f}/v{veloc:.0f} after {aw.move_time_prehome:.2f}/{aw.move_time:.2f}/{aw.move_time_posthome:.2f}s\n"
            respond += f"Missed"
            if aw.move.home[0]:
                respond += f" X {aw.missed['x']:.2f},"
            if aw.move.home[1]:
                respond += f" Y {aw.missed['y']:.2f},"
            if aw.move.home[2]:
                respond += f" Z {aw.missed['z']:.2f},"
            self.gcode.respond_info(respond[:-1])
            if measured_val is not None:
                if m_var * (1 + aw.accuracy) > m_max or m_var * (1 - aw.accuracy) < m_min:
                    measuring = False
            measured_val = m_var
            if valid:
                m_min = m_var
            else:
                m_max = m_var
            m_var = (m_min + m_max)//2

        aw.time_total = perf_counter() - aw.time_start
        return m_var

    def _attempt(self, aw: AttemptWrapper):
        timeAttempt = perf_counter()

        self._set_velocity(self.th_veloc, self.th_accel, self.th_scv)
        self._move([aw.move.pos["x"][0], aw.move.pos["y"][0], aw.move.pos["z"][0]], self.th_veloc)
        self.toolhead.wait_moves()
        self._set_velocity(aw.veloc, aw.accel, aw.scv)
        timeMove = perf_counter()

        self._move([aw.move.pos["x"][1], aw.move.pos["y"][1], aw.move.pos["z"][1]], aw.veloc)
        self.toolhead.wait_moves()
        aw.move_time = perf_counter() - timeMove
        aw.move_dist = aw.move.dist
        
        valid, aw.home_steps, aw.missed, aw.move_time_posthome = self._posttest(aw.home_steps, aw.max_missed, aw.move.home)
        aw.time_last = perf_counter() - timeAttempt
        return valid

    def _validate(self, speed, iterations, margin, small_margin, max_missed):
        pos = {
            "x": {
                "min": self.axis_limits["x"]["min"] + margin,
                "max": self.axis_limits["x"]["max"] - margin,
                "center_min": self.axis_limits["x"]["center"] - (small_margin/2),
                "center_max": self.axis_limits["x"]["center"] + (small_margin/2),
            },
            "y": {
                "min": self.axis_limits["y"]["min"] + margin,
                "max": self.axis_limits["y"]["max"] - margin,
                "center_min": self.axis_limits["y"]["center"] - (small_margin/2),
                "center_max": self.axis_limits["y"]["center"] + (small_margin/2),
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
            self.toolhead.wait_moves()
            self._home(x, y, False)
            steps = self._get_steps()

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
        prevScv   = self.toolhead.square_corner_velocity
        self._set_velocity(self.th_veloc, self.th_accel, self.th_scv)
        command = ["G28"]
        if x:
            command[-1] += " X0"
        if y:
            command[-1] += " Y0"
        if z:
            command[-1] += " Z0"
        self.gcode._process_commands(command, False)
        self.toolhead.wait_moves()
        self._set_velocity(prevVeloc, prevAccel, prevScv)

    def _get_steps(self):
        kin = self.toolhead.get_kinematics()
        steppers = kin.get_steppers()
        pos = {}
        for s in steppers:
            s_name = s.get_name()
            if s_name in ["stepper_x", "stepper_y", "stepper_z"]:
                pos[s_name[-1]] = s.get_mcu_position()
        return pos

    def _prehome(self, home: list):
        self.toolhead.wait_moves()
        dur = perf_counter()
        self._home(home[0], home[1], home[2])
        self.toolhead.wait_moves()
        dur = perf_counter() - dur

        home_steps = self._get_steps()
        return home_steps, dur
    
    def _posttest(self, start_steps, max_missed, home: list):
        self.toolhead.wait_moves()
        dur = perf_counter()
        self._home(home[0], home[1], home[2])
        self.toolhead.wait_moves()
        dur = perf_counter() - dur

        valid = True
        stop_steps = self._get_steps()
        step_dif = {}
        missed = {}
        if home[0]:
            step_dif["x"] = abs(start_steps["x"] - stop_steps["x"])
            missed["x"] = step_dif['x']/self.steppers['x'][2]
            if missed["x"] > max_missed:
                valid = False
        if home[1]:
            step_dif["y"] = abs(start_steps["y"] - stop_steps["y"])
            missed["y"] = step_dif['y']/self.steppers['y'][2]
            if missed["y"] > max_missed:
                valid = False
        if home[2]:
            step_dif["z"] = abs(start_steps["z"] - stop_steps["z"])
            missed["z"] = step_dif['z']/self.steppers['z'][2]
            if missed["z"] > max_missed:
                valid = False

        return valid, stop_steps, missed, dur
    
    def _set_velocity(self, velocity: float, accel: float, scv: float):
        #self.gcode.respond_info(f"AUTO SPEED setting limits to VELOCITY={velocity} ACCEL={accel}")
        self.toolhead.max_velocity = velocity
        self.toolhead.max_accel = accel
        self.toolhead.requested_accel_to_decel = accel
        self.toolhead.square_corner_velocity = scv
        self.toolhead._calc_junction_deviation()

    def cmd_X_ENDSTOP_ACCURACY(self, gcmd):

        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the X axis from the previously stored values
        second_homing_speed = self.steppers['x'][4]
        homing_retract_dist = self.steppers['x'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()
        
        # Log the starting position for X
        gcmd.respond_info("X_ENDSTOP_ACCURACY at X:%.3f (samples=%d)\n" % (pos[0], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the X positions hit during each sample
        positions = []

        # Move to the X endstop sample_count times and collect the X positions
        for _ in range(sample_count):
            self._home(True, False, False)
            pos = toolhead.get_position()  # Get the current X position after homing
            positions.append(pos[0])
            toolhead.manual_move([pos[0] - homing_retract_dist, None, None], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for X positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value
        
        deviation_sum = sum([(x - avg_value) ** 2 for x in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "X endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))


    def cmd_Y_ENDSTOP_ACCURACY(self, gcmd):

        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the Y axis from the previously stored values
        second_homing_speed = self.steppers['y'][4]
        homing_retract_dist = self.steppers['y'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()
        
        # Log the starting position for Y
        gcmd.respond_info("Y_ENDSTOP_ACCURACY at Y:%.3f (samples=%d)\n" % (pos[1], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the Y positions hit during each sample
        positions = []

        # Move to the Y endstop sample_count times and collect the Y positions
        for _ in range(sample_count):
            self._home(False, True, False)
            pos = toolhead.get_position()  # Get the current Y position after homing
            positions.append(pos[1])
            toolhead.manual_move([None, pos[1] - homing_retract_dist, None], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for Y positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value
        
        deviation_sum = sum([(y - avg_value) ** 2 for y in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "Y endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))

    def cmd_Z_ENDSTOP_ACCURACY(self, gcmd):

        if not len(self.steppers.keys()) == 3:
            raise gcmd.error(f"Printer must be homed first! Found {len(self.steppers.keys())} homed axes.")

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the Z axis from the previously stored values
        second_homing_speed = self.steppers['z'][4]
        homing_retract_dist = self.steppers['z'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()
        
        # Log the starting position for Z
        gcmd.respond_info("Z_ENDSTOP_ACCURACY at Z:%.3f (samples=%d)\n" % (pos[2], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the Z positions hit during each sample
        positions = []

        # Move to the Z endstop sample_count times and collect the Z positions
        for _ in range(sample_count):
            self._home(False, False, True)
            pos = toolhead.get_position()  # Get the current Z position after homing
            positions.append(pos[2])
            toolhead.manual_move([None, None, pos[2] + homing_retract_dist], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for Z positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value
        
        deviation_sum = sum([(z - avg_value) ** 2 for z in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "Z endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))