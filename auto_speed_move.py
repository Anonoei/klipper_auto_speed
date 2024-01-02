import math

from auto_speed_funcs import calculate_distance

class Move:
    home = [False, False, False]
    def __init__(self):
        self.dist = 0.0
        self.pos = {}
        self.max_dist: float = 0.0

    def __str__(self):
        fmt = f"dist/max {self.dist:.0f}/{self.max_dist:.0f}\n"
        if self.pos.get("x", None) is not None:
            fmt += f"Pos X: {self.pos['x']}\n"
        if self.pos.get("y", None) is not None:
            fmt += f"Pos Y: {self.pos['y']}\n"
        if self.pos.get("z", None) is not None:
            fmt += f"Pos Z: {self.pos['z']}\n"
        return fmt

    def _calc(self, axis_limits, veloc, accel, margin):
        if self.max_dist == 0.0:
            self.Init(axis_limits, margin)

    def _validate(self, margin: float):
        if self.dist < 5.0:
            self.dist = 5.0
        self.dist += margin
        if self.dist > self.max_dist:
            self.dist = self.max_dist

    def Init(self, axis_limits, margin):
        ...
    def Calc(self, axis_limits, veloc, accel, margin):
        ...

class MoveX(Move):
    def Init(self, axis_limits, margin, isolate_xy):
        home_y = not isolate_xy 
        self.home = [True, home_y, False]
        self.max_dist = axis_limits["x"]["dist"] - margin*2
    def Calc(self, axis_limits, veloc, accel, margin):
        self._calc(axis_limits, veloc, accel, margin)
        self.dist = calculate_distance(veloc, accel)/2
        self._validate(margin)
        self.pos = {
            "x": [
                axis_limits["x"]["max"] - self.dist,
                axis_limits["x"]["max"] - margin
            ],
            "y": [None, None],
            "z": [None, None]
        }

class MoveY(Move):
    def Init(self, axis_limits, margin, isolate_xy):
        home_x = not isolate_xy 
        self.home = [home_x, True, False]
        self.max_dist = axis_limits["y"]["dist"] - margin*2
    def Calc(self, axis_limits, veloc, accel, margin):
        self._calc(axis_limits, veloc, accel, margin)
        self.dist = calculate_distance(veloc, accel)/2
        self._validate(margin)
        self.pos = {
            "x": [None, None],
            "y": [
                axis_limits["y"]["max"] - self.dist,
                axis_limits["y"]["max"] - margin
            ],
            "z": [None, None]
        }

class MoveDiagX(Move):
    home = [True, True, False]
    def Init(self, axis_limits, margin, _):
        self.max_dist = min(axis_limits["x"]["dist"], axis_limits["y"]["dist"]) - margin*2
    def Calc(self, axis_limits, veloc, accel, margin):
        self._calc(axis_limits, veloc, accel, margin)
        self.dist = (calculate_distance(veloc, accel)/2 * math.sin(45))
        self._validate(margin)
        self.pos = {
            "x": [
                axis_limits["x"]["max"] - self.dist,
                axis_limits["x"]["max"] - margin
            ],
            "y": [
                axis_limits["y"]["max"] - self.dist,
                axis_limits["y"]["max"] - margin
            ],
            "z": [None, None]
        }

class MoveDiagY(Move):
    home = [True, True, False]
    def Init(self, axis_limits, margin, _):
        self.max_dist = min(axis_limits["x"]["dist"], axis_limits["y"]["dist"]) - margin*2
    def Calc(self, axis_limits, veloc, accel, margin):
        self._calc(axis_limits, veloc, accel, margin)
        self.dist = (calculate_distance(veloc, accel)/2 * math.sin(45))
        self._validate(margin)
        self.pos = {
            "x": [
                axis_limits["x"]["min"] + self.dist,
                axis_limits["x"]["min"] + margin
            ],
            "y": [
                axis_limits["y"]["max"] - self.dist,
                axis_limits["y"]["max"] - margin
            ],
            "z": [None, None]
        }

class MoveZ(Move):
    home = [False, False, True]
    def Init(self, axis_limits, margin, _):
        self.max_dist = axis_limits["z"]["dist"] - margin*2
    def Calc(self, axis_limits, veloc, accel, margin):
        self.dist = (calculate_distance(veloc, accel))
        self._validate(margin)
        self.pos = {
            "x": [None, None],
            "y": [None, None],
        }
        if axis_limits["z"]["home"] <= axis_limits["z"]["min"]:
            self.pos["z"] =  [
                axis_limits["z"]["min"] + self.dist,
                axis_limits["z"]["min"] + margin
            ]
        else:
            self.pos["z"] =  [
                axis_limits["z"]["max"] - self.dist,
                axis_limits["z"]["max"] - margin
            ]