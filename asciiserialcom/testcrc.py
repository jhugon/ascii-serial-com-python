#!/usr/bin/env python3


class CrcMkr:
    def __init__(self, nBits, poly):
        """
        nBits is number of bits in the register
        poly is an unsigned number nBits long
        """
        self.nBits = nBits
        self.poly = poly
        self.bitMask = 2 ** nBits - 1
        self.register = 0

    def __call__(self, data):
        """
        Input data should be a bytearray
        """
        # data = bytearray(data+(self.nBits//8)*b'\0')
        data = bytearray(data)
        register = self.register
        while len(data) != 0:
            currentByte = data.pop(-1)
            print(hex(currentByte), bin(currentByte))
            for iBit in range(8):
                inComingBit = None
                outGoingBit = None
                if True:
                    inComingBit = (currentByte >> (7 - iBit)) & 1
                else:
                    inComingBit = (currentByte >> iBit) & 1
                if True:
                    outGoingBit = (register >> (self.nBits - 1)) & 1
                    print("register pre-shift: ", bin(register))
                    register = (register << 1) & self.bitMask  # shift out
                    print("register post-shift: ", bin(register))
                    register |= inComingBit  # shift in
                else:
                    outGoingBit = register & 1
                    register = (register >> 1) & self.bitMask  # shift out
                    register |= inComingBit << (self.nBits - 1)  # shift in
                if outGoingBit == 1:
                    print("outGoingBit == 1")
                    register = (register ^ self.poly) & self.bitMask
                print(bin(currentByte), iBit, bin(register))
        self.register = register
        return register

    def __str__(self):
        return "CrcMkr nBits: {} poly: {:X} bitMask: {:X} register: {:X}".format(
            self.nBits, self.poly, self.bitMask, self.register
        )


if __name__ == "__main__":
    import crcmod  # type: ignore

    ##message = b"123456789"
    # message = b"~"
    # crc = CrcMkr(8,0x07)
    # print(crc)
    # print("My CRC: ",bin(crc(message)))
    # crcmodFun = crcmod.mkCrcFun(0x107,0,False,0)
    # print("crcmod: ",bin(crcmodFun(message)))

    print("starting...\n")
    crc4 = CrcMkr(4, 0b0011)
    print(crc4)
    bsStr = chr(0b11) + chr(0b01011011)
    bs = bsStr.encode("ASCII")
    print(bs, len(bs))
    print("crc2:", bin(crc4(bs)))  # should be 0b1110

    dnp = crcmod.predefined.mkPredefinedCrcFun("crc-16-dnp")
    print("{:X} == {}".format(dnp(b"123456789"), "EA82"))
    print("{:X}".format(dnp(b">00r0F.")))
    print("{:X}".format(dnp(b">02w0F 003FFF92.")))
