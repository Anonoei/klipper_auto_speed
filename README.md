# Klipper Auto Speed
 Klipper module for automatically calculating your printer's maximum acceleration/velocity

*With one copy/paste and one line in your configuration, automatically optimize your printer's motion*

This module automatically performs movements on the *x*, *y*, *x-diagonal*, *y-diagonal*, and *z* axes, and measures your steppers missed steps at various accelerations/velocities.
With the default configuration, this may take *awhile* (~10 minutes).
Most of the testing time is waiting for your printer to home.
On my printer with default settings (except MAX_MISSED), it takes ~3.5 minutes for acceleration, and ~5 minutes for velocity.

**Sensorless homing**: If you're using sensorless homing `MAX_MISSED=1.0` is probably too low.
The endstop variance check will tell you how many steps you lose when homing.
For instance, on my printer I lose around 0-4.2 steps each home.
I run `AUTO_SPEED MAX_MISSED=10.0` to account for that variance, and occasional wildly different endstop results.

**This module is under development**, and has only been validated on CoreXY printers: You may run into issues or bugs, feel free to use the discord channel, or post an issue here.
 - [Discord - DOOMCUBE User Projects](https://discord.com/channels/825469421346226226/1162192150822404106)

Your printer shouldn't have any crashes due to the movement patterns used, and re-homing before/after each test, so it's safe to walk away and let it do it's thing.

Using Ellis' pattern (AUTO_SPEED_VALIDATE) is **NOT** a safe movement pattern. Please ensure your toolhead isn't crashing before walking away.

# Table of Contents
 - [Overview](https://github.com/Anonoei/klipper_auto_speed#overview)
 - [Example Usage](https://github.com/Anonoei/klipper_auto_speed#example-usage)
 - [Roadmap](https://github.com/Anonoei/klipper_auto_speed#roadmap)
 - [How does it work](https://github.com/Anonoei/klipper_auto_speed#how-does-it-work)
 - [Using Klipper Auto Speed](https://github.com/Anonoei/klipper_auto_speed#using-klipper-auto-speed)
   - [Installation](https://github.com/Anonoei/klipper_auto_speed#installation)
     - [Moonraker Update Manager](https://github.com/Anonoei/klipper_auto_speed#moonraker-update-manager)
   - [Configuration](https://github.com/Anonoei/klipper_auto_speed#configuration)
   - [Macros](https://github.com/Anonoei/klipper_auto_speed#macro)
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
- Validate your printer's current accel/velocity (Ellis' test pattern)
  - `AUTO_SPEED_VALIDATE`
- Graph your printer's max velocity/accel
  - `AUTO_SPEED_GRAPH`
- Graph your printer's max velocity/accel between v100 and v1000, over 9 steps
  - `AUTO_SPEED_GRAPH VELOCITY_MIN=100 VELOCITY_MAX=1000 VELOCITY_DIV=9`
 
## Roadmap
 - [ ] Export printer results as a 'benchmark' to a database to see average speeds for different printers
 - [ ] Make _ACCEL/_VELOCITY smarter, based on printer size
 - [ ] Add support for running through moonraker (enables scripting different commands, arguments)
 - [ ] Save validated/measured results to printer config (like SAVE_CONFIG)
 - [ ] Couple ACCEL/VELOCITY similar to AUTO_SPEED_GRAPH
   - [ ] Add AUTO_SPEED ACCEL=10000 - to find what velocity lets you use accel 10000
   - [ ] Add AUTO_SPEED VELOC=500 - to find what accel lets you use velocity 500
   - [ ] Make AUTO_SPEED measure different accels/velocity to find the best values based on printer size
 - [X] Add testing Z axis
 - [X] Reduce code duplication
 - [X] Check kinematics to find best movement patterns
 - [X] Update calculated accel/velocity depending on test to be more accurate
 - [X] Update axis movement logic

## How does it work?
 1. Home your printer
 2. If your print is enclosed, heat soak it. You want to run this module in the typical state your printer is in when you're printing.
 3. Run `AUTO_SPEED`
    1. Prepare
       1. Make sure the printer is level
       2. Check endstop variance
          - Validate the endstops are accurate enough for `MAX_MISSED`
    2. Find the maximum acceleration
       - Perform a binary search between `ACCEL_MIN` and `ACCEL_MAX`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
       4. If difference between start/stop steps is more than `max_missed`, go to next step
    3. Find maximum velocity
       - Perform a binary search between `VELOCITY_MIN` and `VELOCITY_MAX`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
       4. If difference between start/stop steps is more than `max_missed`, go to next step
    4. Show results

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
 To install this module you need to clone the repository and run the `install.sh` script.
 **Depending on when you installed klipper, you may also need to [update your klippy-env python version.](https://github.com/Anonoei/klipper_auto_speed#update-klippy-env)**

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

#### Update klippy-env
 1. `sudo apt install python3`
 2. `sudo apt install python3-numpy`
 3. `sudo systemctl stop klipper`
 4. `python3 -m venv --update ~/klippy-env`
 5. `~/klippy-env/bin/pip install -r "~/klipper/scripts/klippy-requirements.txt"`

### Configuration
Place this in your printer.cfg
```
[auto_speed]
```
The values listed below are the defaults Auto Speed uses. You can include them if you wish to change their values or run into issues.
```
[auto_speed]
#axis: diag_x, diag_y  ; One or multiple of `x`, `y`, `diag_x`, `diag_y`, `z`

#margin: 20            ; How far away from your axes to perform movements

#settling_home: 1      ; Perform settling home before starting Auto Speed
#max_missed: 1.0       ; Maximum full steps that can be missed
#endstop_samples: 3    ; How many endstop samples to take for endstop variance

#accel_min: 1000.0     ; Minimum acceleration test may try
#accel_max: 50000.0    ; Maximum acceleration test may try
#accel_accu: 0.05      ; Keep binary searching until the result is within this percentage

#velocity_min: 50.0    ; Minimum velocity test may try
#velocity_max: 5000.0  ; Maximum velocity test may try
#velocity_accu: 0.05   ; Keep binary searching until the result is within this percentage

#derate: 0.8           ; Derate discovered results by this amount

#validate_margin: Unset      ; Margin for VALIDATE, Defaults to margin
#validate_inner_margin: 20.0 ; Margin for VALIDATE inner pattern
#validate_iterations: 50     ; Perform VALIDATE pattern this many times

#results_dir: ~/printer_data/config ; Destination directory for graphs
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
ACCEL_ACCU        | 0.05    | Keep binary searching until the result is within this percentage
VELOCITY_MIN      | 50.0    | Minimum velocity test may try
VELOCITY_MAX      | 5000.0  | Maximum velocity test may try
VELOCITY_ACCU     | 0.05    | Keep binary searching until the result is within this percentage
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
 ACCEL_ACCU | 0.05    | Keep binary searching until the result is within this percentage

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
 VELOCITY_ACCU | 0.05    | Keep binary searching until the result is within this percentage

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

 Argument        | Default | Description
 --------------- | ------- | -----------
 AXIS            | Unset   | Perform test on these axes, defaults to diag_x, diag_y
 MARGIN          | 20.0    | Used when DIST is 0.0, how far away from axis to perform movements
 DERATE          | 0.8     | How much to derate maximum values for the recommended max
 MAX_MISSED      | 1.0     | Maximum fulls steps that can be missed
 VELOCITY_MIN    | Unset   | Minimum velocity test may try
 VELOCITY_MAX    | Unset   | Maximum velocity test may try
 VELOCITY_DIV    | 5       | How many velocities to test
 VELOCITY_ACCU   | 0.05    | Keep binary searching until the result within this percent
 ACCEL_MIN_SLOPE | 100     | Calculated min slope value $\frac{10000}{velocity \div slope}$
 ACCEL_MAX_SLOPE | 1800    | Calculated max slope value $\frac{10000}{velocity \div slope}$

## Console Output
 Console output is slightly different depending on whether testing acceleration/velocity, and which axis is being tested.

 - `axis` is one of `x`, `y`, `diag_x`, `diag_y`, `z`
 - The three times after `after` are (first home time)/(movement time)/(end home time)
 - `#`s before decimals are variable, `#`s after decimals are static

### Acceleration tests
```
AUTO SPEED accel on `axis` try # (#.##s)
Moved #.##mm at a###/v### after #.##/#.##/#.##s
Missed X #.##, Y #.##
```
Example:
```
AUTO SPEED accel on diag_x try 1 (19.66s)
Moved 1.43mm at a17333/v241 after 8.92/0.30/9.93s
Missed X 0.31, Y 2.00
```

### Velocity tests
```
AUTO SPEED velocity on `axis` try # (#.##s)
Moved #.##mm at a###/v### after #.##/#.##/#.##s
Missed X #.##, Y #.##
```
Example:
```
AUTO SPEED velocity on diag_y try 1 (23.91s)
Moved 13.44mm at a91456/v1700 after 8.92/0.31/13.87s
Missed X 0.06, Y 132.00
```

### Acceleration results
```
AUTO SPEED found maximum acceleration after #.##s
| `AXIS 1` max: ###
| `AXIS 2` max: ###

Recommended values:
| `AXIS 1` max: ###
| `AXIS 2` max: ###
Recommended acceleration: ###
```
Example:
```
AUTO SPEED found maximum acceleration after 218.00s
| DIAG X max: 48979
| DIAG Y max: 48979

Recommended values:
| DIAG X max: 39183
| DIAG Y max: 39183
Recommended acceleration: 39183
```

### Velocity results
```
AUTO SPEED found maximum velocity after #.##s
| `AXIS 1` max: ###
| `AXIS 2` max: ###

Recommended values
| `AXIS 1` max: ###
| `AXIS 2` max: ###
Recommended velocity: ###
```
Example:
```
AUTO SPEED found maximum velocity after 307.60s
| DIAG X max: 577
| DIAG Y max: 552

Recommended values
| DIAG X max: 462
| DIAG Y max: 442
Recommended velocity: 442
```

### Recommended results
```
AUTO SPEED found recommended acceleration and velocity after #.##s
| `AXIS 1` max: a### v###
| `AXIS 2`: a### v###
Recommended accel: ###
Recommended velocity: ###
```
Example:
```
AUTO SPEED found recommended acceleration and velocity after 525.61s
| DIAG X max: a39183 v462
| DIAG Y max: a39183 v442
Recommended accel: 39183
Recommended velocity: 442
```
