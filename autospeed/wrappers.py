# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

from .move import Move

class ResultsWrapper:
    def __init__(self):
        self.name: str = ""
        self.duration: float = None
        self.vals: dict = {}

    def __str__(self):
        fmt = f"ResultsWrapper {self.name}, duration: {self.duration}\n"
        fmt += f"| Vals: {self.vals}"
        return fmt

    def derate(self, derate):
        vList = []
        newVals = {}
        for k, v in self.vals.items():
            newVals[f"max_{k}"] = v
            newVals[k] = v * derate
            vList.append(newVals[k])
        self.vals = newVals
        self.vals["rec"] = min(vList)

class AttemptWrapper:
    def __init__(self):
        self.type: str = ""
        self.axis: str = ""
        self.min: float = None
        self.max: float = None
        self.accuracy: float = None
        self.max_missed: int = None
        self.margin: float = None
        self.accel: float = 0.0
        self.veloc: float = 0.0
        self.scv: float = 0
        
        self.home_steps: float = None
        
        self.tries: int = 0
        self.move: Move = None
        self.move_dist: float = 0.0
        self.move_valid = True
        self.move_missed: dict = None
        self.move_time_prehome: float = 0.0
        self.move_time: float = 0.0
        self.move_time_posthome: float = 0.0
        self.time_start: float = 0.0
        self.time_last: float = 0.0
        self.time_total: float = 0.0

    def __str__(self):
        fmt = f"AttemptWrapper {self.type} on {self.axis}, try {self.tries}\n"
        fmt += f"| Min: {self.min:.0f}, Max: {self.max:.0f}\n"
        fmt += f"| Accuracy: {self.accuracy*100}%, Max Missed: {self.max_missed:.0f}\n"
        fmt += f"| Margin: {self.margin}, Accel: {self.accel:.0f}, Veloc: {self.veloc:.0f}\n"
        fmt += f"| Move: {self.move}"
        fmt += f"| Valid: {self.move_valid}, Dist: {self.move_dist:.0f}\n"
        fmt += f"| Times: {self.move_time_prehome:.2f}/{self.move_time:.2f}/{self.move_time_posthome:.2f}s over {self.time_last:.2f}"
        return fmt
