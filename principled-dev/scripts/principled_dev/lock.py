"""POSIX advisory file lock."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import IO


class FileLock:
    def __init__(self, path: str | Path, *, blocking: bool = True):
        self.path = Path(path)
        self.blocking = blocking
        self._file: IO[bytes] | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file = self.path.open("a+b")
        operation = fcntl.LOCK_EX | (0 if self.blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(file.fileno(), operation)
        except BaseException:
            file.close()
            raise
        self._file = file
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._file is not None:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None
