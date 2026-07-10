import os
import sys
import time

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

class FileLock:
    def __init__(self, lock_path: str, default_timeout: int = 15):
        self.lock_path: str = lock_path
        self.lock_file = None
        self.default_timeout = default_timeout

    def __enter__(self) -> "FileLock":
        if not HAS_FCNTL:
            raise RuntimeError("fcntl module is unavailable. POSIX file locking is required on macOS and Linux.")
        self.lock_file = open(self.lock_path, "w")

        start_time = time.time()
        try:
            timeout_env = os.environ.get("LOCK_TIMEOUT_SECS")
            if timeout_env is not None:
                try:
                    timeout = int(timeout_env)
                except ValueError:
                    timeout = self.default_timeout
            else:
                timeout = self.default_timeout
        except Exception:
            timeout = self.default_timeout

        try:
            acquired = False
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                sys.stderr.write("Another instance is running. Waiting for lock...\n")
                sys.stderr.flush()

            while not acquired:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Timed out waiting for file lock after {timeout} seconds.")
                try:
                    fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except (BlockingIOError, OSError):
                    time.sleep(0.5)
        except BaseException:
            if self.lock_file:
                try:
                    self.lock_file.close()
                except Exception:
                    pass
                self.lock_file = None
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self.lock_file.close()
            except Exception:
                pass
            self.lock_file = None
