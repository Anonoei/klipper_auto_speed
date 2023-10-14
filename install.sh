#!/bin/bash
# automatically calculate your printer's maximum acceleration/velocity
#
# Copyright (C) 2023 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

# Force script to exit if an error occurs
set -e

KLIPPER_PATH="${HOME}/klipper"
SYSTEMDDIR="/etc/systemd/system"
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

# Verify we're running as root
if [ "$(id -u)" -eq 0 ]; then
    echo "This script must not run as root"
    exit -1
fi

# Check if Klipper is installed
if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F "klipper.service")" ]; then
    echo "Klipper service found!"
else
    echo "Klipper service not found, please install Klipper first"
    exit -1
fi

# Link auto speed to klipper
echo "Linking auto speed to Klipper..."
ln -sf "${SRCDIR}/auto_speed.py" "${KLIPPER_PATH}/klippy/extras/auto_speed.py"

# Restart klipper
echo "Restarting Klipper..."
sudo systemctl restart klipper