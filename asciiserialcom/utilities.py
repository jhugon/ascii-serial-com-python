import trio
import trio.testing
import logging
from .host import Host

from typing import Tuple


class MemoryWriteStream:
    """
    Makes a network socket behave like a file
    """

    def __init__(self, stream):
        self.stream = stream

    async def write(self, data):
        await self.stream.send_all(data)

    async def flush(self):
        return


class MemoryReadStream:
    """
    Makes a network socket behave like a file
    """

    def __init__(self, stream):
        self.stream = stream

    async def read(self):
        return await self.stream.receive_some()


def breakStapledIntoWriteRead(stapledStream):
    return (
        MemoryWriteStream(stapledStream.send_stream),
        MemoryReadStream(stapledStream.receive_stream),
    )


class TestLockstepStreamHost:
    """
    For testing, creates Host hooked up directly to a StapledStream
    """

    def __init__(self, nursery: trio.Nursery, registerBitWidth: int):
        self.host_ss, self.device_ss = trio.testing.lockstep_stream_pair()
        self.host_write_stream, self.host_read_stream = breakStapledIntoWriteRead(
            self.host_ss
        )
        self.host = Host(
            nursery, self.host_read_stream, self.host_write_stream, registerBitWidth
        )

    def get_host(self) -> Host:
        return self.host

    def get_device_streams(self) -> trio.StapledStream:
        return self.device_ss


class TestMemoryStreamHost:
    """
    For testing, creates Host hooked up to a StapledStream through some buffers
    """

    def __init__(self, nursery: trio.Nursery, registerBitWidth: int):
        self.host_ss, self.device_ss = trio.testing.memory_stream_pair()
        self.host_write_stream, self.host_read_stream = breakStapledIntoWriteRead(
            self.host_ss
        )
        self.host = Host(
            nursery, self.host_read_stream, self.host_write_stream, registerBitWidth
        )

    def get_host(self) -> Host:
        return self.host

    def get_device_streams(self) -> trio.StapledStream:
        return self.device_ss


class TestSimpleLoopbackHost:
    """
    For testing, creates Host with fout hooked up to fin
    """

    def __init__(self, nursery: trio.Nursery, registerBitWidth: int):
        (
            self.send_stream,
            self.receive_stream,
        ) = trio.testing.memory_stream_one_way_pair()
        self.write_stream = MemoryWriteStream(self.send_stream)
        self.read_stream = MemoryReadStream(self.receive_stream)
        self.host = Host(nursery, self.read_stream, self.write_stream, registerBitWidth)

    def get_host(self) -> Host:
        return self.host


class ChannelWriteStream:
    """
    Makes a channel behave like a file
    """

    def __init__(self, chan):
        self.chan = chan

    async def write(self, data):
        await self.chan.send(data)

    async def flush(self):
        return


class ChannelReadStream:
    """
    Makes a channel behave like a file
    """

    def __init__(self, chan):
        self.chan = chan

    async def read(self):
        return await self.chan.receive()


class Tracer(trio.abc.Instrument):
    """
    Copied from Trio documentation October 2021
    """

    def before_run(self):
        logging.debug("!!! run started")

    def _print_with_task(self, msg, task):
        # repr(task) is perhaps more useful than task.name in general,
        # but in context of a tutorial the extra noise is unhelpful.
        logging.debug(f"{msg}: {task.name}")

    def task_spawned(self, task):
        self._print_with_task("### new task spawned", task)

    def task_scheduled(self, task):
        self._print_with_task("### task scheduled", task)

    def before_task_step(self, task):
        self._print_with_task(">>> about to run one step of task", task)

    def after_task_step(self, task):
        self._print_with_task("<<< task step finished", task)

    def task_exited(self, task):
        self._print_with_task("### task exited", task)

    def before_io_wait(self, timeout):
        if timeout:
            logging.debug(f"### waiting for I/O for up to {timeout} seconds")
        else:
            logging.debug("### doing a quick check for I/O")
        self._sleep_time = trio.current_time()

    def after_io_wait(self, timeout):
        duration = trio.current_time() - self._sleep_time
        logging.debug(f"### finished I/O check (took {duration} seconds)")

    def after_run(self):
        logging.debug("!!! run finished")
