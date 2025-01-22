import os
import time
import ctypes
import platform
import subprocess
from datetime import datetime
from dotenv import load_dotenv


# Setup environment variables
load_dotenv()
 


# Authentication headers
# Using Chrome user agent to fly low and avoid the radar :)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


# Prevent the system from sleeping
def disable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001) 
    elif platform.system() == "Linux":
        try:
            subprocess.Popen([
                'sudo', 'systemd-inhibit', '--what=handle-lid-switch', 
                '--why="Running Python program"', 'sleep', 'infinity'
            ])
        except Exception as e:
            print(f"Failed to inhibit sleep: {e}")


# Allow the system to sleep
def enable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    elif platform.system() == "Linux":
        try:
            subprocess.Popen(['sudo', 'pkill', '-f', 'systemd-inhibit'])
        except Exception as e:
            print(f"Failed to allow sleep: {e}")


# Decoration wrapper to calculate total execution time
def calculate_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            disable_system_sleep()
            result = func(*args, **kwargs)
        except Exception as e:
            print(f"Error: {e}")
            result = None
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"Execution time: {execution_time:.2f} seconds")
            print(f"Execution time: {(execution_time/60):.2f} minutes")
            
            enable_system_sleep()
        
        return result

    return wrapper


# Generate a unique file name so subsequent runs don't overwrite local edits!
def get_unique_filename(folder, fname, extension):
    counter = 1
    file = f"{folder}/{fname}.{extension}"

    os.makedirs(folder, exist_ok=True)

    while os.path.exists(file):
        file = f"{folder}/{fname}_{counter}.{extension}"
        counter += 1
    return file
