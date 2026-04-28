import termios
import os
import asyncio

# AUSerial (Async Unix Serial) — a minimal async serial port implementation using only the standard library.
# Designed for high performance and low latency in asyncio applications.
#
# Advantages over existing libraries:
# vs aioserial — aioserial wraps pySerial's blocking reads in run_in_executor, which spawns a thread for every I/O operation.
# The implementation uses add_reader/add_writer directly on the file descriptor, leveraging the kernel's epoll/kqueue mechanism.
# Zero threads, zero polling, truly non-blocking.
#
# vs pySerial — pySerial is entirely synchronous. A serial.read() call blocks the entire thread until data arrives or the timeout expires.
# In an async application, this freezes the event loop. The code suspends the coroutine and lets other tasks run while waiting for data.
#
# vs pyserial-asyncio — pyserial-asyncio uses asyncio's Transport/Protocol abstraction, which is callback-driven and verbose.
# You need to subclass Protocol, implement data_received, and wire up a Transport. The approach exposes a simple coroutine-based API
# (await serial.read(), await serial.write()) that is easier to reason about and compose with other async code.
#
#
# Additional qualities of the implementation:
# Direct os.open + termios configuration — no dependency on pySerial at all, just the standard library
# Async context manager for clean resource management
# Locks to prevent concurrent read/write conflicts
# Proper error propagation through Futures rather than silent failures
# Idempotent close() with cancellation of pending operations
# Minimal code (~80 lines) with no external dependencies

# The tradeoff is portability: this only works on Unix systems (Linux, macOS) since it relies on termios, os.open,
# and add_reader which requires a file descriptor backed by a real epoll/kqueue-compatible handle.
# Windows would need a completely different implementation.


_BYTESIZE = {5: termios.CS5, 6: termios.CS6, 7: termios.CS7, 8: termios.CS8}


class AUSerial:
    def __init__(
        self,
        path: str,
        baudrate: int = termios.B115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        xonxoff: bool = False,
        rtscts: bool = False,
    ):
        if bytesize not in _BYTESIZE:
            raise ValueError(
                f"bytesize must be one of {sorted(_BYTESIZE)}, got {bytesize}"
            )
        if parity not in ("N", "E", "O"):
            raise ValueError(f"parity must be 'N', 'E', or 'O', got {parity!r}")
        if stopbits not in (1, 2):
            raise ValueError(f"stopbits must be 1 or 2, got {stopbits}")

        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            attrs = termios.tcgetattr(self.fd)

            # Raw mode — no input/output processing, no echo, no signals.
            attrs[0] = 0  # iflag
            attrs[1] = 0  # oflag
            attrs[3] = 0  # lflag

            # cflag: base + bytesize + parity + stopbits + hw flow control.
            cflag = termios.CLOCAL | termios.CREAD | _BYTESIZE[bytesize]
            if parity in ("E", "O"):
                cflag |= termios.PARENB
            if parity == "O":
                cflag |= termios.PARODD
            if stopbits == 2:
                cflag |= termios.CSTOPB
            if rtscts:
                cflag |= termios.CRTSCTS
            attrs[2] = cflag

            # Software flow control.
            if xonxoff:
                attrs[0] |= termios.IXON | termios.IXOFF

            # Baudrate.
            attrs[4] = baudrate
            attrs[5] = baudrate

            # Non-blocking reads: return immediately if no data.
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0

            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            # Clear any stale bytes in the OS receive buffer from a previous session.
            # Note: for devices that stream immediately on open (GPS modules, MCUs that print boot banners),
            # this will discard the first few bytes — almost always desired, but worth knowing.
            termios.tcflush(self.fd, termios.TCIFLUSH)
        except Exception:
            os.close(self.fd)
            raise

        self._loop: asyncio.AbstractEventLoop | None = None
        self._read_future: asyncio.Future[bytes] | None = None
        self._write_future: asyncio.Future[int] | None = None
        self._read_buf: bytearray = bytearray()

    async def open(self) -> None:
        self._loop = asyncio.get_running_loop()
        # Locks must be created in the context of the event loop that will use them
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    async def _read_raw(self, n_bytes: int = 64) -> bytes:
        """Read directly from fd. Caller must hold _read_lock."""
        assert self._loop is not None, "Call open() first"

        loop = self._loop
        self._read_future = loop.create_future()
        future = self._read_future

        def on_readable():
            try:
                chunk = os.read(self.fd, n_bytes)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            else:
                if not future.done():
                    future.set_result(chunk)
            finally:
                loop.remove_reader(self.fd)

        loop.add_reader(self.fd, on_readable)
        return await future or b""

    async def read(self, n_bytes: int = 64) -> bytes:
        assert self._loop is not None, "Call open() first"
        async with self._read_lock:
            if self._read_buf:
                data = bytes(self._read_buf[:n_bytes])
                del self._read_buf[:n_bytes]
                return data
            return await self._read_raw(n_bytes)

    async def read_until(self, terminator: bytes, size: int | None = None) -> bytes:
        assert self._loop is not None, "Call open() first"
        async with self._read_lock:
            buf = self._read_buf

            while True:
                idx = buf.find(terminator)
                if idx != -1:
                    end = idx + len(terminator)
                    result = bytes(buf[:end])
                    del buf[:end]
                    return result

                if size is not None and len(buf) >= size:
                    result = bytes(buf[:size])
                    del buf[:size]
                    return result

                chunk = (
                    await self._read_raw()
                )  # always reads from fd, never touches buf
                if not chunk:
                    if buf:
                        result = bytes(buf)
                        buf.clear()
                        return result
                    raise EOFError("EOF reached before terminator")

                buf.extend(chunk)

    async def write(self, data: bytes) -> int:
        assert self._loop is not None, "Call open() first"
        async with self._write_lock:
            loop = self._loop
            self._write_future = loop.create_future()
            future = self._write_future

            def on_writable():
                try:
                    n = os.write(self.fd, data)
                except Exception as e:
                    if not future.done():
                        future.set_exception(e)
                else:
                    if not future.done():
                        future.set_result(n)
                finally:
                    loop.remove_writer(self.fd)

            loop.add_writer(self.fd, on_writable)
            return await future

    def close(self) -> None:
        if self._loop is None:
            return  # idempotent
        loop = self._loop
        if self._read_future and not self._read_future.done():
            self._read_future.cancel()
        if self._write_future and not self._write_future.done():
            self._write_future.cancel()
        loop.remove_reader(self.fd)
        loop.remove_writer(self.fd)
        os.close(self.fd)
        self._loop = None

    # Context manager async
    async def __aenter__(self) -> "AUSerial":
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.close()
