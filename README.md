# Klipper Auto Speed
 Klipper module for automatically calculating your printer's maximum acceleration/velocity

**This module is under development**: Nothing should go wrong, but please keep an eye on your printer, as this will push it to it's physical limits.

This module automatically performs [Ellis' TEST_SPEED macro](https://ellis3dp.com/Print-Tuning-Guide/articles/determining_max_speeds_accels.html), and measured the missed steps on your steppers at various accelerations/velocities. Depending on your ACCEL_START and VELOCITY_START, this may take a long time to finish.

# Table of Contents
 - [Overview](https://github.com/Anonoei/klipper_auto_speed#overview)
 - [How does it work](https://github.com/Anonoei/klipper_auto_speed#how-does-it-work)
 - [Using Klipper Auto Speed](https://github.com/Anonoei/klipper_auto_speed#using-klipper-auto-speed)
   - [Installation](https://github.com/Anonoei/klipper_auto_speed#installation)
     - [Moonraker Update Manager](https://github.com/Anonoei/klipper_auto_speed#moonraker-update-manager)
   - [Configuration](https://github.com/Anonoei/klipper_auto_speed#configuration)
   - [Macro](https://github.com/Anonoei/klipper_auto_speed#macro)

## Overview
 - License: MIT

## How does it work?
 1. Home your printer
 2. If your print is enclosed, heat soak it. You want to run this module at the typical state your printer is in when you're printing.
 3. Run `AUTO_SPEED`
    1. Check endstop variance
       - Validate the endstops are accurate enough for `MAX_MISSED`
    2. Find the maximum acceleration
       - Given `ACCEL_START`, `ACCEL_STOP_` `ACCEL_STEP`, increase acceleration until we miss more than `MAX_MISSED` steps. Move the toolhead over the pattern at each velocity `TEST_ITERATION` times
    3. Find maximum velocity
       - Given `VELOCITY_START`, `VELOCITY_STOP_` `VELOCITY_STEP`, increase velocity until we miss more than `MAX_MISSED` steps. Move the toolhead over the pattern at each velocity `TEST_ITERATION` times
    4. Stress test
       - Start at max acceleration/velocity and slowly decrease both until less than `MAX_MISSED` steps are lost after `STRESS_INTERATION`s.

## Using Klipper Auto Speed

### Installation
 To install this module you need to clone the repository and run the `install.sh` script

#### Automatic installation
```
cd ~
git clone https://github.com/Anonoei/klipper_auto_speed.git
cd klipper_auto_speed
chmod +x install.sh
./install.sh
```

#### Manual installation
1.  Clone the repository
    1. `cd ~`
    2. `git clone https://github.com/Anonoei/klipper_auto_speed.git`
    3. `cd klipper_auto_speed`
2.  Link auto_speed to klipper
    1. `ln -sf ~/klipper_auto_speed/auto_speed.py ~/klipper/klippy/extras/auto_speed.py`
3.  Restart klipper
    1. `sudo systemctl restart klipper`

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

### Configuration
Place this in your printer.cfg
```
[auto_speed]
```
The values listed below are the defaults Auto Speed uses. You can include them if you wish to change their values or run into issues.
```
[auto_speed]
z: 50                 ; Z position to run Auto Speed
margin: 20            ; How far away from your axis maximums to perform the test movement
pattern_margin: 20    ; How far from your axis centers to perform the small test movement

settling_home: True   ; Perform settling home before starting Auto Speed
max_missed: 1.0       ; Maximum full steps that can be missed
endstop_samples: 3    ; How many endstop samples to take for endstop variance

test_interations: 2   ; While testing for maximum, perform the test movement this many times
stress_iterations: 50 ; While finding final maximums, perform the test movement this many times

accel_start: Unset    ; Starting acceleration, Defaults to your printer's current acceleration
accel_stop: 50000.0   ; Maximum possible acceleration the test will go to
accel_step: 1000.0    ; Increase accel_start by this amount each test

velocity_start: Unset ; Starting velocity, Defaults to your printer's current velocity
velocity_stop: 5000.0 ; Maximum possible velocity the test will go to
velocity_step: 50.0   ; Increase velocity_start by this amount each test
```

### Macro
Run the klipper command `AUTO_SPEED`. You can also use the arguments below
Argument          | Default | Description
----------------- | ------- | -----------
Z                 | 50      | Z position to run Auto Speed
MARGIN            | 20      | How far away from your axis maximums to perform the test movement
PATTERN_MARGIN    | 20      | How far from your axis centers to perform the small test movement
SETTLING_HOME     | 1       | Perform settling home before starting Auto Speed
MAX_MISSED        | 1.0     | Maximum full steps that can be missed
ENDSTOP_SAMPLES   | 3       | How many endstop samples to take for endstop variance
TEST_ITERATIONS   | 2       | While testing for maximum, perform the test movement this many times
STRESS_ITERATIONS | 50      | While finding final maximums, perform the test movement this many times
ACCEL_START       | Unset   | Starting acceleration, Defaults to your printer's current acceleration
ACCEL_STOP        | 50000.0 | Maximum possible acceleration the test will go to
ACCEL_STEP        | 1000.0  | Increase accel_start by this amount each test
VELOCITY_START    | Unset   | Starting velocity, Defaults to your printer's current velocity
VELOCITY_STOP     | 5000.0  | Maximum possible velocity the test will go to
VELOCITY_STEP     | 50.0    | Increase velocity_start by this amount each test