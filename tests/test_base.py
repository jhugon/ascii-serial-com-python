import io
import logging
import unittest
import unittest.mock
from unittest.mock import patch
from asciiserialcom.base import (
    check_register_number,
    check_register_content,
    convert_from_hex,
    convert_to_hex,
)
from asciiserialcom.host import Host
from asciiserialcom.message import ASC_Message
from asciiserialcom.circularBuffer import Circular_Buffer_Bytes
from asciiserialcom.errors import *
from asciiserialcom.utilities import (
    breakStapledIntoWriteRead,
    MemoryWriteStream,
    Tracer,
    TestMemoryStreamHost,
)
import crcmod  # type: ignore
import datetime
import trio
import trio.testing


class TestMessaging(unittest.TestCase):
    def setUp(self):
        self.crcFunc = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")

    def test_send_message(self):
        async def run_test(self, frame, args):
            nRegBits = 32
            got_to_cancel = False
            with trio.move_on_after(1) as cancel_scope:
                async with trio.open_nursery() as nursery:
                    testHolder = TestMemoryStreamHost(nursery, nRegBits)
                    host = testHolder.get_host()
                    device_streams = testHolder.get_device_streams()
                    await host.send_message(*args)
                    result = await device_streams.receive_some()
                    self.assertEqual(result, frame)
                    got_to_cancel = True
                    cancel_scope.cancel()
            self.assertTrue(got_to_cancel)

        for frame, args in [
            (b">00w.", (b"w", b"")),
            (b">00w0123456789ABCDEF.", (b"w", b"0123456789ABCDEF")),
            (b">00w" + b"A" * 56 + b".", (b"w", b"A" * 56)),
            (b">00zERrPhU10mfn.", (b"z", b"ERrPhU10mfn")),
        ]:
            with self.subTest(i="frame={}, args={}".format(frame, args)):
                frame += "{:04X}".format(self.crcFunc(frame)).encode("ascii") + b"\n"
                trio.run(run_test, self, frame, args)

    def test_send_stream_message(self):
        async def run_test(self, arg):
            nRegBits = 32
            got_to_cancel = False
            with trio.move_on_after(1) as cancel_scope:
                async with trio.open_nursery() as nursery:
                    testHolder = TestMemoryStreamHost(nursery, nRegBits)
                    host = testHolder.get_host()
                    device_streams = testHolder.get_device_streams()
                    last = None
                    for i in range(256 * 4):
                        await host.send_stream_message(arg)
                        result = await device_streams.receive_some()
                        counter = int(result[4:6].decode(), 16)
                        data = result[7:-6]
                        self.assertEqual(data, arg)
                        if last == 255:
                            self.assertEqual(counter, 0)
                        elif last:
                            self.assertEqual(counter, last + 1)
                        last = counter
                    got_to_cancel = True
                    cancel_scope.cancel()
            self.assertTrue(got_to_cancel)

        for arg in [
            b"",
            b"abcdef",
            b"x" * 53,
        ]:
            with self.subTest(i="{}".format(arg)):
                trio.run(run_test, self, arg)


class TestStreaming(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s",
        )
        self.crcFunc = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")

    def tearDown(self):
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s"
        )

    def test_receive_to_channel_with_lockstep_stream(self):
        async def run_on_all(func, collection):
            for i, x in enumerate(collection):
                logging.debug(f"About to run on element {i}")
                await func(x)
                logging.debug(f"finished running on element {i}")
            logging.debug(f"run on all finished")

        async def run_test(self, messages, payloads):
            nRegBits = 32
            host, device = trio.testing.lockstep_stream_pair()
            host_write_stream, host_read_stream = breakStapledIntoWriteRead(host)
            got_to_cancel = False
            with trio.move_on_after(10) as cancel_scope:
                (result_send_chan, result_recv_chan,) = trio.open_memory_channel(0)
                async with result_recv_chan:
                    async with trio.open_nursery() as nursery:
                        host = Host(
                            nursery, host_read_stream, host_write_stream, nRegBits
                        )
                        host.forward_received_s_messages_to(result_send_chan)
                        nursery.start_soon(run_on_all, device.send_all, messages)
                        result = []
                        with trio.move_on_after(0.5):
                            while True:
                                nMissed, payload = await result_recv_chan.receive()
                                logging.debug(f"received message: {payload}")
                                self.assertEqual(nMissed, 0)
                                result.append(payload)
                        logging.debug("result")
                        logging.debug(result)
                        logging.debug("messages")
                        logging.debug(payloads)
                        self.assertEqual(result, payloads)
                        got_to_cancel = True
                        cancel_scope.cancel()
            self.assertTrue(got_to_cancel)

        for messages in [
            [b">00s" + (b"%02X" % x) + b"," + (b"%04i" % x) + b"." for x in range(256)],
            [
                b">00s" + (b"%02X" % x) + b"," + (b"%04i" % (256 - x)) + b"."
                for x in range(256)
            ],
        ]:
            with self.subTest(i="messages={}".format(messages)):
                messages = [
                    x + "{:04X}".format(self.crcFunc(x)).encode("ascii") + b"\n"
                    for x in messages
                ]
                payloads = [message[7:11] for message in messages]
                trio.run(run_test, self, messages, payloads)

    @unittest.skip("Have trouble with the memory stream")
    def test_receive_to_channel_with_memory_stream(self):
        async def run_on_all(func, collection):
            for i, x in enumerate(collection):
                logging.debug(f"About to run on element {i}")
                await func(x)
                logging.debug(f"finished running on element {i}")
            logging.debug(f"run on all finished")

        async def run_test(self, messages):
            nRegBits = 32
            host, device = trio.testing.memory_stream_pair()
            host_write_stream, host_read_stream = breakStapledIntoWriteRead(host)
            got_to_cancel = False
            with trio.move_on_after(10) as cancel_scope:
                (result_send_chan, result_recv_chan,) = trio.open_memory_channel(0)
                async with result_recv_chan:
                    async with trio.open_nursery() as nursery:
                        host = Host(
                            nursery, host_read_stream, host_write_stream, nRegBits
                        )
                        host.forward_received_s_messages_to(result_send_chan)
                        nursery.start_soon(run_on_all, device.send_all, messages)
                        result = []
                        with trio.move_on_after(3):
                            while True:
                                msg = await result_recv_chan.receive()
                                logging.debug(f"received message: {msg}")
                                result.append(msg.get_packed())
                        logging.info("result")
                        logging.info(result)
                        logging.info("messages")
                        logging.info(messages)
                        self.assertEqual(result, messages)
                        got_to_cancel = True
                        cancel_scope.cancel()
            self.assertTrue(got_to_cancel)

        for messages in [[b">00s" + (b"%04i" % x) + b"." for x in range(5)]]:
            with self.subTest(i="messages={}".format(messages)):
                messages = [
                    x + "{:04X}".format(self.crcFunc(x)).encode("ascii") + b"\n"
                    for x in messages
                ]
                trio.run(run_test, self, messages, instruments=[Tracer()])

    def test_receive_to_asyncfile(self):
        async def run_on_all(func, collection):
            for i, x in enumerate(collection):
                logging.debug(f"About to run on element {i}")
                await func(x)
                logging.debug(f"finished running on element {i}")
            logging.debug(f"run on all finished")

        async def run_test(self, messages):
            nRegBits = 32
            host, device = trio.testing.lockstep_stream_pair()
            host_write_stream, host_read_stream = breakStapledIntoWriteRead(host)
            got_to_cancel = False
            with io.BytesIO() as outfile_sync:
                outfile = trio.wrap_file(outfile_sync)
                with trio.move_on_after(10) as cancel_scope:
                    async with trio.open_nursery() as nursery:
                        host = Host(
                            nursery, host_read_stream, host_write_stream, nRegBits
                        )
                        host.forward_received_s_messages_to(outfile)
                        await run_on_all(device.send_all, messages)
                        got_to_cancel = True
                        cancel_scope.cancel()
                outfile_sync.seek(0)
                result = outfile_sync.read()
                logging.debug(result)
                self.assertTrue(result, b"".join(messages))
            self.assertTrue(got_to_cancel)

        for messages in [
            [b">00s" + (b"%02X" % x) + b"," + (b"%04i" % x) + b"." for x in range(256)],
            [
                b">00s" + (b"%02X" % x) + b"," + (b"%04i" % (256 - x)) + b"."
                for x in range(256)
            ],
        ]:
            with self.subTest(i="messages={}".format(messages)):
                messages = [
                    x + "{:04X}".format(self.crcFunc(x)).encode("ascii") + b"\n"
                    for x in messages
                ]
                trio.run(run_test, self, messages)

    def test_receive_to_syncfile(self):
        async def run_on_all(func, collection):
            for i, x in enumerate(collection):
                logging.debug(f"About to run on element {i}")
                await func(x)
                logging.debug(f"finished running on element {i}")
            logging.debug(f"run on all finished")

        async def run_test(self, messages):
            nRegBits = 32
            host, device = trio.testing.lockstep_stream_pair()
            host_write_stream, host_read_stream = breakStapledIntoWriteRead(host)
            got_to_cancel = False
            with io.BytesIO() as outfile_sync:
                with trio.move_on_after(10) as cancel_scope:
                    async with trio.open_nursery() as nursery:
                        host = Host(
                            nursery, host_read_stream, host_write_stream, nRegBits
                        )
                        host.forward_received_s_messages_to(outfile_sync)
                        await run_on_all(device.send_all, messages)
                        logging.debug("Finished run_on_all, cancelling cancel_scope")
                        got_to_cancel = True
                        cancel_scope.cancel()
                outfile_sync.seek(0)
                result = outfile_sync.read()
                logging.debug(result)
                self.assertTrue(result, b"".join(messages))
            self.assertTrue(got_to_cancel)

        for messages in [
            [b">00s" + (b"%02X" % x) + b"," + (b"%04i" % x) + b"." for x in range(256)],
            [
                b">00s" + (b"%02X" % x) + b"," + (b"%04i" % (256 - x)) + b"."
                for x in range(256)
            ],
        ]:
            with self.subTest(i="messages={}".format(messages)):
                messages = [
                    x + "{:04X}".format(self.crcFunc(x)).encode("ascii") + b"\n"
                    for x in messages
                ]
                trio.run(run_test, self, messages)


class TestUnpack(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s",
        )
        self.crcFunc = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")

    def tearDown(self):
        logging.basicConfig(
            # filename="test_integration.log",
            # level=logging.INFO,
            # level=logging.DEBUG,
            format="%(asctime)s %(levelname)s L%(lineno)d %(funcName)s: %(message)s"
        )

    def test_unpack_e(self):
        async def run_test(self, msg, exp_error_text, exp_error_cause_message):
            nRegBits = 32
            host, device = trio.testing.lockstep_stream_pair()
            host_write_stream, host_read_stream = breakStapledIntoWriteRead(host)
            async with trio.open_nursery() as nursery:
                host = Host(nursery, host_read_stream, host_write_stream, nRegBits)
                error_text, error_cause_message = host._unpack_received_e_message(msg)
                self.assertEqual(error_text, exp_error_text)
                self.assertEqual(error_cause_message, exp_error_cause_message)
                nursery.cancel_scope.cancel()

        for msg, error_text, error_causing_message in [
            (
                ASC_Message(b"0", b"0", b"e", b"10,w,123412345"),
                ERROR_CODE_DICT[0x10],
                ASC_Message(b"0", b"0", b"w", b"123412345"),
            ),
            (
                ASC_Message(b"0", b"0", b"e", b"30,s,FF"),
                ERROR_CODE_DICT[0x30],
                ASC_Message(b"0", b"0", b"s", b"FF"),
            ),
        ]:
            with self.subTest(i="msg={}".format(msg)):
                trio.run(run_test, self, msg, error_text, error_causing_message)


class TestChecks(unittest.TestCase):
    def test_check_register_content(self):

        for nBits in [8, 16, 32, 64]:
            for arg, comp in [
                (b"0", b"0"),
                (b"FF", b"FF"),
                (bytearray(b"ff"), b"FF"),
                ("ff", b"FF"),
                (0xFF, b"FF"),
                (0x3A, b"3A"),
                (3, b"3"),
            ]:
                lencomp = nBits // 4 - len(comp)
                if lencomp > 0:
                    comp = b"0" * lencomp + comp
                with self.subTest(i="nBits={}, arg={}".format(nBits, arg)):
                    self.assertEqual(check_register_content(arg, nBits), comp)

            for arg in [-3, 2.4, b"0" * (nBits // 4 + 1), b"0" * 200]:
                with self.subTest(i="nBits={}, arg={}".format(nBits, arg)):
                    with self.assertRaises(BadRegisterContentError):
                        check_register_content(arg, nBits)

    def test_check_register_number(self):

        for arg, comp in [
            (b"0", b"0000"),
            (b"FF", b"00FF"),
            (bytearray(b"ff"), b"00FF"),
            ("ff", b"00FF"),
            (0xFF, b"00FF"),
            (0x3A, b"003A"),
            (3, b"0003"),
        ]:
            with self.subTest(i="arg={}".format(arg)):
                self.assertEqual(check_register_number(arg), comp)

        for arg in [-3, 2.4, 0x1FFFF, b"0" * 5, b"0" * 200]:
            with self.subTest(i="arg={}".format(arg)):
                with self.assertRaises(BadRegisterNumberError):
                    check_register_number(arg)


class TestConvert(unittest.TestCase):
    def test_to_hex(self):
        self.assertEqual(convert_to_hex(b"e"), b"0E")
        self.assertEqual(convert_to_hex(b"e", 5), b"0000E")
        self.assertEqual(convert_to_hex(b"e", 0), b"E")
        self.assertEqual(convert_to_hex(b"e", 1), b"E")

        self.assertEqual(convert_to_hex("e"), b"0E")
        self.assertEqual(convert_to_hex("e", 5), b"0000E")
        self.assertEqual(convert_to_hex("e", 0), b"E")
        self.assertEqual(convert_to_hex("e", 1), b"E")

        self.assertEqual(convert_to_hex(bytearray(b"e")), b"0E")
        self.assertEqual(convert_to_hex(bytearray(b"e"), 5), b"0000E")
        self.assertEqual(convert_to_hex(bytearray(b"e"), 0), b"E")
        self.assertEqual(convert_to_hex(bytearray(b"e"), 1), b"E")

        self.assertEqual(convert_to_hex(255), b"FF")
        self.assertEqual(convert_to_hex(255, 5), b"000FF")
        self.assertEqual(convert_to_hex(255, 0), b"FF")
        self.assertEqual(convert_to_hex(255, 1), b"FF")

        self.assertEqual(convert_to_hex(0), b"00")
        self.assertEqual(convert_to_hex(0, 5), b"00000")
        self.assertEqual(convert_to_hex(0, 0), b"0")
        self.assertEqual(convert_to_hex(0, 1), b"0")

        for x in (b"", "", bytearray(b"")):
            with self.assertRaises(ValueError):
                convert_to_hex(x)

    def test_from_hex(self):
        self.assertEqual(convert_from_hex(b"e"), 14)
        self.assertEqual(convert_from_hex(bytearray(b"e")), 14)
        self.assertEqual(convert_from_hex("e"), 14)

        self.assertEqual(convert_from_hex(b"123"), 291)
        self.assertEqual(convert_from_hex(bytearray(b"123")), 291)
        self.assertEqual(convert_from_hex("123"), 291)

        self.assertEqual(convert_from_hex(b"0" * 20), 0)

        for x in (b"", "", bytearray(b"")):
            with self.assertRaises(ValueError):
                convert_from_hex(x)

        for x in (b"g", b"135x235", "x125"):
            with self.assertRaises(ValueError):
                convert_from_hex(x)
