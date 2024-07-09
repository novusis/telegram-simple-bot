import io
import time
import traceback
from datetime import datetime


class CachedItem:
    def __init__(self, items, timeout):
        self.items = items
        self.timeout = timeout
        self.start_accessed = now_unix_time()
        self.last_accessed = now_unix_time()

    def get_first(self):
        self.last_accessed = now_unix_time()
        return self.items[0] if self.items else None

    def get(self, silent=False):
        if not silent:
            self.last_accessed = now_unix_time()
        return self.items

    def get_online_time(self):
        return now_unix_time() - self.start_accessed

    def is_timeout_passed(self):
        return (now_unix_time() - self.last_accessed) > self.timeout


def convert_seconds_to_hms(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def convert_seconds_to_hm(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return "{:02d} hour {:02d} min".format(hours, minutes)


def convert_unix_timestamp_to_readable(unix_timestamp):
    return datetime.fromtimestamp(unix_timestamp).strftime('%d.%m.%y/%H:%M:%S')


def now_unix_time():
    return time.time()


def log_stack(message, limit=5, start=-2):
    stack_buffer = io.StringIO()
    traceback.print_stack(limit=limit, file=stack_buffer)
    stack_content = stack_buffer.getvalue()
    stack_buffer.close()
    stack_lines = stack_content.splitlines()
    if stack_lines:
        stack_lines = stack_lines[:-start]
    stack_content = '\n'.join(stack_lines)
    LIGHT_GREEN = "\033[92m"
    RESET_COLOR = "\033[0m"
    full_message = f"{message}{LIGHT_GREEN}{stack_content}{RESET_COLOR}"
    print(full_message)


def log_error(message):
    LIGHT_GREEN = "\033[91m"
    RESET_COLOR = "\033[0m"
    full_message = f"{convert_unix_timestamp_to_readable(now_unix_time())}| {LIGHT_GREEN}{message}{RESET_COLOR}\n"
    log_stack(full_message, limit=5, start=-3)


def get_string_by_utc(utc):
    return utc.strftime('%Y-%m-%d %H:%M:%S')


def get_utc_by_string(date):
    return datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
