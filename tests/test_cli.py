import logging
import unittest
import trio
import trio.testing
import subprocess
import os
from functools import partial
from pathlib import Path

STDOUT = subprocess.DEVNULL
STDERR = subprocess.DEVNULL
# STDOUT = None
# STDERR = None


class TestCLI(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s",
        )
        host_to_device_fifo = Path("host_to_device.fifo")
        device_to_host_fifo = Path("device_to_host.fifo")
        if not host_to_device_fifo.exists():
            os.mkfifo(host_to_device_fifo)
        if not device_to_host_fifo.exists():
            os.mkfifo(device_to_host_fifo)
        self.host_to_device_fifo = host_to_device_fifo
        self.device_to_host_fifo = device_to_host_fifo

    def tearDown(self):
        self.host_to_device_fifo.unlink()
        self.device_to_host_fifo.unlink()
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s"
        )

    def test_read(self):
        async def sender(self, message_received, task_status=trio.TASK_STATUS_IGNORED):
            logging.debug(f"sender outfile: {self.device_to_host_fifo}")
            async with await trio.open_file(self.device_to_host_fifo, "wb") as f:
                task_status.started()
                logging.debug(f"Waiting for receiver to receive message")
                await message_received.wait()
                logging.debug(f"Received message received event, writing message")
                await f.write(b">00r0000,0F.9A58\n")
                await f.flush()
            logging.debug(f"Closed device_to_host_fifo")

        async def receiver(
            self, message_received, task_status=trio.TASK_STATUS_IGNORED
        ):
            logging.debug(f"receiver infile: {self.host_to_device_fifo}")
            try:
                async with await trio.open_file(self.host_to_device_fifo, "rb") as f:
                    task_status.started()
                    data = b""
                    while True:
                        logging.debug(f"Trying to read")
                        data += await f.read(1)
                        logging.debug(f"{data!r:4}")
                        if data == b">00r0000.DDA7\n":
                            message_received.set()
                            logging.debug(f"Sent message_received event!")
                            break
            except Exception as e:
                raise e
            finally:
                self.assertTrue(message_received.is_set())
                logging.debug(f"Closed host_to_device_fifo")

        async def run_test(self):
            test_timeout = 5  # seconds
            host_timeout = 2  # seconds
            message_received = trio.Event()
            with trio.move_on_after(test_timeout) as move_on_scope:
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(receiver, self, message_received)
                    nursery.start_soon(sender, self, message_received)
                    nursery.start_soon(
                        partial(
                            trio.run_process,
                            [
                                "asciiserialcom",
                                "--serial-send",
                                str(self.host_to_device_fifo),
                                str(self.device_to_host_fifo),
                                "read",
                                "0",
                                "--timeout",
                                str(host_timeout),
                            ],
                            stdout=STDOUT,
                            stderr=STDOUT,
                        )
                    )

        trio.run(run_test, self)

    def test_write(self):
        async def sender(self, message_received):
            async with await trio.open_file(self.device_to_host_fifo, "wb") as f:
                await message_received.wait()
                logging.debug(f"Sending message")
                await f.write(b">00w0000.252E\n")
                await f.flush()

        async def receiver(self, message_received):
            logging.debug(f"receiver infile: {self.host_to_device_fifo}")
            try:
                async with await trio.open_file(self.host_to_device_fifo, "rb") as f:
                    data = b""
                    while True:
                        logging.debug(f"Trying to read")
                        data += await f.read(1)
                        logging.debug(f"{data!r:4}")
                        if data == b">00w0000,FF.079B\n":
                            message_received.set()
                            logging.debug(f"Sent message_received event!")
                            break
            except Exception as e:
                raise e
            finally:
                self.assertTrue(message_received.is_set())
                logging.debug(f"Closed host_to_device_fifo")

        async def run_test(self):
            test_timeout = 10  # seconds
            host_timeout = 5  # seconds
            message_received = trio.Event()
            with trio.move_on_after(test_timeout) as move_on_scope:
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(receiver, self, message_received)
                    nursery.start_soon(sender, self, message_received)
                    nursery.start_soon(
                        partial(
                            trio.run_process,
                            [
                                "asciiserialcom",
                                "--serial-send",
                                str(self.host_to_device_fifo),
                                str(self.device_to_host_fifo),
                                "write",
                                "0",
                                "255",
                                "--timeout",
                                str(host_timeout),
                            ],
                            stdout=STDOUT,
                            stderr=STDOUT,
                        )
                    )

        trio.run(run_test, self)

    def test_stream(self):
        async def sender(self, start_streaming, stop_streaming):
            nMessagesSent = 0
            try:
                async with await trio.open_file(self.device_to_host_fifo, "wb") as f:
                    await start_streaming.wait()
                    while True:
                        await f.write(b">00s0 0 0 0.DE10\n")
                        await f.flush()
                        logging.debug(f"Sent message #{nMessagesSent}")
                        nMessagesSent += 1
                        await trio.sleep(0.1)
                        if stop_streaming.is_set():
                            break
            except Exception as e:
                raise e
            finally:
                self.assertTrue(start_streaming.is_set())
                self.assertTrue(stop_streaming.is_set())
                logging.debug(
                    f"Closed device_to_host_fifo after sending {nMessagesSent} messages"
                )

        async def receiver(self, start_streaming, stop_streaming):
            logging.debug(f"receiver infile: {self.host_to_device_fifo}")
            try:
                async with await trio.open_file(self.host_to_device_fifo, "rb") as f:
                    data = b""
                    while True:
                        # logging.debug(f"Trying to read")
                        newdata = await f.read(1)
                        if len(newdata) == 0:
                            continue
                        data += newdata
                        logging.debug(f"{data!r:4}")
                        if data == b">00n.3854\n":
                            start_streaming.set()
                            logging.debug(f"Sent start_streaming event!")
                            data = b""
                        elif data == b">00f.57C0\n":
                            stop_streaming.set()
                            logging.debug(f"Sent stop_streaming event!")
                            break
            except Exception as e:
                raise e
            finally:
                self.assertTrue(start_streaming.is_set())
                self.assertTrue(stop_streaming.is_set())
                logging.debug(f"Closed host_to_device_fifo")

        async def run_test(self):
            test_timeout = 10  # seconds
            host_timeout = 1  # seconds
            start_streaming = trio.Event()
            stop_streaming = trio.Event()
            with trio.move_on_after(test_timeout) as move_on_scope:
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(receiver, self, start_streaming, stop_streaming)
                    nursery.start_soon(sender, self, start_streaming, stop_streaming)
                    nursery.start_soon(
                        partial(
                            trio.run_process,
                            [
                                "asciiserialcom",
                                "--serial-send",
                                str(self.host_to_device_fifo),
                                str(self.device_to_host_fifo),
                                "stream",
                                "--stop-seconds",
                                str(host_timeout),
                            ],
                            stdout=STDOUT,
                            stderr=STDOUT,
                        )
                    )

        trio.run(run_test, self)
