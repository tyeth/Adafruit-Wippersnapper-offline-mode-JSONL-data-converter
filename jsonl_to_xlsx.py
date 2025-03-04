# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Tyeth Gundry for Adafruit Industries
#
# Converts JSONL datalogger log files to Excel/CSV format
# =======================================================
#
# For use with Adafruit WipperSnapper IoT Firmware - Offline Logging Mode
# Will convert all log files into matching output files, converting timesamps, I2C addresses to component names
# ( Requires a config.json file to map I2C addresses to component names ), and extracting board type from
# wipper_boot_out.txt file (or config.json fallback). If --merged option then filename column included too.
#
# Setup:
# ======
# pip install -r requirements.txt
#
# Usage:
# python jsonl_to_xlsx.py [log-path] [output-path] [config-path] [wipper-boot-path] [--interactive] [--recurse] [--csv]
#
# log-path: Path to the log file or folder containing log files (default: current folder)
# output-path: Path to the output file/folder (default: same as log-path)
# config-path: Path to the WipperSnapper Device config.json file (default: same as log-path)
# wipper-boot-path: Path to the wipper_boot_out.txt file (default: same as log-path)
# --interactive: Enter interactive mode to input paths manually
# --recurse, -r: Recurse into directories to find log files
# --csv: Output to CSV instead of Excel format (XLSX)
# --merged: Create single merged output file from all logs
#
# e.g. to process all .log files in current and subdirectories into a single output file:
# python jsonl_to_xlsx.py -r

import json
import os
import traceback
import time
import pandas as pd
import click


# Convert to DataFrame and save to Excel/CSV
def write_data_to_file(log_path, output_file_extension,output_path,excel_mode,data):
    if data:
        if not output_path.endswith(output_file_extension):
            if os.path.isdir(output_path):
                output_path = os.path.join(output_path, os.path.basename(log_path) + output_file_extension)
            else:
                output_path += output_file_extension
        if os.path.exists(output_path):
            new_timestamp = int(time.time())
            click.echo(f"Output file already exists: {output_path}, renaming to {output_path}.bak{new_timestamp}")
            os.rename(output_path, output_path + ".bak" + str(new_timestamp))
        df = pd.DataFrame(data)
        if excel_mode:
            print("Writing data to Excel...(this may take a while)")
            try:
                df.to_excel(output_path, index=False,)
                print(f"Excel file saved to {output_path}")
            except Exception as e:
                traceback.print_exc()
                # TODO: split at 1.04million row limit per sheet into new sheet (better for XlsWriter progress bar)
                #if e.__class__.__name__ == "ValueError" and "This sheet is too large" in e:
                print(f"*** Failed to save Excel file, attempting CSV instead. Original Error: {e}")
                return write_data_to_file(log_path,'.csv',output_path[:-5]+'.csv',excel_mode=False,data=data)
        else:
            print("Writing data to CSV...(usually fairly quick)")
            try:
                df.to_csv(output_path, index=False)
                print(f"CSV file saved to {output_path}")
            except:
                traceback.print_exc()
                return False
        return True
    else:
        print("No data to write.")
        return False

@click.command()
@click.argument('log-path',  type=click.Path(exists=True), required=False)
@click.argument('output-path',  type=click.Path(), required=False)
@click.argument('config-path',  type=click.Path(exists=True), required=False)
@click.argument('wipper-boot-path', type=click.Path(exists=True), required=False) #help="Used to extract board type", required=False)
@click.option('--interactive', is_flag=True, help='Enter interactive mode', default=False)
@click.option('--recurse', '-r', is_flag=True, help='Recurse into directories to find log files', default=False)
@click.option('--csv', is_flag=True, help='Output to CSV instead of XLSX', default=False)
@click.option('--merged',is_flag=True, help='Create single merged output file from all logs', default=False)
def jsonl_to_xlsx(config_path, log_path, output_path, wipper_boot_path,interactive, recurse, csv, merged, **kwargs):
    # Default paths
    interactive_mode = interactive or not any([config_path, log_path, output_path, wipper_boot_path])
    excel_mode = not csv
    output_file_extension = '.xlsx' if excel_mode else '.csv'
    default_folder = os.getcwd()
    log_path = log_path or default_folder


    if interactive_mode:
        click.echo("No path arguments passed. Entering interactive mode.")
        log_path = click.prompt('Enter the path to the log file or folder, (blank for current)', default=log_path)
        config_path = click.prompt('Optionally enter the path to the config file', default=config_path if config_path else log_path)
        wipper_boot_path = click.prompt('Optionally enter the path to the wipper_boot_out.txt file', default=wipper_boot_path if wipper_boot_path else log_path)
        output_path = click.prompt('Optionally enter the path to the output file/folder (blank for auto)', default=output_path if output_path else log_path)
        # check logpath and outputpath are both files or folders, not mixed
        if os.path.isdir(log_path) != os.path.isdir(output_path):
            click.echo("Log file/folder and output file/folder must both be files or folders. Adjusting output path.")
            output_path = log_path if os.path.isdir(log_path) else log_path+output_file_extension
        # if path for log_path then ask if user wants to recurse
        if os.path.isdir(log_path):
            recurse = recurse or click.confirm('Do you want to recurse into directories to find log files?', default=True)

    config_path = config_path or os.path.join(log_path if os.path.isdir(log_path) else default_folder, 'config.json')
    if merged:
        output_path = output_path or os.path.join(log_path if os.path.isdir(log_path) else default_folder, 'output' + output_file_extension)
    else:
        output_path = output_path or log_path
    wipper_boot_path = wipper_boot_path or os.path.join(log_path if os.path.isdir(log_path) else default_folder, 'wipper_boot_out.txt')

    # Confirm file paths with the user
    click.echo(f"Log file/folder: {log_path}")
    click.echo(f"Optional Config file: {config_path}")
    click.echo(f"Optional Wipper_boot_out.txt file: {wipper_boot_path}")
    click.echo(f"Output file/folder: {output_path}")
    if interactive_mode and not click.confirm('Do you want to proceed with these paths?', default=True):
        click.echo("Operation cancelled.")
        return

    print("*** Starting JSONL to Excel conversion ***")

    # Load the config file to map I2C addresses to component names
    config_data = {}
    if os.path.exists(config_path):
        if not os.path.isfile(config_path):
            config_path = os.path.join(config_path, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = json.load(f)

    i2c_mapping = {
        comp.get("i2cDeviceAddress"): comp.get("name", "Unknown") for comp in config_data.get("components", [])
    }
    print(f"Loaded {len(i2c_mapping)} I2C address mappings from config file.")

    # Extract board type from config or wipper_boot_out.txt
    board_type = config_data.get("exportedFromDevice", {}).get("rtc", "Unknown Board")
    if os.path.exists(wipper_boot_path):
        if not os.path.isfile(wipper_boot_path):
            wipper_boot_path = os.path.join(wipper_boot_path, "wipper_boot_out.txt")
        if os.path.exists(wipper_boot_path):
            with open(wipper_boot_path, "r") as f:
                for line in f:
                    if "Board ID:" in line:
                        board_type = line.split(":")[-1].strip()
                        break

    print(f"Board type: {board_type}")

    # Find all log files in the specified path (recurse)
    log_files = []
    if os.path.isdir(log_path):
        if recurse:
            for root, _, files in os.walk(log_path):
                log_files.extend([os.path.join(root, file) for file in files if file.endswith(('.log', '.jsonl'))])
        else:
            log_files = [os.path.join(log_path, file) for file in os.listdir(log_path) if file.endswith(('.jsonl', '.log'))]
    else:
        log_files = [log_path]

    print(f"Found {len(log_files)} log files to process.")
    errors = []
    data = []
    for log_file in log_files:
        if not merged:
            data = []
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                for i, line in enumerate(f):
                    if i==0 or (i + 1) % 1000 == 0:
                        print(f"Processing line {i+1} of {log_file}...")
                    try:
                        entry = json.loads(line.strip())
                        # Extract relevant fields
                        i2c_address = entry.get("i2c_address", "Unknown")
                        component_name = i2c_mapping.get(i2c_address, "Unknown")

                        structured_entry = {
                            "DateTime": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.get("timestamp",0))),
                            "Timestamp": entry.get("timestamp", "Unknown"),
                            "Value": entry.get("value", "Unknown"),
                            "SI Unit": entry.get("si_unit", "Unknown"),
                            "I2C Address": i2c_address
                        }
                        if component_name != "Unknown":
                            structured_entry["Component"] = component_name
                            structured_entry["Component@Address"] = f"{component_name}@{i2c_address}"
                        if board_type != "Unknown Board":
                            structured_entry["Board"] = board_type
                        if merged:
                            structured_entry["Filename"] = os.path.basename(log_file)

                        data.append(structured_entry)
                    except Exception as e:
                        errors.append(f"Error processing line {i+1} of {log_file}: {e}")
                        print(f"Error processing line {i+1} of {log_file}: {e}")
                        traceback.print_exc()
                        print(f"Line {i+1} content (pausing for 3secs to allow reading error/line):\n{line}")
                        time.sleep(3)
            print(f"Finished processing {i+1} lines from {log_file}")
            if not merged:
                # TODO: check output_path is dir and add logname then extension, otherwise if isfile (but recurse=True) assume one worksheet per filename (16k limit)
                if os.path.isdir(output_path):
                    new_output_path = os.path.join(output_path, log_file + output_file_extension)
                else:
                    new_output_path = output_path
                if not write_data_to_file(log_path,output_file_extension,new_output_path,excel_mode,data):
                    errors.append(f"Failed to write outputfile {output_path}({output_file_extension}) from {log_file} [data len: {len(data)}]")
        else:
            print(f"Log file not found: {log_file}")

    if merged:
        if not write_data_to_file(log_path,output_file_extension,output_path,excel_mode,data):
            errors.append(f"Failed to write outputfile {output_path}({output_file_extension}) from {log_file} [data len: {len(data)}]")

    print("*** Conversion complete ***")
    if errors:
        print(f"*** Caught {len(errors)} Processing Errors:")
        print(errors)

if __name__ == '__main__':
    jsonl_to_xlsx()
