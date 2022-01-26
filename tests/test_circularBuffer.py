import unittest
import unittest.mock
from asciiserialcom.circularBuffer import Circular_Buffer
from asciiserialcom.circularBuffer import Circular_Buffer_Bytes


class TestCircularBufferList(unittest.TestCase):
    def setUp(self):
        self.buf = Circular_Buffer(10, lambda n: [0] * n)

    def test_push_back_until_full(self):
        buf = self.buf
        # print("only init:",buf)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        buf.push_back([0])
        # print("push_back([0])",buf)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        buf.push_back(range(1, 6))
        # print("push_back(range(1,6))",buf)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)
        buf.push_back(range(6, 10))
        # print("push_back(range(6,10))",buf)
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)
        popped = buf.pop_back(len(buf))
        # print("pop_back(10)",buf)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(popped, list(range(10)))

    def test_push_back_past_full(self):
        buf = self.buf
        # print("only init:",buf)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        buf.push_back(range(11))
        # print("push_back([0])",buf)
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)
        popped = buf.pop_back(len(buf))
        # print("pop_back(10)",buf)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(popped, list(range(1, 11)))

        buf.push_back(range(100))
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)
        popped = buf.pop_back(len(buf))
        # print("pop_back(10)",buf)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(popped, list(range(90, 100)))

    def test_push_pop_back(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())

        buf.push_back(range(5))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 5)

        popped = buf.pop_back(2)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 3)
        self.assertEqual(popped, list(range(3, 5)))

        buf.push_back([1111, 2222, 3333])
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)

        popped = buf.pop_back(5)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        self.assertEqual(popped, [1, 2, 1111, 2222, 3333])

        buf.push_back(range(20))
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)

        with self.assertRaises(ValueError):
            popped = buf.pop_back(11)

        popped = buf.pop_back(10)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(len(buf), 0)
        self.assertEqual(popped, list(range(10, 20)))

    def test_push_front_until_full(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        buf.push_front([0])
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        buf.push_front(range(1, 6))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)
        buf.push_front(range(6, 10))
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)
        popped = buf.pop_back(len(buf))
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(popped, [6, 7, 8, 9, 1, 2, 3, 4, 5, 0])

    def test_push_front_past_full(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        buf.push_front(range(20))
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)
        popped = buf.pop_back(len(buf))
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(popped, list(range(10)))

    def test_push_pop_front(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())

        buf.push_front(range(5))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 5)

        popped = buf.pop_front(2)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 3)
        self.assertEqual(popped, list(range(2)))

        buf.push_front([1111, 2222, 3333])
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)

        popped = buf.pop_front(5)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        self.assertEqual(popped, [1111, 2222, 3333, 2, 3])

        buf.push_front(range(20))
        self.assertTrue(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 10)

        with self.assertRaises(ValueError):
            popped = buf.pop_front(11)

        popped = buf.pop_front(10)
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())
        self.assertEqual(len(buf), 0)
        self.assertEqual(popped, list(range(10)))

    def test_push_pop_front_back(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())

        buf.push_front(range(5))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 5)

        popped = buf.pop_front(2)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 3)
        self.assertEqual(popped, list(range(2)))

        buf.push_back([1111, 2222, 3333])
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)

        popped = buf.pop_back(5)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        self.assertEqual(popped, [3, 4, 1111, 2222, 3333])

    def test_removeFrontTo(self):
        buf = self.buf

        buf.push_front(range(8))
        buf.removeFrontTo(4, inclusive=True)
        self.assertEqual(len(buf), 3)

        buf.push_back([55] * 3)
        buf.removeFrontTo(6, inclusive=False)
        self.assertEqual(len(buf), 5)

        self.assertEqual(buf.pop_back(len(buf)), [6, 7] + [55] * 3)
        self.assertTrue(buf.isEmpty())
        buf.removeFrontTo(6, inclusive=True)
        self.assertTrue(buf.isEmpty())

        buf.push_back(range(20))
        buf.removeFrontTo(19, inclusive=True)
        self.assertTrue(buf.isEmpty())

    def test_removeBackTo(self):
        buf = self.buf

        buf.push_front(range(8))
        buf.removeBackTo(4, inclusive=True)
        self.assertEqual(len(buf), 4)

        buf.push_back([55] * 3)
        buf.removeBackTo(2, inclusive=False)
        self.assertEqual(len(buf), 3)

        self.assertEqual(buf.pop_back(len(buf)), [0, 1, 2])
        self.assertTrue(buf.isEmpty())
        buf.removeBackTo(6, inclusive=True)
        self.assertTrue(buf.isEmpty())

        buf.push_back(range(20))
        buf.removeBackTo(0, inclusive=True)
        self.assertTrue(buf.isEmpty())

    def test_count(self):
        buf = self.buf

        self.assertEqual(buf.count(3), 0)

        buf.push_back(range(4))
        self.assertEqual(buf.count(3), 1)
        buf.push_back([2] * 3)
        self.assertEqual(buf.count(2), 4)
        buf.push_back([99] * 20)
        self.assertEqual(buf.count(99), buf.capacity)

    def test_findFirst(self):
        buf = self.buf

        self.assertIsNone(buf.findFirst(3))

        buf.push_back(range(5))
        self.assertIsNone(buf.findFirst(8))
        self.assertEqual(buf.findFirst(3), 3)
        buf.push_front(range(2))
        self.assertEqual(buf.findFirst(3), 5)
        buf.push_back(range(50))
        self.assertEqual(buf.findFirst(45), 5)

    def test_getitem(self):
        buf = self.buf
        with self.assertRaises(IndexError):
            buf[0]
        with self.assertRaises(IndexError):
            buf[5]
        buf.push_back(range(5))
        with self.assertRaises(IndexError):
            buf[5]
        self.assertEqual(buf[0], 0)
        self.assertEqual(buf[4], 4)
        buf.push_back(range(20))
        self.assertEqual(buf[0], 10)
        self.assertEqual(buf[9], 19)


class TestCircularBufferBytes(unittest.TestCase):
    def setUp(self):
        self.buf = Circular_Buffer_Bytes(10)

    def test_push_pop(self):
        buf = self.buf
        self.assertFalse(buf.isFull())
        self.assertTrue(buf.isEmpty())

        buf.push_front(bytes(range(5)))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 5)

        popped = buf.pop_front(2)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 3)
        self.assertEqual(popped, bytes(range(2)))

        buf.push_back(bytes([111, 222, 255]))
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 6)

        popped = buf.pop_back(5)
        self.assertFalse(buf.isFull())
        self.assertFalse(buf.isEmpty())
        self.assertEqual(len(buf), 1)
        self.assertEqual(popped, bytes([3, 4, 111, 222, 255]))

    def test_count(self):
        buf = self.buf

        self.assertEqual(buf.count(3), 0)
        self.assertEqual(buf.count(b"3"), 0)

        buf.push_back(b"01234")
        self.assertEqual(buf.count(b"3"), 1)
        buf.push_back(b"2" * 3)
        self.assertEqual(buf.count(b"2"), 4)
        self.assertEqual(buf.count(b"2"[0]), 4)
        buf.push_back(b"\xFF" * 20)
        self.assertEqual(buf.count(b"\xFF"), buf.capacity)

    def test_findFirst(self):
        buf = self.buf

        self.assertIsNone(buf.findFirst(b"3"))
        self.assertIsNone(buf.findFirst(b"3"[0]))

        buf.push_back(b"012345")
        self.assertIsNone(buf.findFirst(b"8"))
        self.assertEqual(buf.findFirst(b"3"), 3)
        self.assertEqual(buf.findFirst(b"3"[0]), 3)
        buf.push_front(b"01")
        self.assertEqual(buf.findFirst(b"3"), 5)
        buf.push_back(bytes(range(256)))
        self.assertEqual(buf.findFirst(b"\xFB"), 5)

    def test_removeFrontTo(self):
        buf = self.buf

        buf.push_back(b"0123456")
        buf.removeFrontTo(b"0", inclusive=False)
        self.assertEqual(len(buf), 7)
        self.assertEqual(buf.pop_back(len(buf)), b"0123456")


if __name__ == "__main__":
    unittest.main()
