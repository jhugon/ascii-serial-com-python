"""
Circular buffer implementation in python
"""

from __future__ import annotations
from typing import Any, Callable, Optional, Union
from collections.abc import Sequence, MutableSequence


class Circular_Buffer:
    """
    Implements a circular buffer using a collection
    """

    def __init__(self, N: int, collInitFunc: Callable[[int], MutableSequence]) -> None:
        """
        N: int capacity of buffer
        collInitFunc: a function that returns
            the desired collection when called with a length argument
            Examples:
                lambda n: [0]*n
                lambda n: str('0')*n
                lambda n: bytearray(n)
        """
        self.capacity = N
        self.collInitFunc = collInitFunc
        self.data = self.collInitFunc(N)
        self.iStart = 0
        self.iStop = 0
        self.size = 0

    def push_back(self, b: Sequence) -> None:
        """
        Add elements to the end of the circular buffer
        Does so by overwriting earlier contents if necessary

        b: collection of elements

        """
        for x in b:
            self.data[self.iStop] = x
            self.iStop = (self.iStop + 1) % self.capacity
            if self.size == self.capacity:
                self.iStart = (self.iStart + 1) % self.capacity
            else:
                self.size += 1

    def push_front(self, b: Sequence) -> None:
        """
        Add elements to the start of the circular buffer

        Does so by overwriting later contents if necessary

        b: collection of elements
        """
        for x in reversed(b):
            self.iStart = (self.iStart - 1) % self.capacity
            self.data[self.iStart] = x
            if self.size == self.capacity:
                self.iStop = (self.iStop - 1) % self.capacity
            else:
                self.size += 1

    def pop_front(self, N: int) -> Sequence:
        """
        Pop the first N elements off of start of the circular buffer and return them
        """
        if N > self.capacity:
            raise ValueError(
                "N is greater than capacity of buffer: ", N, " > ", self.capacity
            )
        N = min(N, self.size)
        result = self.collInitFunc(N)
        for i in range(min(N, self.size)):
            result[i] = self.data[self.iStart]
            self.iStart = (self.iStart + 1) % self.capacity
            self.size -= 1
        return result

    def pop_back(self, N: int) -> Sequence:
        """
        Pop the last N elements off of the end of the circular buffer and return them
        """
        if N > self.capacity:
            raise ValueError(
                "N is greater than capacity of buffer: ", N, " > ", self.capacity
            )
        N = min(N, self.size)
        result = self.collInitFunc(N)
        for i in range(N):
            j = (self.iStop - N + i) % self.capacity
            result[i] = self.data[j]
        self.iStop = (self.iStop - N) % self.capacity
        self.size -= N
        return result

    def removeFrontTo(self, val: Any, inclusive: bool = False) -> None:
        """
        Remove front elements up to given val

        If there is a long string of the value, then inclusive only removes the first

        if inclusive, then remove the given val, otherwise all before the given val

        returns None
        """
        while True:
            if self.isEmpty():
                return
            elif self.data[self.iStart] == val:
                if inclusive:
                    self.iStart = (self.iStart + 1) % self.capacity
                    self.size -= 1
                return
            else:
                self.iStart = (self.iStart + 1) % self.capacity
                self.size -= 1

    def removeBackTo(self, val: Any, inclusive: bool = False) -> None:
        """
        Remove back elements to given val

        if inclusive, then remove the given val, otherwise all after the given val

        returns None
        """
        while True:
            if self.isEmpty():
                return
            elif self.data[self.iStop - 1] == val:
                if inclusive:
                    self.iStop = (self.iStop - 1) % self.capacity
                    self.size -= 1
                return
            else:
                self.iStop = (self.iStop - 1) % self.capacity
                self.size -= 1

    def count(self, x: Any) -> int:
        """
        Returns number of elements equal to x in buffer
        """
        result = 0
        for i in range(self.size):
            j = (self.iStart + i) % self.capacity
            if self.data[j] == x:
                result += 1
        return result

    def findFirst(self, x: Any) -> Optional[int]:
        """
        Returns the index (from iStart) of the first occurance of x

        Returns None if no x found
        """
        for i in range(self.size):
            j = (self.iStart + i) % self.capacity
            if self.data[j] == x:
                return i
        return None

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, i: int) -> Any:
        """
        Access the circular buffer like a collection
        """
        if i >= len(self):
            raise IndexError("index", i, " >= len: ", len(self))
        return self.data[(self.iStart + i) % self.capacity]

    def isFull(self) -> bool:
        return len(self) == self.capacity

    def isEmpty(self) -> bool:
        return len(self) == 0

    def __str__(self) -> str:
        return "{}: capacity: {} size: {} iStart: {} iStop: {}\n    {}".format(
            self.__class__.__name__,
            self.capacity,
            self.size,
            self.iStart,
            self.iStop,
            self.data,
        )


class Circular_Buffer_Bytes(Circular_Buffer):
    """
    Implements a circular buffer as a bytearray object
    """

    def __init__(self, N: int):
        super().__init__(N, lambda n: bytearray(n))

    def removeFrontTo(self, val: Union[bytes, int], inclusive: bool = False) -> None:
        """
        Remove front elements up to given val

        If there is a long string of the value, then inclusive only removes the first

        if inclusive, then remove the given val, otherwise all before the given val

        returns None
        """
        if isinstance(val, bytes):
            if len(val) != 1:
                raise ValueError("val must be int or length 1 bytes, not:", val)
            else:
                val = val[0]
        super().removeFrontTo(val, inclusive=inclusive)

    def removeBackTo(self, val: Union[bytes, int], inclusive: bool = False) -> None:
        """
        Remove back elements to given val

        if inclusive, then remove the given val, otherwise all after the given val

        returns None
        """
        if isinstance(val, bytes):
            if len(val) != 1:
                raise ValueError("val must be int or length 1 bytes, not:", val)
            else:
                val = val[0]
        super().removeBackTo(val, inclusive=inclusive)

    def count(self, x: Union[bytes, int]) -> int:
        """
        Returns number of elements equal to x in buffer
        """
        if isinstance(x, bytes):
            if len(x) != 1:
                raise ValueError("x must be int or length 1 bytes, not:", x)
            else:
                x = x[0]

        return super().count(x)

    def findFirst(self, x: Union[bytes, int]) -> Optional[int]:
        """
        Returns the index (from iStart) of the first occurance of x

        Returns None if no x found
        """
        if isinstance(x, bytes):
            if len(x) != 1:
                raise ValueError("x must be int or length 1 bytes, not:", x)
            else:
                x = x[0]

        return super().findFirst(x)


if __name__ == "__main__":
    pass
