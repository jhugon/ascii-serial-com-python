"""
Functions to setup TTYs
"""

import inspect
import logging
import termios
import tty
import sys
from pathlib import Path
from typing import Union, Optional, IO


def setup_tty(f: Union[IO, int, str, Path], speed: int, arduino_dont_hup: bool = True):
    """
    Setup the TTY for use with ASCII Serial Com.

    The TTY is set to raw mode and VMIN is set to 0. This seems
    to be what the Arduino serial monitor does.

    f: file object or file descriptor (int)

    speed: an int baud rate. Must be a supported value by termios
        If you use an unsupported value, will print out the
        available options and raise Exception
    """
    try:
        speedconstname = "B{:d}".format(speed)
        speedconst = getattr(termios, speedconstname)
    except AttributeError:
        errorstr = f"baud not supported: {speed}"
        logging.error(errorstr)
        members = [x[0] for x in inspect.getmembers(termios)]
        avail_speeds = [
            x[1:] for x in members if len(x) > 2 and x[0] == "B" and x[1].isdecimal()
        ]
        avail_speeds.sort(key=int)
        logging.info(f"Available options: {', '.join(avail_speeds)}")
        raise Exception(errorstr)
    else:
        if isinstance(f, str) or isinstance(f, Path):
            with open(f) as openfile:
                _do_setup(openfile, speedconst, arduino_dont_hup)
        elif isinstance(f, int) or isinstance(f, IO):
            _do_setup(f, speedconst, arduino_dont_hup)


def _do_setup(f: Union[IO, int], speedconst: str, arduino_dont_hup: bool):
    tty.setraw(f)
    tty_attrs = termios.tcgetattr(f)
    tty_attrs[4] = speedconst
    tty_attrs[5] = speedconst

    # Sets blocking/non-blocking/timeout behavior
    # This blocks for 0.1 second at most
    tty_attrs[6][termios.VMIN] = 0
    tty_attrs[6][termios.VTIME] = 1

    # Arduino resets on hardware hangup, that is when DTR goes low
    # This disables that
    # On command line, `stty -F <dev> -hupcl` does similar
    if arduino_dont_hup:
        tty_attrs[2] &= ~termios.HUPCL

    tty_attrs[3] &= ~termios.ECHO  # added for STLink

    termios.tcsetattr(f, termios.TCSAFLUSH, tty_attrs)
