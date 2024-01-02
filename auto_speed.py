# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

def load_config(config): # Called by klipper from [auto_speed]
    try:
        from .autospeed import AutoSpeed
    except ImportError:
        raise ImportError(f"Please re-run klipper_auto_speed/install.sh")
    from .autospeed import AutoSpeed
    return AutoSpeed(config)