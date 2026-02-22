import os
import time

import requests
from dotenv import load_dotenv


def init():
    """
    Initialise environment variables from a .env file.

    Call this at the entry point of each script before accessing
    environment variables.
    """
    load_dotenv()


# Authentication headers
# Using Chrome user agent to fly low and avoid the radar :)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
}


def print_line(message):
    """
    Print a message to stdout.

    Args:
        message (str): The message to print.

    Returns:
        None
    """
    print(message)


# Decoration wrapper to calculate total execution time
def calculate_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
        except Exception as e:
            print_line(f"Error in {func.__name__}: {e}")
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time

            print_line(f"Execution time: {execution_time:.2f} seconds")
            print_line(f"Execution time: {(execution_time/60):.2f} minutes")

        return result

    return wrapper


# Generate a unique file name so subsequent runs don't overwrite local edits!
def get_unique_filename(folder, fname, extension):
    counter = 1

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, '..', '..', folder)

    file = os.path.join(path, f"{fname}.{extension}")

    os.makedirs(path, exist_ok=True)

    while os.path.exists(file):
        file = os.path.join(path, f"{fname}_{counter}.{extension}")
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
                print_line(f'Failed to fetch data from {url}')
                raise e
