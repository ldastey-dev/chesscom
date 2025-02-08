import os
import sys
import time
import ctypes
import requests
import platform
import subprocess
from dotenv import load_dotenv


# Setup environment variables
load_dotenv()
 

# Authentication headers
# Using Chrome user agent to fly low and avoid the radar :)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
}

# Make sure we have all the dependencies installed
# Avoids having to manually remember to run this command
def install_requirements():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    requirements_path = os.path.join(base_dir, '..', '..', 'requirements.txt')

    if os.path.exists(requirements_path):
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', '-r', requirements_path])
    else:
        print("requirements.txt not found\n")


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
            print(f"Failed to inhibit sleep: {e}\n")


# Allow the system to sleep
def enable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    elif platform.system() == "Linux":
        try:
            subprocess.Popen(['sudo', 'pkill', '-f', 'systemd-inhibit'])
        except Exception as e:
            print(f"Failed to allow sleep: {e}\n")


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
            
            print(f"Execution time: {execution_time:.2f} seconds\n")
            print(f"Execution time: {(execution_time/60):.2f} minutes\n")
            
            enable_system_sleep()
        
        return result

    return wrapper


# Generate a unique file name so subsequent runs don't overwrite local edits!
def get_unique_filename(folder, fname, extension):
    counter = 1

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path to requirements.txt relative to the base directory
    path = f'{os.path.join(base_dir, '..', '..')}/{folder}'
    
    file = f"{path}/{fname}.{extension}"

    os.makedirs(folder, exist_ok=True)

    while os.path.exists(file):
        file = f"{folder}/{fname}_{counter}.{extension}"
        counter += 1
    return file


# Wrap external calls with retry and error handling 
def request_handler(url, headers=None, retries=3, backoff_factor=0.3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            
            response.raise_for_status()
            return response
        except (ConnectionError, requests.HTTPError, requests.Timeout) as e:
            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt)
                time.sleep(sleep_time)
            else:
                print(f'Failed to fetch data from {url}\n')
                raise e