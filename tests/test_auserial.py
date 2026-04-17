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


async def test_read_receives_bytes_from_the_other_end(
    pty_pair: tuple[int, str],
) -> None:
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


async def test_read_until_finds_terminator(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r\n")
        data = await serial.read_until(b"\r\n")
        assert data == b"hello\r\n"


async def test_read_until_stops_at_terminator_not_end_of_buffer(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r\nworld")
        data = await serial.read_until(b"\r\n")
        assert data == b"hello\r\n"


async def test_read_until_multichar_terminator(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"\x02E\r")
        data = await serial.read_until(b"\x02E\r")
        assert data == b"\x02E\r"


async def test_read_until_terminator_split_across_chunks(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r")
        await asyncio.sleep(0.01)
        os.write(master_fd, b"\n")
        data = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=1.0)
        assert data == b"hello\r\n"


async def test_read_until_size_cap_returns_when_reached(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"abcdefgh")  # no terminator
        data = await asyncio.wait_for(serial.read_until(b"\r\n", size=4), timeout=1.0)
        assert len(data) >= 4
        assert b"\r\n" not in data


async def test_read_until_terminator_wins_over_size(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hi\r\nmore")
        data = await serial.read_until(b"\r\n", size=100)
        assert data == b"hi\r\n"


async def test_read_until_without_open_asserts(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    serial = AUSerial(slave_path)
    try:
        with pytest.raises(AssertionError):
            await serial.read_until(b"\r\n")
    finally:
        os.close(serial.fd)


async def test_read_until_timeout_via_wait_for(pty_pair: tuple[int, str]) -> None:
    _, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=0.1)


async def test_read_until_after_timeout_still_works(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=0.1)
        os.write(master_fd, b"recovery\r\n")
        data = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=1.0)
        assert data == b"recovery\r\n"


async def test_read_until_preserves_surplus_for_next_read(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r\nworld")

        data1 = await serial.read_until(b"\r\n")
        assert data1 == b"hello\r\n"

        # This is the critical assertion: "world" must still be readable
        data2 = await serial.read(64)
        assert data2 == b"world"


async def test_read_until_preserves_surplus_for_next_read_until(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r\nworld\r\n")

        data1 = await serial.read_until(b"\r\n")
        assert data1 == b"hello\r\n"

        data2 = await serial.read_until(b"\r\n")
        assert data2 == b"world\r\n"


async def test_read_until_eof_behavior(pty_pair: tuple[int, str]) -> None:
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"partial")
        os.close(master_fd)

        # Either we get partial data OR EOF
        try:
            data = await serial.read_until(b"\r\n")
            assert data in (b"partial",)
        except EOFError:
            pass


async def test_read_until_eof_with_empty_buffer_raises(
    pty_pair: tuple[int, str],
) -> None:
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        os.close(master_fd)  # immediate EOF

        with pytest.raises(EOFError):
            await serial.read_until(b"\r\n")


async def test_concurrent_reads_are_serialized(pty_pair: tuple[int, str]) -> None:
    """Two concurrent read() calls must not interleave — one gets all the data, the other waits."""
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        results = []

        async def do_read() -> None:
            data = await asyncio.wait_for(serial.read(64), timeout=2.0)
            results.append(data)

        # Launch two concurrent readers before any data arrives
        task1 = asyncio.create_task(do_read())
        task2 = asyncio.create_task(do_read())
        await asyncio.sleep(0)  # let both tasks reach their await point

        os.write(master_fd, b"first")
        await asyncio.sleep(0.01)
        os.write(master_fd, b"second")

        await asyncio.gather(task1, task2)

        # Each chunk must go to exactly one reader, never split or merged wrongly
        assert sorted(results) == [b"first", b"second"]


async def test_concurrent_read_until_calls_are_serialized(
    pty_pair: tuple[int, str],
) -> None:
    """Two concurrent read_until() calls must serialize — no interleaving of their buffers."""
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        results = []

        async def do_read_until() -> None:
            data = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=2.0)
            results.append(data)

        task1 = asyncio.create_task(do_read_until())
        task2 = asyncio.create_task(do_read_until())
        await asyncio.sleep(0)

        os.write(master_fd, b"line1\r\nline2\r\n")

        await asyncio.gather(task1, task2)

        # Each full line must land in exactly one call
        assert sorted(results) == [b"line1\r\n", b"line2\r\n"]


async def test_read_blocked_by_read_until_in_progress(
    pty_pair: tuple[int, str],
) -> None:
    """A read() must not steal bytes from a read_until() that is in progress."""
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        read_until_started = asyncio.Event()
        read_result: list[bytes] = []
        read_until_result: list[bytes] = []

        async def slow_read_until() -> None:
            # Signal that we've started, then wait for the terminator
            read_until_started.set()
            data = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=2.0)
            read_until_result.append(data)

        async def concurrent_read() -> None:
            await read_until_started.wait()
            await asyncio.sleep(0)  # yield to let read_until block on the lock
            data = await asyncio.wait_for(serial.read(64), timeout=2.0)
            read_result.append(data)

        task1 = asyncio.create_task(slow_read_until())
        task2 = asyncio.create_task(concurrent_read())
        await asyncio.sleep(0)

        os.write(master_fd, b"hello\r\nworld")

        await asyncio.gather(task1, task2)

        # read_until must get the full line, read() gets the surplus — never the reverse
        assert read_until_result == [b"hello\r\n"]
        assert read_result == [b"world"]


async def test_read_until_blocked_by_read_in_progress(
    pty_pair: tuple[int, str],
) -> None:
    """A read_until() must wait if a read() already holds the lock."""
    master_fd, slave_path = pty_pair

    async with AUSerial(slave_path) as serial:
        # read() goes first and consumes its chunk
        read_task = asyncio.create_task(asyncio.wait_for(serial.read(64), timeout=2.0))
        await asyncio.sleep(0)  # let read() reach its await on the future

        read_until_task = asyncio.create_task(
            asyncio.wait_for(serial.read_until(b"\r\n"), timeout=2.0)
        )
        await asyncio.sleep(0)

        os.write(master_fd, b"chunk1")
        await asyncio.sleep(0.01)
        os.write(master_fd, b"then\r\n")

        read_data = await read_task
        read_until_data = await read_until_task

        # read() gets first chunk, read_until() gets the next line — no overlap
        assert read_data == b"chunk1"
        assert read_until_data == b"then\r\n"


async def test_read_until_with_non_matching_surplus(pty_pair):
    master_fd, slave_path = pty_pair
    async with AUSerial(slave_path) as serial:
        os.write(master_fd, b"hello\r\nwo")
        data1 = await serial.read_until(b"\r\n")
        assert data1 == b"hello\r\n"  # leaves b"wo" in buffer

        os.write(master_fd, b"rld\r\n")
        data2 = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=1.0)
        assert data2 == b"world\r\n"
