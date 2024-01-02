# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

import math

def calculate_velocity(accel: float, travel: float):
    return math.sqrt(travel/accel)*accel

def calculate_accel(veloc: float, travel: float):
    return veloc**2/travel

def calculate_distance(veloc: float, accel: float):
    return veloc**2/accel

def calculate_diagonal(x: float, y: float):
    return math.sqrt(x**2 + y**2)

def calculate_graph(velocity: float, slope: int):
    return (10000/(velocity/slope))