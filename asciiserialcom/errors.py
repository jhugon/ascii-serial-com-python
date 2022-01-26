"""
Errors and Exceptions for ASCII Serial Com Python Interface
"""

import typing

ERROR_CODE_DICT = {
    0x00: "Unknown Error",
    0x01: "No Error",
    0x10: "Data too long for frame",
    0x11: "Problem computing checksum",
    0x12: "Invalid frame",
    0x13: "Invalid frame: missing or misplaced '.'",
    0x14: "Invalid frame: non-hex char where hex char expected",
    0x15: "Command not implemented",
    0x16: "Unexpected command",
    0x17: "Data too short",
    0x20: "Register block is null (invalid)",
    0x21: "Register number out of bounds",
    0x22: "Register value is wrong number of bytes",
    0x30: "Circular buffer out of bounds",
    0x31: "Circular buffer tried to pop from empty buffer",
    0x40: "File read error",
    0x41: "File write error",
}


def printError(error: Exception) -> None:
    args = error.args
    argsStr = " ".join([str(x) for x in args])
    print(f"{type(error).__name__}: {argsStr}")


class ASCErrorBase(Exception):
    """
    Abstract base class for Ascii-Serial-Com Errors
    """


class MalformedFrameError(ASCErrorBase):
    """
    Message frame does not meet specification
    """


class ResponseTimeoutError(ASCErrorBase):
    """
    Timeout while waiting for response frame
    """


class VersionMismatchErrorBase(ASCErrorBase):
    """
    Abstract base class for version mismatch errors
    """


class AsciiSerialComVersionMismatchError(VersionMismatchErrorBase):
    """
    Different ASC version in a received frame than expected.
    """


class ApplicationVersionMismatchError(VersionMismatchErrorBase):
    """
    Different application version byte received in a frame than expected.
    """


class BadCommandError(ASCErrorBase):
    """
    Frame command byte is not valid
    """


class BadDataError(ASCErrorBase):
    """
    Frame data section is not valid
    """


class BadRegisterNumberError(ASCErrorBase):
    """
    Register number is not valid
    """


class BadRegisterContentError(ASCErrorBase):
    """
    Register content is not valid
    """


class BadStreamMsgNumberError(ASCErrorBase):
    """
    Stream message number is not valid
    """


class TextFileNotAllowedError(ASCErrorBase):
    """
    Stream files must be opened in binary mode
    """


class ConfigurationError(ASCErrorBase):
    """
    __init__ args don't make sense
    """


class MessageIntegrityError(ASCErrorBase):
    """
    Corrupted message data
    """


class ShellArgumentError(ASCErrorBase):
    """
    Incorrect argument(s) to shell command
    """


class FileReadError(ASCErrorBase):
    """
    Incorrect argument(s) to shell command
    """


class EMessageUnpackError(ASCErrorBase):
    """
    Error unpacking 'e' command
    """


class DeviceError(ASCErrorBase):
    """
    Received error message from device
    """
