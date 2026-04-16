"""Shared fixtures: a PTY pair that stands in for a real serial port.

`os.openpty()` returns a master/slave pair of real file descriptors backed by
the kernel's terminal driver. AUSerial opens the slave via its path, the test
writes to / reads from the master to simulate the other end of the wire.
"""

import os
from collections.abc import Iterator

import pytest


@pytest.fixture
def pty_pair() -> Iterator[tuple[int, str]]:
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    try:
        yield master_fd, slave_path
    finally:
        for fd in (master_fd, slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass
