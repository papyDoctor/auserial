# Examples

All examples below live in the [`examples/`](https://github.com/papyDoctor/auserial/tree/main/examples)
directory of the repository and run as-is on any Linux or macOS machine with
a serial device connected (adjust the path).

## Minimal — `examples/minimal.py`

```python
--8<-- "examples/minimal.py"
```

The `async with` block calls `open()` on entry and `close()` on exit, so the
file descriptor is released even if an exception is raised inside.

## Reading with a timeout — `examples/timeout.py`

```python
--8<-- "examples/timeout.py"
```

`asyncio.wait_for` bounds the read. On timeout the coroutine is cancelled
cleanly: AUSerial's internal lock and reader registration are released.

## Reading until a delimiter — `examples/read_until.py`

```python
--8<-- "examples/read_until.py"
```

Use the built-in `read_until()` rather than rolling your own loop —
it preserves surplus bytes (anything after the delimiter) in an internal
buffer so the next read gets them.

## Reading an exact number of bytes — `examples/read_exactly.py`

```python
--8<-- "examples/read_exactly.py"
```

`read()` may return fewer bytes than requested. For fixed-size protocol
frames, accumulate until the exact count is reached.

## Concurrent reader + periodic writer — `examples/good_way_to_use.py`

```python
--8<-- "examples/good_way_to_use.py"
```

The whole point of `auserial`: one coroutine parked in `serial.read()`
while another writes periodically — no threads, no callback gymnastics.

## Listing ports — `examples/list_ports.py`

```python
--8<-- "examples/list_ports.py"
```

Synchronous helper, useful at program startup to pick the right device
based on `description` / `hwid` rather than a hardcoded path.
