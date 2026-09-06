"""Owned file-description leases, not PID liveness guesses.

The parent holds a fresh inode before committing an execution intent and passes
that same locked description through exec. Recovery opens a *different*
description; it cannot acquire the lease while any original holder survives.
Missing, replaced, linked or inaccessible leases mean unknown, never exited.
"""

import fcntl
import os
import re
import stat
from contextlib import contextmanager

from backend.analytics_fixture import private_directory


def execution_directory(state, execution_id):
    if not isinstance(execution_id, str) or re.fullmatch(r"exec_[a-f0-9]{32}", execution_id) is None:
        raise ValueError("invalid owned execution identity")
    return private_directory(state) / "workers" / execution_id


def create_lease(state, execution_id):
    root = private_directory(state) / "workers"
    root.mkdir(mode=0o700, exist_ok=True)
    private_directory(root)
    directory = execution_directory(state, execution_id)
    directory.mkdir(mode=0o700)
    (directory / "tmp").mkdir(mode=0o700)
    fd = os.open(directory / ".lease", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        info = os.fstat(fd)
        return fd, info.st_dev, info.st_ino, directory / "tmp"
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def released_lease(state, record):
    directory = execution_directory(state, record["execution_id"])
    private_directory(directory.parent)
    private_directory(directory)
    fd = os.open(directory / ".lease", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or (info.st_dev, info.st_ino) != (record["lease_dev"], record["lease_ino"])):
            raise ValueError("execution lease identity changed")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield directory
    finally:
        os.close(fd)


def clear_owned_spill(directory):
    """Called only while holding the proven-exited lease. Keep all evidence.

    Only known DuckDB disposable names in this exact execution's private tmp
    directory are removable. Validate the entire bounded list before unlinking;
    an unknown object means uncertainty and retains the execution reservation.
    """
    temporary = private_directory(directory / "tmp")
    fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        names = os.listdir(fd)
        if len(names) > 1024:
            raise ValueError("unexpected worker spill count")
        owned = []
        for name in names:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (re.fullmatch(r"duckdb_temp_storage_[A-Z0-9]+-[0-9]+\.tmp", name) is None
                    or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1):
                raise ValueError("refusing unknown worker temporary object")
            owned.append((name, info.st_dev, info.st_ino, info.st_size))
        for name, dev, ino, _size in owned:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (dev, ino):
                raise ValueError("worker temporary object changed after exit")
            os.unlink(name, dir_fd=fd)
        os.fsync(fd)
        return {"temp_removed_files": len(owned), "temp_removed_bytes": sum(item[3] for item in owned)}
    finally:
        os.close(fd)
