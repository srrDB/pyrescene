from __future__ import division

import rar
import os
import zlib
import sys

dir = "C:/dump/"
emp = dir + "empty.rar"

# get unknown CRC
for block in rar.RarReader(emp).read_all():
    print(block.explain())
    if block.rawtype == rar.BlockType.RarNewSub:
        rr = block.file_crc
        rrblock = block
    if block.rawtype == rar.BlockType.RarPackedFile:
        file = block.file_crc

# works for file, but not RR
tofind = rr
print("To find: %s or %x" % (tofind, tofind))

with open(emp, "rb") as f:
    bytes = f.read()
size = os.stat(emp).st_size
print("File size: %d" % size)

def give_range(begin, end):
    for i in range(begin, end + 1):
        for j in range(i, end + 1):
            yield (i, j)

cache = dict()

def get_crc(range, previous=None):
    try:
        if previous:
            return zlib.crc32(bytes[range[0]:range[1]], previous)
        else:
            return cache[range]
    except KeyError:
        if previous:
            cache[range] = zlib.crc32(bytes[range[0]:range[1]], previous)
        else:
            cache[range] = zlib.crc32(bytes[range[0]:range[1]])
        return cache[range]

def bruteforce():
    for (begin, end) in give_range(0, size):
    #    print("%d - %d" % (begin, end))

        crc = get_crc((begin, end), file)
        if tofind == crc or tofind == (crc & 0xffffffff) or tofind == ~crc:
            print("start: %d, end: %d" % (begin, end))
            sys.exit()

    #    crcfirst = get_crc((begin, end))
    #    for (be, en) in give_range(end, size):
    #        crc = get_crc((be, en), crcfirst)
    #        if tofind == crc or tofind == (crc & 0xffffffff) or tofind == ~crc:
    #            print("start: %d, end: %d" % (begin, end))
    #            print("start: %d, end: %d" % (be, en))
    #            sys.exit()

    #    percentage = ((begin + 1) / size) * 100
    #    if round(percentage, 1) % 5 == 0:
    #        print("%d%% checked" % round(percentage))
    pass

def calc_prev_crc():
    print(rrblock.block_position)
    print(rrblock.block_position + rrblock.header_size)
    print(rrblock.block_position + rrblock.header_size + rrblock.add_size)
    d = bytes[rrblock.block_position + rrblock.header_size:
              rrblock.block_position + rrblock.header_size + rrblock.add_size]
    print(len(d))
    assert zlib.crc32(d) == zlib.crc32(d, ~0xffffffff)
    crc = zlib.crc32(d, ~0x0fffffff)
    print("Calculated: %x" % (crc & 0xffffffff))
    print("Calculated: %x" % (~crc & 0xffffffff))
    print("Calculated: %x" % (~crc))
    print("Calculated: %x" % (crc))

    if tofind == crc or tofind == (crc & 0xffffffff) or tofind == ~crc:
        print("%x" % (crc))
        sys.exit()

calc_prev_crc()

print("Nothing found.")

"""662 - 662
662 - 663
663 - 663
Nothing found.

http://blog.affien.com/archives/2005/07/15/reversing-crc/
http://www.ross.net/crc/download/crc_v3.txt
"""
