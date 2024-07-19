import io
import time
import traceback
from datetime import datetime


class CacheManager:
    cache_items = {}

    def __init__(self, add_callback, cached_timeout):
        self.add_callback = add_callback
        self.cached_timeout = cached_timeout

    def get_online(self):
        return len(self.cache_items.keys())

    def check_online(self):
        keys = list(self.cache_items.keys())
        close_sessions = {}
        for key in keys:
            if self.cache_items[key].is_timeout_passed():
                close_sessions[self.cache_items[key].get_first().external_id] = self.cache_items[key].get_online_time()
                del self.cache_items[key]
        return close_sessions

    def get_from_cache(self, key, def_get, show_error=True):
        if not key:
            log_error(f"CacheManager.get_from_cache error: no key <{key}>")
            return
        key = str(key)
        if key in self.cache_items:
            # get from cache
            return self.cache_items[key].get_first()

        user = def_get(key)
        if user:
            self.set_to_cache(key, user)
            if self.add_callback:
                self.add_callback(user)
            return user
        else:
            if show_error:
                log_error(f"CacheManager.get_from_cache error: no item by key <{key}>")
            return None

    def set_to_cache(self, key, user):
        key = str(key)
        if key in self.cache_items:
            self.cache_items[key].set([user])
        else:
            self.cache_items[key] = CachedItem([user], self.cached_timeout)

    def delete(self, key):
        key = str(key)
        if key in self.cache_items:
            del self.cache_items[key]


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

    def set(self, items):
        self.items = items
        self.last_accessed = now_unix_time()

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
