import unittest
import unittest.mock
from asciiserialcom.message import ASC_Message
from asciiserialcom.errors import *
import crcmod  # type: ignore
import datetime


class TestCRC(unittest.TestCase):
    def setUp(self):
        self.crcFunc = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")

    def test_crc(self):
        reg_num = 2
        reg_val = 0x1234567A
        reply_message = b">00r%02X,%08X." % (reg_num, reg_val)
        good_crc = "{:04X}".format(self.crcFunc(reply_message)).encode("ascii")
        self.assertEqual(ASC_Message.compute_checksum(reply_message), good_crc)
        self.assertEqual(
            ASC_Message.compute_checksum(reply_message + b"aslkdgasbv\n"), good_crc
        )

    def test_crc_raises(self):
        for x in (b"", b"1251235", b">235235", b".", b"235.", b"22235\n", b"\n", b">"):
            with self.assertRaises(MalformedFrameError):
                ASC_Message.compute_checksum(x)


class TestChecks(unittest.TestCase):
    def setUp(self):
        pass

    def test_check_command(self):

        for i in [b"w", b"W", bytearray(b"W"), "W"]:
            with self.subTest(i=i):
                self.assertEqual(ASC_Message._check_command(i), b"w")

        for i in [b"www", b"", 3, b"2"]:
            with self.subTest(i=i):
                with self.assertRaises(BadCommandError):
                    ASC_Message._check_command(i)

    def test_check_data(self):

        for i in [
            (b"12345", b"12345"),
            ("12345", b"12345"),
            (bytearray(b"12345"), b"12345"),
            (b"", b""),
            (b"0" * 56, b"0" * 56),
        ]:
            with self.subTest(i=i):
                self.assertEqual(ASC_Message._check_data(b"w", i[0]), i[1])

        for i in [3, 2.4, b"0" * 57, b"0" * 200]:
            with self.subTest(i=i):
                with self.assertRaises(BadDataError):
                    ASC_Message._check_data(b"w", i)


class TestPackAndUnpack(unittest.TestCase):
    def setUp(self):
        self.crcFunc = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")

    def test_pack_message(self):

        for args, returnval in [
            ((b"0", b"0", b"w", b""), b">00w."),
            ((b"0", b"0", b"w", b"0"), b">00w0."),
            ((b"0", b"0", b"w", b"00000000"), b">00w00000000."),
        ]:
            with self.subTest(i="args={}, returnval={}".format(args, returnval)):
                returnval += (
                    "{:04X}".format(self.crcFunc(returnval)).encode("ascii") + b"\n"
                )
                msg = ASC_Message(*args)
                self.assertEqual(msg.get_packed(), returnval)

    def test_unpack_message(self):

        for frame, returnval in [
            (b">00w.", ASC_Message(b"0", b"0", b"w", b"")),
            (b">09x.", ASC_Message(b"0", b"9", b"x", b"")),
            (
                b">00w0123456789ABCDEF.",
                ASC_Message(b"0", b"0", b"w", b"0123456789ABCDEF"),
            ),
            (b">0Fw" + b"A" * 56 + b".", ASC_Message(b"0", b"F", b"w", b"A" * 56)),
        ]:
            with self.subTest(i="frame={}, returnval={}".format(frame, returnval)):
                frame += "{:04X}".format(self.crcFunc(frame)).encode("ascii") + b"\n"
                self.assertEqual(ASC_Message.unpack(frame), returnval)

        frame = b">\n"
        with self.assertRaises(MalformedFrameError):
            ASC_Message.unpack(frame)
        frame = b">.\n"
        with self.assertRaises(MessageIntegrityError):
            ASC_Message.unpack(frame)
        frame = b">."
        frame += "{:04X}".format(self.crcFunc(frame) + 1).encode("ascii") + b"\n"
        with self.assertRaises(MessageIntegrityError):
            ASC_Message.unpack(frame)

        for frame in [b">.", b">00.", b">0w.", b">w.", b""]:
            with self.subTest(i="frame: {}".format(frame)):
                frame += "{:04X}".format(self.crcFunc(frame)).encode("ascii") + b"\n"
                with self.assertRaises(MalformedFrameError):
                    ASC_Message.unpack(frame)
