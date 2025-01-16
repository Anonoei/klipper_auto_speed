import re
import sys
import os

def interpolate_acceleration(velocity_acceleration_pairs, velocity):
    min_velocity = velocity_acceleration_pairs[0][0]
    max_velocity = velocity_acceleration_pairs[-1][0]
    
    if velocity < min_velocity:
        acceleration_x, acceleration_y = velocity_acceleration_pairs[0][1], velocity_acceleration_pairs[0][2]
    elif velocity > max_velocity:
        acceleration_x, acceleration_y = velocity_acceleration_pairs[-1][1], velocity_acceleration_pairs[-1][2]
    else:
        for i in range(len(velocity_acceleration_pairs) - 1):
            v1, a1_x, a1_y = velocity_acceleration_pairs[i]
            v2, a2_x, a2_y = velocity_acceleration_pairs[i+1]
            if v1 <= velocity <= v2:
                acceleration_x = int((velocity - v1) * (a2_x - a1_x) / (v2 - v1) + a1_x)
                acceleration_y = int((velocity - v1) * (a2_y - a1_y) / (v2 - v1) + a1_y)
                return acceleration_x, acceleration_y
    
    return acceleration_x, acceleration_y

def read_velocity_acceleration_pairs(file_path):
    velocity_acceleration_pairs = []
    use_individual_acceleration = False
    
    try:
        with open(file_path, 'r') as config_file:
            capture_values = False
            for line in config_file:
                line = line.strip()
                if line.startswith("#*# Speed,XAcceleration,YAcceleration"):
                    capture_values = True
                    use_individual_acceleration = True
                elif line.startswith("#*# End Values"):
                    capture_values = False
                elif capture_values:
                    values = line.lstrip("#*#").strip().split(',')
                    if len(values) == 3:
                        velocity, acceleration_x, acceleration_y = map(int, values)
                        velocity_acceleration_pairs.append((velocity, acceleration_x, acceleration_y))
                    elif len(values) == 2:
                        velocity, acceleration = map(int, values)
                        velocity_acceleration_pairs.append((velocity, acceleration, acceleration))
                        use_individual_acceleration = False
    except FileNotFoundError:
        print(f'Datei nicht gefunden: {file_path}')
    except Exception as e:
        print(f'Ein Fehler ist aufgetreten: {str(e)}')
    
    return velocity_acceleration_pairs, use_individual_acceleration

def process_gcode(input_filename, velocity_acceleration_pairs, factor, use_individual_acceleration):
    try:
        with open(input_filename, 'r') as input_file:
            base_name, extension = os.path.splitext(input_filename)
            output_filename = f'{base_name}_parsed{extension}'
            
            with open(output_filename, 'w') as output_file:
                acceleration_override_x = None
                acceleration_override_y = None
                for line in input_file:
                    match = re.match(r'G1 F(\d+)', line)
                    if match:
                        velocity_mm_per_min = int(match.group(1))
                        velocity_mm_per_sec = velocity_mm_per_min / 60
                        acceleration_x, acceleration_y = interpolate_acceleration(velocity_acceleration_pairs, velocity_mm_per_sec)
                        if acceleration_x is not None and acceleration_y is not None:
                            acceleration_x = int(acceleration_x * factor / 100)  # Apply factor
                            acceleration_y = int(acceleration_y * factor / 100)  # Apply factor
                            output_file.write(line)
                            if use_individual_acceleration:
                                output_file.write(f'SET_KINEMATICS_LIMIT X_ACCEL={acceleration_x} Y_ACCEL={acceleration_y}\n')
                            else:
                                output_file.write(f'SET_VELOCITY_LIMIT ACCEL={acceleration_y}\n')
                        else:
                            output_file.write(line)
                    elif line.startswith('M201'):
                        match_x = re.search(r'X(\d+)', line)
                        match_y = re.search(r'Y(\d+)', line)
                        if match_x:
                            acceleration_override_x = int(match_x.group(1))
                        if match_y:
                            acceleration_override_y = int(match_y.group(1))
                        output_file.write(line)
                    else:
                        output_file.write(line)
        
        print(f'Die G-Code-Datei wurde erfolgreich erstellt: {output_filename}')
    except FileNotFoundError:
        print(f'Datei nicht gefunden: {input_filename}')
    except Exception as e:
        print(f'Ein Fehler ist aufgetreten: {str(e)}')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Verwendung: python gcode_parser.py <Eingabedatei>')
    else:
        input_filename = sys.argv[1]
        config_path = "/home/pi/printer_data/config/scripts/Autoacc/autoacc.cfg"
        velocity_acceleration_pairs, use_individual_acceleration = read_velocity_acceleration_pairs(config_path)
        
        if velocity_acceleration_pairs:
            factor = 100  # Default factor (no reduction)
            try:
                with open(config_path, 'r') as config_file:
                    for line in config_file:
                        if line.strip().startswith("#*# Faktor in %:"):
                            factor = int(line.split(':')[1])
                            break
            except FileNotFoundError:
                pass
            
            process_gcode(input_filename, velocity_acceleration_pairs, factor, use_individual_acceleration)
        else:
            print("Geschwindigkeits-Beschleunigungs-Paare konnten nicht aus der Konfigurationsdatei gelesen werden.")
