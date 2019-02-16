#! /usr/bin/env python3

# Copyright (c) 2011-2012 Martin 'vadmium' Panter
# Copyright (c) 2014 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

"""Rar archive access, extended from "rarfile" module"""

USE_NUMPY = True

# Optimum values possibly depend on speed of Python and cache sizes and
# characteristics
buf_size = 0x10000
FILE_CRC_BUF = buf_size
FILE_COPY_CRC_BUF = buf_size

from rarfile import (
    Struct, crc32,
    S_BLK_HDR, S_FILE_HDR, S_SHORT, S_LONG,
    RAR_ID,
    RAR_BLOCK_MAIN, RAR_BLOCK_FILE, RAR_BLOCK_SUB, RAR_BLOCK_ENDARC,
    RAR_BLOCK_OLD_RECOVERY,
    RAR_LONG_BLOCK, RAR_SKIP_IF_UNKNOWN,
    RAR_MAIN_VOLUME, RAR_MAIN_RECOVERY, RAR_MAIN_FIRSTVOLUME, RAR_MAIN_LOCK,
    RAR_MAIN_NEWNUMBERING,
    RAR_FILE_SPLIT_BEFORE, RAR_FILE_SPLIT_AFTER, RAR_FILE_DICTMASK,
    RAR_FILE_DICT256, RAR_FILE_DICT4096, RAR_FILE_LARGE, RAR_FILE_SALT,
    RAR_FILE_UNICODE, RAR_FILE_EXTTIME,
    RAR_ENDARC_NEXT_VOLUME, RAR_ENDARC_DATACRC, RAR_ENDARC_REVSPACE,
    RAR_ENDARC_VOLNR,
    RAR_OS_WIN32, RAR_OS_UNIX,
)

import struct
import io

if USE_NUMPY:
    try:
        import numpy
    except ImportError:
        USE_NUMPY = False
if not USE_NUMPY:
    import array

RAR_MAIN_EXTRA = 2 + 4
MAIN_HDR_SIZE = S_BLK_HDR.size + RAR_MAIN_EXTRA

def write_main(volume, version, is_rr, is_first_vol, naming, is_lock):
    write_block(volume,
        type=RAR_BLOCK_MAIN,
        flags=RAR_MAIN_VOLUME ^
            is_rr * RAR_MAIN_RECOVERY ^
            (version >= 3 and is_first_vol) * RAR_MAIN_FIRSTVOLUME ^
            is_lock * RAR_MAIN_LOCK ^
            (naming >= 3) * RAR_MAIN_NEWNUMBERING,
        data=(
            (0 for i in range(RAR_MAIN_EXTRA)),
        ))

def write_file(volume, file, split_before, split_after, name, is_unicode,
dictsize, host_os, attr, accum_crc, dostime, xtime=None, size=None,
pack_size=None):
    size_64 = size_64_encode(pack_size, size)
    header_size = file_hdr_size(name, xtime, size_64)
    volume.seek(+header_size, io.SEEK_CUR)

    left = pack_size
    crc = 0 if split_after else accum_crc
    while left > 0:
        chunk = file.read(min(FILE_COPY_CRC_BUF, left))
        left -= len(chunk)
        volume.write(chunk)
        crc = crc32(chunk, crc)
        if split_after:
            accum_crc = crc32(chunk, accum_crc)

    parts = list()
    flags = (RAR_LONG_BLOCK ^ split_before * RAR_FILE_SPLIT_BEFORE ^
        split_after * RAR_FILE_SPLIT_AFTER ^ dictsize ^
        is_unicode * RAR_FILE_UNICODE)
    parts.append(S_FILE_HDR.pack(
        pack_size & bitmask(32), size & bitmask(32),
        host_os, crc, dostime, 20, ord("0"), len(name), attr
    ))

    if size_64 is not None:
        flags ^= RAR_FILE_LARGE
        parts.append(size_64)

    parts.append(name)

    if xtime is not None:
        flags ^= RAR_FILE_EXTTIME
        parts.append(xtime)

    volume.seek(-pack_size - header_size, io.SEEK_CUR)
    write_block(volume, RAR_BLOCK_FILE, flags, parts)
    volume.seek(+pack_size, io.SEEK_CUR)

    if split_after: return accum_crc

def file_hdr_size(name, xtime, size_64):
    size = S_BLK_HDR.size + S_FILE_HDR.size + len(name)
    if size_64 is not None:
        size += len(size_64)
    if xtime is not None: size += len(xtime)
    return size

FILE_PACK_POS = 0
FILE_DATA_POS = 4
FILE_OS_POS = 8
FILE_CRC_POS = 9
FILE_TIME_POS = 13
FILE_VER_POS = 17
FILE_METHOD_POS = 18
FILE_NAME_POS = 19
FILE_ATTR_POS = 21

DICT_DEFAULT = {2: RAR_FILE_DICT256, 3: RAR_FILE_DICT4096}
DICT_MIN = 64
DICT_MAX = 4096
DICT_POS = 5

def size_64_encode(packed, unpacked):
    if packed <= 1 << 31 and unpacked <= 1 << 31:
        return None
    return S_HIGH_SIZE.pack(packed >> 32, unpacked >> 32)

S_HIGH_SIZE = Struct("<LL")

def filename_encode(name, is_unicode):
    field = bytearray(name, "latin-1")
    if not is_unicode: return field

    field.append(0)
    field.append(1)  # Default MSB observed in the wild
    pos = 0
    left = len(name)
    while left > 0:
        opcode_byte = 0
        opcode_pos = BYTE_BITS
        chunk = bytearray()

        while opcode_pos >= FILENAME_OPCODE_BITS and left > 0:
            opcode_pos -= FILENAME_OPCODE_BITS

            if 1 == left:
                opcode = FILENAME_8_BIT
                chunk.append(ord(name[pos]))
                left = 0
            else:
                opcode = FILENAME_COPY
                size = min(COPY_LEN_MIN + bitmask(COPY_LEN_BITS), left)
                chunk.append(0 << COPY_MSB_BIT | size - COPY_LEN_MIN)
                pos += size
                left -= size

            opcode_byte |= opcode << opcode_pos

        field.append(opcode_byte)
        field.extend(chunk)

    return field

FILENAME_8_BIT = 0
FILENAME_MSB = 1
FILENAME_16_BIT = 2
FILENAME_COPY = 3

FILENAME_OPCODE_BITS = 2

COPY_LEN_MIN = 2
COPY_LEN_BITS = 7
COPY_MSB_BIT = 7

def time_encode(tm, frac=0):
    dostime = (
        tm.tm_sec >> 1 << DOS_2SEC_BIT ^
        tm.tm_min << DOS_MIN_BIT ^
        tm.tm_hour << DOS_HOUR_BIT ^
        tm.tm_mday << DOS_DAY_BIT ^
        tm.tm_mon << DOS_MONTH_BIT ^
        tm.tm_year - 1980 << DOS_YEAR_BIT)

    one_sec = tm.tm_sec & 1
    if not frac and not one_sec: return (dostime, None)

    flags = 1 << TIME_VALID_BIT
    flags |= one_sec << TIME_ONE_BIT
    frac = int(frac * 10 ** TIME_FRAC_DIGITS)

    size = TIME_FRAC_BYTES
    while size > 0:
        if frac & 0xFF: break
        frac >>= 8
        size -= 1
    flags |= size << TIME_SIZE_BIT

    xtime = bytearray(S_SHORT.pack(
        flags << MTIME_INDEX * TIME_FLAG_BITS))

    for _ in range(size):
        xtime.append(frac & 0xFF)
        frac >>= 8

    return (dostime, xtime)

DOS_2SEC_BIT = 0
DOS_2SEC_BITS = 5
DOS_MIN_BIT = 5
DOS_MIN_BITS = 6
DOS_HOUR_BIT = 11
DOS_HOUR_BITS = 5
DOS_DAY_BIT = 16
DOS_DAY_BITS = 5
DOS_MONTH_BIT = 21
DOS_MONTH_BITS = 4
DOS_YEAR_BIT = 25
DOS_YEAR_BITS = 7

MTIME_INDEX = 3
TIME_FLAG_BITS = 4
TIME_VALID_BIT = 3
TIME_ONE_BIT = 2
TIME_SIZE_BIT = 0
TIME_SIZE_BITS = 2
TIME_FRAC_DIGITS = 7
TIME_FRAC_BYTES = 3

ATTR_ARCHIVE = 5
ATTR_NORMAL = 7

def write_rr(version, host_os, volume, rr_count):
    prot_size = volume.tell()
    (rr_crcs, rr_sects) = rr_calc(volume, rr_count, prot_size)

    crc = crc32(rr_crcs, RR_CRC_INIT)
    for s in rr_sects:
        crc = crc32(s.buffer(), crc)

    prot_sect_count = len(rr_crcs) // S_SHORT.size
    size = prot_sect_count * RR_CRC_SIZE + rr_count * RR_SECT_SIZE

    if version < 3:
        write_block(volume,
            type=RAR_BLOCK_OLD_RECOVERY,
            flags=RAR_LONG_BLOCK ^ RAR_SKIP_IF_UNKNOWN,
            data=(
                S_LONG.pack(size),
                (20,),
                S_SHORT.pack(rr_count),
                S_LONG.pack(prot_sect_count),
                RR_PROTECT_2,
            ))
    else:
        write_block(volume,
            type=RAR_BLOCK_SUB,
            flags=RAR_LONG_BLOCK ^ RAR_SKIP_IF_UNKNOWN,
            data=(
                S_FILE_HDR.pack(size, size, host_os, crc, 0, 29, ord("0"),
                    len(RR_SUB_NAME), 0),
                RR_SUB_NAME,
                RR_PROTECT_3,
                S_LONG.pack(rr_count),
                struct.pack("<Q", prot_sect_count),
            ))

    volume.write(rr_crcs)
    for s in rr_sects:
        volume.write(s.buffer())

def rr_calc(volume, rr_count, size):
    volume.seek(0)

    rr_crcs = bytearray()
    rr_sects = tuple(BitVector(RR_SECT_SIZE) for _ in range(rr_count))

    aslice = 0
    while size > 0:
        if size < RR_SECT_SIZE:
            chunk = volume.read(size).ljust(RR_SECT_SIZE, bytes((0,)))
            size = 0
        else:
            chunk = volume.read(RR_SECT_SIZE)
            size -= RR_SECT_SIZE

        rr_crcs.extend(S_SHORT.pack(~crc32(chunk) & bitmask(16)))
        rr_sects[aslice].xor(chunk)
        aslice = (aslice + 1) % rr_count

    return (rr_crcs, rr_sects)

def calc_rr_count(version, total, vol_max):
    if version < 3:
        if vol_max < 50000:
            rr = 2
        if 50000 <= vol_max < 500000:
            rr = 4
        if 500000 <= vol_max:
            rr = 8

        return min(rr, quanta(total, RR_SECT_SIZE))

    if version >= 3:
        if total < RR_SECT_SIZE:
            return 1

        # Default recovery data size is 0.6%
        rr = total * 6 // RR_SECT_SIZE // 1000 + 2

        if rr >= RR_MAX:
            return RR_MAX

        if rr < 6:
            return rr
        else:
            return rr | 1  # Always an odd number

# Calculate space available for RR-protected data
def calc_prot_size(version, volsize, rr_count):
    # Allocate space for all RR-protected data and sector CRCs
    space = volsize - RR_HEADER_SIZE[version] - rr_count * RR_SECT_SIZE

    # Last quantum is useless if it cannot fit a CRC and any data
    last_q = last_quantum(space, RR_QUANTUM)
    if last_q <= RR_CRC_SIZE: space -= last_q

    prot_sect_count = quanta(space, RR_QUANTUM)
    return space - prot_sect_count * RR_CRC_SIZE

RR_MAX = 524288
RR_SECT_SIZE = 512
RR_CRC_SIZE = 2
RR_SUB_NAME = b"RR"
RR_PROTECT_2 = b"Protect!"
RR_PROTECT_3 = b"Protect+"
RR_HEADER_SIZE = {
    2: S_BLK_HDR.size + 4 + 1 + 2 + 4 + len(RR_PROTECT_2),
    3: S_BLK_HDR.size + S_FILE_HDR.size + len(RR_SUB_NAME) +
        len(RR_PROTECT_3) + 4 + 8,
}

# Why is this odd CRC initialiser used?
RR_CRC_INIT = 0xF0000000

# One quantum of space for each CRC
RR_QUANTUM = RR_SECT_SIZE + RR_CRC_SIZE

# Fast access to RR sectors as machine words instead of bytes.
# The xor operation is endian-agnostic.
# On an x86-64 computer,
#     element-wise array.array("L") xor operation was about 8 times faster
#         than bytearray
#     array-wise numpy.array(dtype=int) xor operation was about 3.5 times
#         faster than for element-wise array.array("L")
if USE_NUMPY:
    class BitVector:
        def __init__(self, size):
            self.array = numpy.frombuffer(bytearray(size),
                dtype=numpy.int)
        def buffer(self):
            return self.array
        def xor(self, buffer):
            return self.array.__ixor__(
                numpy.frombuffer(buffer, dtype=numpy.int))
else:
    class BitVector:
        def __init__(self, size):
            self.array = array.array("L", bytes(size))
        def buffer(self):
            return self.array
        def xor(self, buffer):
            for (i, v) in enumerate(array.array("L", buffer)):
                self.array[i] ^= v
            return self

def write_end(volume, version, flags, volnum, is_last_vol):
    size = volume.tell()
    volume.seek(0)
    crc = file_crc32(volume, size)

    if version >= 3:
        flags |= (RAR_SKIP_IF_UNKNOWN ^
            (not is_last_vol) * RAR_ENDARC_NEXT_VOLUME)
        parts = list()

        if flags & RAR_ENDARC_DATACRC:
            parts.append(S_LONG.pack(crc))
        if flags & RAR_ENDARC_VOLNR:
            parts.append(S_SHORT.pack(volnum))
        if flags & RAR_ENDARC_REVSPACE:
            parts.append(0 for _ in range(END_EXTRA))

        write_block(volume, RAR_BLOCK_ENDARC, flags, parts)

    return crc

def end_size(version, flags):
    if version < 3:
        return 0

    size = S_BLK_HDR.size

    if flags & RAR_ENDARC_DATACRC:
        size += 4
    if flags & RAR_ENDARC_VOLNR:
        size += 2
    if flags & RAR_ENDARC_REVSPACE:
        size += END_EXTRA

    return size

END_EXTRA = 7

# The "rar_decompress" function creates a Rar file but not in a reusable way
def write_block(file, btype, flags, data):
    block = bytearray()
    for part in data: block.extend(part)

    header = S_BLK_HDR_DATA.pack(btype, flags, S_BLK_HDR.size + len(block))

    crc = crc32(header)
    crc = crc32(block, crc)
    file.write(S_SHORT.pack(crc & bitmask(16)))

    file.write(header)
    file.write(block)

HDR_CRC_POS = 0
HDR_DATA_POS = 2
HDR_TYPE_POS = 2
HDR_FLAGS_POS = 3
HDR_SIZE_POS = 5
S_BLK_HDR_DATA = Struct("<BHH")  # S_BLK_HDR without the CRC field prepended

def file_crc32(file, size):
    crc = 0
    while size > 0:
        chunk = file.read(min(FILE_CRC_BUF, size))
        size -= len(chunk)
        crc = crc32(chunk, crc)
    return crc

def bitmask(size): return ~(~0 << size)
BYTE_BITS = 8
def quanta(total, quantum): return (total - 1) // quantum + 1
def last_quantum(total, quantum): return (total - 1) % quantum + 1
