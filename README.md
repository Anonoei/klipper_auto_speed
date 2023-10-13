# Klipper Auto Speed
 Klipper module for automatically calculating your printer's maximum acceleration/velocity

**This module is under development**: Nothing should go wrong, but please keep an eye on your printer, as this will push it to it's physical limits.

This module automatically performs [Ellis' TEST_SPEED macro](https://ellis3dp.com/Print-Tuning-Guide/articles/determining_max_speeds_accels.html), and measured the missed steps on your steppers at various accelerations/velocities. Depending on your ACCEL_START and VELOCITY_START, this may take a long time to finish.

**Sensorless homing**: If you're using sensorless homing you may find that `MAX_MISSED=1.0` is too low. the endstop variance check will tell you how many steps you lose when homing. For instance, on my printer I lose around 0-4.2 steps each home. I run `AUTO_SPEED MAX_MISSED=5.0` to account for that variance. If you have one wildly different result, the default `TEST_ATTEMPTS` of 2 should catch it and keep going.

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
       - accel = `ACCEL_START`
       - velocity = `(math.sqrt(travel/accel)*accel) / math.log10(accel)`
       1. Home, and save stepper start steps
       2. Move over the pattern at `accel`/`velocity` `TEST_ITERATION` times
       3. Home, and save stepper stop steps
       4. Check if between start and stop steps we missed more than `MAX_MISSED` steps.
          1. If we missed more than `MAX_MISSED`, go to the next step
          2. Otherwise, accel += `ACCEL_STEP`
    3. Find maximum velocity
       - velocity = `VELOCITY_START`
       - accel = `(velocity**2/travel) * 4`
       1. Home, and save stepper start steps
       2. Move over the pattern at `accel`/`velocity` `TEST_ITERATION` times
       3. Home, and save stepper stop steps
       4. Check if between start and stop steps we missed more than `MAX_MISSED` steps.
          1. If we missed more than `MAX_MISSED`, go to the next step
          2. Otherwise, velocity += `VELOCITY_STEP`
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

test_iterations: 2    ; While testing for maximum, perform the test movement this many times
test_attempts: 2      ; Re-test this many times if test fails
stress_iterations: 50 ; While finding final maximums, perform the test movement this many times

accel_start: 1000.0   ; Starting acceleration
accel_stop: 50000.0   ; Maximum possible acceleration the test will go to
accel_step: 1000.0    ; Increase accel_start by this amount each test

velocity_start: 100.0 ; Starting velocity
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
TEST_ATTEMPTS     | 2       | Re-test this many times if test fails
STRESS_ITERATIONS | 50      | While finding final maximums, perform the test movement this many times
ACCEL_START       | 1000.0  | Starting acceleration
ACCEL_STOP        | 50000.0 | Maximum possible acceleration the test will go to
ACCEL_STEP        | 1000.0  | Increase accel_start by this amount each test
VELOCITY_START    | 100.0   | Starting velocity
VELOCITY_STOP     | 5000.0  | Maximum possible velocity the test will go to
VELOCITY_STEP     | 50.0    | Increase velocity_start by this amount each test