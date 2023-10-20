# Klipper Auto Speed
 Klipper module for automatically calculating your printer's maximum acceleration/velocity

*With one copy/paste and one line in your configuration, automatically optimize your printer's motion*

This module automatically performs movements on the x, y, x diagonal, and y diagonal axes, and measures your steppers missed steps at various accelerations/velocities.
With the default configuration, this may take *awhile* (up to an hour).
Most of the testing time is waiting for your printer to home.
On my printer with default settings (except MAX_MISSED), it takes ~23 minutes for acceleration, ~20 minutes for velocity, and 5 minutes for the validation test.

**Sensorless homing**: If you're using sensorless homing `MAX_MISSED=1.0` is probably too low.
The endstop variance check will tell you how many steps you lose when homing.
For instance, on my printer I lose around 0-4.2 steps each home.
I run `AUTO_SPEED MAX_MISSED=10.0` to account for that variance, and occasional wildly different results.

**This module is under development**, and has only been validated on CoreXY printers: You may run into issues or bugs, feel free to use the discord channel, or post an issue here.
 - [Discord - DOOMCUBE User Projects](https://discord.com/channels/825469421346226226/1162192150822404106)

Your printer shouldn't have any crashes due to the movement patterns used, and re-homing before/after each test, so it's safe to walk away and let it do it's thing.

# Table of Contents
 - [Overview](https://github.com/Anonoei/klipper_auto_speed#overview)
 - [Example Usage](https://github.com/Anonoei/klipper_auto_speed#example-usage)
 - [Roadmap](https://github.com/Anonoei/klipper_auto_speed#roadmap)
 - [How does it work](https://github.com/Anonoei/klipper_auto_speed#how-does-it-work)
 - [Using Klipper Auto Speed](https://github.com/Anonoei/klipper_auto_speed#using-klipper-auto-speed)
   - [Installation](https://github.com/Anonoei/klipper_auto_speed#installation)
     - [Moonraker Update Manager](https://github.com/Anonoei/klipper_auto_speed#moonraker-update-manager)
   - [Configuration](https://github.com/Anonoei/klipper_auto_speed#configuration)
   - [Macro](https://github.com/Anonoei/klipper_auto_speed#macro)
     - [AUTO_SPEED](https://github.com/Anonoei/klipper_auto_speed#auto_speed)
     - [AUTO_SPEED_ACCEL](https://github.com/Anonoei/klipper_auto_speed#auto_speed_accel)
     - [AUTO_SPEED_VELOCITY](https://github.com/Anonoei/klipper_auto_speed#auto_speed_velocity)
     - [AUTO_SPEED_VALIDATE](https://github.com/Anonoei/klipper_auto_speed#auto_speed_validate)
     - [AUTO_SPEED_GRAPH](https://github.com/Anonoei/klipper_auto_speed#auto_speed_graph)
 - [Console Output](https://github.com/Anonoei/klipper_auto_speed#console-output)

## Overview
 - License: MIT

## Example Usage
- Default usage (find max accel/velocity)
  - `AUTO_SPEED`
- Find maximum acceleration on y axis
  - `AUTO_SPEED_ACCEL AXIS="y"`
- Find maximum acceleration on y, then x axis
  - `AUTO_SPEED_VELOCITY AXIS="y,x"`
- Validate your printer's current accel/velocity
  - `AUTO_SPEED_VALIDATE`
- Graph your printer's max accel between v00 and v1000
  - `AUTO_SPEED_GRAPH VELOCITY_MIN=100 VELOCITY_MAX=1000`
- Graph your printer's max accel between v100 and v1000, over 10 steps
  - `AUTO_SPEED_GRAPH VELOCITY_MIN=100 VELOCITY_MAX=1000 VELOCITY_DIV=10`
 
## Roadmap
 - [ ] Check kinematics to find best movement patterns
 - [ ] Update calculated accel/velocity depending on test to be more accurate
 - [ ] Update axis movement logic
 - [ ] Add support for running through moonraker
 - [ ] Add testing Z axis
 - [ ] Reduce code duplication
 - [ ] Save validated/measured results to printer config

## How does it work?
 1. Home your printer
 2. If your print is enclosed, heat soak it. You want to run this module at the typical state your printer is in when you're printing.
 3. Run `AUTO_SPEED`
    1. Check endstop variance
       - Validate the endstops are accurate enough for `MAX_MISSED`
    2. Find the maximum acceleration
       - Perform a binary search between `ACCEL_MIN` and `ACCEL_MAX`
       - velocity = `(math.sqrt(travel/accel)*accel) * .7`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
    3. Find maximum velocity
       - Perform a binary search between `VELOCITY_MIN` and `VELOCITY_MAX`
       - accel = `(velocity**2/travel) * 4`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
    4. Show results
       - Print results on each axis, for both accel and velocity, and also print the recommended (derated) values

## Using Klipper Auto Speed

### Moonraker Update Manager
```
[update_manager klipper_auto_speed]
type: git_repo
path: ~/klipper_auto_speed
origin: https://github.com/anonoei/klipper_auto_speed.git
primary_branch: main
install_script: install.sh
managed_services: klipper
```

### Installation
 To install this module you need to clone the repository and run the `install.sh` script

#### Automatic installation
```
cd ~
git clone https://github.com/Anonoei/klipper_auto_speed.git
cd klipper_auto_speed
./install.sh
```

#### Manual installation
1.  Clone the repository
    1. `cd ~`
    2. `git clone https://github.com/Anonoei/klipper_auto_speed.git`
    3. `cd klipper_auto_speed`
2.  Link auto_speed to klipper
    1. `ln -sf ~/klipper_auto_speed/auto_speed.py ~/klipper/klippy/extras/auto_speed.py`
3.  Install matplotlib
    1.  `~/klippy-env/bin/python -m pip install matplotlib`
4.  Restart klipper
    1. `sudo systemctl restart klipper`

### Configuration
Place this in your printer.cfg
```
[auto_speed]
```
The values listed below are the defaults Auto Speed uses. You can include them if you wish to change their values or run into issues.
```
[auto_speed]
axis: diag_x, diag_y  ; One or multiple of `x`, `y`, `diag_x`, `diag_y`

z: Unset              ; Z position to run Auto Speed, defaults to 10% of z axis length
margin: 20            ; How far away from your axis maximums to perform the test movement
pattern_margin: 20    ; How far from your axis centers to perform the small test movement

settling_home: True   ; Perform settling home before starting Auto Speed
max_missed: 1.0       ; Maximum full steps that can be missed
endstop_samples: 3    ; How many endstop samples to take for endstop variance

accel_min: 1000.0     ; Minimum acceleration test may try
accel_max: 50000.0    ; Maximum acceleration test may try
accel_dist: 10.0      ; Distance to move when testing, if 0, use total axis - margin
accel_ittr: 1         ; How many iterations of the test to perform
accel_accu: 500.0     ; Keep binary searching until the result is this small

velocity_min: 50.0    ; Minimum velocity test may try
velocity_max: 5000.0  ; Maximum velocity test may try
velocity_dist: 0.0    ; Distance to move when testing, if 0, use total axis - margin
velocity_ittr: 1      ; How many iterations of the test to perform
velocity_accu: 50.0   ; Keep binary searching until the result is this small

derate: 0.8           ; Derate discovered results by this amount

validate_margin: Unset      ; Margin for VALIDATE, Defaults to margin
validate_inner_margin: 20.0 ; Margin for VALIDATE inner pattern
validate_iterations: 50     ; Perform VALIDATE pattern this many times
```

### Macro
Auto Speed is split into 5 separate macros. The default `AUTO_SPEED` automatically calls the other three (`AUTO_SPEED_ACCEL`, `AUTO_SPEED_VELOCITY`, `AUTO_SPEED_VALIDATE`). You can use any argument from those macros when you call `AUTO_SPEED`.

You can also use `AUTO_SPEED_GRAPH` to find your printers velocity-to-accel relationship.

#### AUTO_SPEED
 `AUTO_SPEED` finds maximum acceleration, velocity, and validates results at the end.
Argument          | Default | Description
----------------- | ------- | -----------
AXIS              | Unset   | Perform test on these axes, defaults to diag_x, diag_y
Z                 | 50      | Z position to run Auto Speed
MARGIN            | 20      | How far away from your axis maximums to perform the test movement
SETTLING_HOME     | 1       | Perform settling home before starting Auto Speed
MAX_MISSED        | 1.0     | Maximum full steps that can be missed
ENDSTOP_SAMPLES   | 3       | How many endstop samples to take for endstop variance
TEST_ATTEMPTS     | 2       | Re-test this many times if test fails
ACCEL_MIN         | 1000.0  | Minimum acceleration test may try
ACCEL_MAX         | 50000.0 | Maximum acceleration test may try
ACCEL_DIST        | 10.0    | Distance to move when testing, if 0, use total axis - margin
ACCEL_ITTR        | 1       | How many iterations of the test to perform
ACCEL_ACCU        | 500.0   | Keep binary searching until the result is this small
VELOCITY_MIN      | 50.0    | Minimum velocity test may try
VELOCITY_MAX      | 5000.0  | Maximum velocity test may try
VELOCITY_DIST     | 0.0     | Distance to move when testing, if 0, use total axis - margin
VELOCITY_ITTR     | 1       | How many iterations of the test to perform
VELOCITY_ACCU     | 50.0    | Keep binary searching until the result is this small
LEVEL             | 1       | Level the printer if it's not leveled
VARIANCE          | 1       | Check endstop variance

#### AUTO_SPEED_ACCEL
 `AUTO_SPEED_ACCEL` find maximum acceleration
 Argument   | Default | Description
 ---------- | ------- | -----------
 AXIS       | Unset   | Perform test on these axes, defaults to diag_x, diag_y
 MARGIN     | 20.0    | Used when DIST is 0.0, how far away from axis to perform movements
 DERATE     | 0.8     | How much to derate maximum values for the recommended max
 MAX_MISSED | 1.0     | Maximum fulls steps that can be missed
 ACCEL_MIN  | 1000.0  | Minimum acceleration test may try
 ACCEL_MAX  | 50000.0 | Maximum acceleration test may try
 ACCEL_DIST | 10.0    | Distance to move when testing, if 0, use (total axis - margin)
 ACCEL_ITTR | 1       | How many iterations of the test to perform
 ACCEL_ACCU | 500.0   | Keep binary searching until the result is this small

#### AUTO_SPEED_VELOCITY
 `AUTO_SPEED_VELOCITY` finds maximum velocity
 Argument      | Default | Description
 ------------- | ------- | -----------
 AXIS          | Unset   | Perform test on these axes, defaults to diag_x, diag_y
 MARGIN        | 20.0    | Used when DIST is 0.0, how far away from axis to perform movements
 DERATE        | 0.8     | How much to derate maximum values for the recommended max
 MAX_MISSED    | 1.0     | Maximum fulls steps that can be missed
 VELOCITY_MIN  | 100.0   | Minimum velocity test may try
 VELOCITY_MAX  | 5000.0  | Maximum velocity test may try
 VELOCITY_DIST | 0.0     | Distance to move when testing, if 0, use (total axis - margin)
 VELOCITY_ITTR | 1       | How many iterations of the test to perform
 VELOCITY_ACCU | 50.0    | Keep binary searching until the result is this small

#### AUTO_SPEED_VALIDATE
 `AUTO_SPEED_VALIDATE` validates a specified acceleration/velocity, using [Ellis' TEST_SPEED Pattern](https://github.com/AndrewEllis93/Print-Tuning-Guide/blob/main/macros/TEST_SPEED.cfg)
 Argument              | Default | Description
 --------------------- | ------- | -----------
 MAX_MISSED            | 1.0     | Maximum fulls steps that can be missed
 VALIDATE_MARGIN       | 20.0    | Margin axes max/min pattern can move to
 VALIDATE_INNER_MARGIN | 20.0    | Margin from axes center pattern can move to
 VALIDATE_ITERATIONS   | 50      | Repeat the pattern this many times
 ACCEL                 | Unset   | Defaults to current max accel
 VELOCITY              | Unset   | Defaults to current max velocity


#### AUTO_SPEED_GRAPH
 `AUTO_SPEED_GRAPH` graphs your printer's velocity-to-accel relationship on specified axes
 You must specify `VELOCITY_MIN` and `VELOCITY_MAX`.
 Results are saved to `~/printer_data/config`
 Argument      | Default | Description
 ------------- | ------- | -----------
 AXIS          | Unset   | Perform test on these axes, defaults to diag_x, diag_y
 MARGIN        | 20.0    | Used when DIST is 0.0, how far away from axis to perform movements
 DERATE        | 0.8     | How much to derate maximum values for the recommended max
 MAX_MISSED    | 1.0     | Maximum fulls steps that can be missed
 VELOCITY_MIN  | Unset   | Minimum velocity test may try
 VELOCITY_MAX  | Unset   | Maximum velocity test may try
 VELOCITY_DIV  | 5       | How many velocities to test
 VELOCITY_DIST | 0.0     | Distance to move when testing, if 0, use (total axis - margin)
 VELOCITY_ITTR | 1       | How many iterations of the test to perform
 VELOCITY_ACCU | 0.05    | Keep binary searching until the result within this percent
 ACCEL_MIN_A   | 0.23    | Accel min parabola equation 'a'
 ACCEL_MIN_B   | -300    | Accel min parabola equation 'b'
 ACCEL_MIN_C   | 85000   | Accel min parabola equation 'c' - y at velocity 0
 ACCEL_MAX_A   | 0.19    | Accel max parabola equation 'a'
 ACCEL_MAX_B   | -300    | Accel max parabola equation 'b'
 ACCEL_MAX_C   | 200000  | Accel max parabola equation 'c' - y at velocity 0

## Console Output
 Console output is slightly different depending on whether testing acceleration/velocity, and which axis is being tested.

 - `axis` is one of `x`, `y`, `diag_x`, `diag_y`

For acceleration tests:
```
AUTO SPEED acceleration diag_x measurement 4 (47.48s)
Missed X 4898.39, Y 0.02 at a14750/v659 over 1.24s
```

Velocity tests are the same as acceleration except a few details
```
AUTO SPEED velocity diag_y measurement 5 (40.97s)
Missed X 2.11, Y 3.98 at v797/a8635 over 1.24s
```

Acceleration results
```
AUTO SPEED found maximum acceleration after 1398.34s
| X max: 49249
| Y max: 30107
| DIAG X max: 27084
| DIAG Y max: 24169

Recommended values:
| X max: 39399
| Y max: 24085
| DIAG X max: 21668
| DIAG Y max: 19335
Recommended acceleration: 19335
```

Velocity results
```
AUTO SPEED found maximum velocity after 449.66s
| DIAG X max: 797
| DIAG Y max: 797

Recommended values
| DIAG X max: 638
| DIAG Y max: 638
Recommended velocity: 638
```

Recommended results
```
AUTO SPEED found recommended acceleration and velocity after 993.64s
| DIAG X max: a11217 v638
| DIAG Y max: a10033 v638
Recommended accel: 10033
Recommended velocity: 638
```
