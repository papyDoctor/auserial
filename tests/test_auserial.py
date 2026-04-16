import asyncio
import os

import pytest

from auserial import AUSerial


async def test_open_then_close(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    serial = AUSerial(slave_path)
    await serial.open()
    serial.close()


async def test_context_manager_opens_and_closes(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        assert serial._loop is not None
    assert serial._loop is None


async def test_close_is_idempotent(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    serial = AUSerial(slave_path)
    await serial.open()
    serial.close()
    serial.close()  # must not raise


async def test_read_without_open_asserts(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    serial = AUSerial(slave_path)
    try:
        with pytest.raises(AssertionError):
            await serial.read()
    finally:
        os.close(serial.fd)


async def test_write_reaches_the_other_end(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        n = await serial.write(b"ping")
        assert n == 4
        # give the kernel a tick to shuttle bytes from slave to master
        await asyncio.sleep(0.01)
        assert os.read(master_fd, 64) == b"ping"


async def test_read_receives_bytes_from_the_other_end(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"pong")
        data = await serial.read(64)
        assert data == b"pong"


async def test_read_respects_n_bytes(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"0123456789")
        data = await serial.read(4)
        assert len(data) <= 4


async def test_read_times_out_with_wait_for(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(serial.read(), timeout=0.1)


async def test_read_after_timeout_still_works(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(serial.read(), timeout=0.1)
        os.write(master_fd, b"late")
        data = await asyncio.wait_for(serial.read(), timeout=1.0)
        assert data == b"late"


async def test_concurrent_reader_and_writer(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:

        async def periodic_sender() -> None:
            for _ in range(3):
                await serial.write(b"AT\r\n")
                await asyncio.sleep(0.05)

        async def collect_from_master() -> bytes:
            buf = b""
            while buf.count(b"AT") < 3:
                await asyncio.sleep(0.02)
                try:
                    buf += os.read(master_fd, 64)
                except BlockingIOError:
                    pass
            return buf

        os.set_blocking(master_fd, False)
        _, received = await asyncio.wait_for(
            asyncio.gather(periodic_sender(), collect_from_master()),
            timeout=2.0,
        )
        assert received.count(b"AT") == 3
