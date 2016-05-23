#!/usr/bin/env python
# -*- coding: utf-8 -*-

import zlib
import struct
import binascii

# !Referenced file not found:
#   \Modern.Family.S02E02.1080p.BluRay.X264-7SinS\
#   7sins-modern.family.s02e02.1080p.x264.r00

path = "C:\\Users\\Me\\Desktop\\rebuild\\"
full = path + "7sins-modern.family.s02e02.1080p.x264.mkv"
part = path + "r27data.bin"
todo = path + "modern.family.s02e11.1080p.bluray-bia.r27"
filenb = 28  # r27

amount = 49999894  # amount of data stored in one volume
sfv_crc = 0xfa6f96b5
start = amount * filenb
end = start + amount

# Python 3.2's binascii.unhexlify() requires a byte string
MARKER = b"526172211a0700"
archive = b"f1fb7301000d00000000000000"
fileh = (b"5fbc740301560016f0fa020000605d038dc5d081f192273f14302e00a401"
		b"000000000000000000006d6f6465726e2e66616d696c792e733032653131"
		b"2e31303830702e626c757261792e783236342d6269612e6d6b76")
arend = b"75577b0f40140039e39c7a000000000000000000"

def extract_part(stored_file, output_file):
	with open(stored_file, "rb") as af:
		af.seek(start)
		with open(output_file, "wb") as data:
			data.write(af.read(amount))

def calc_crc(new_data, previous_crc=None):
	"""calculate the crc needed in the header from the file/RR
	previous_volume: not used: not a running crc!"""
	# we only look at the stored data in the current file
	if previous_crc:
		crc = zlib.crc32(new_data, previous_crc) & 0xFFFFFFFF
	else:
		crc = zlib.crc32(new_data) & 0xFFFFFFFF
	return crc

def fix_archive_flags(header, first_volume=False):
	""" necessary because we start from .rar or need .rar 
	first_volume is true if we need to create the .rar file """
	(flags,) = struct.unpack_from("<H", header, 3)
	if first_volume and not flags & 0x0100:
		flags += 0x0100  # fist volume flag
	elif not first_volume and flags & 0x0100:  # the flag is actually set
		flags -= 0x0100
	fixed = header[:3] + struct.pack("<H", flags) + header[5:]
	header_crc = zlib.crc32(fixed[2:]) & 0xFFFF
	return struct.pack("<H", header_crc) + fixed[2:]

def fix_file_flags(header, first_volume=False):
	""" necessary because we start from .rar or need .rar 
	first_volume is true if we need to create the .rar file """
	(flags,) = struct.unpack_from("<H", header, 3)
	if first_volume and flags & 0x0001:
		flags -= 0x0001  # file continued from previous volume
	elif not first_volume and not flags & 0x0001:
		flags += 0x0001
	fixed = header[:3] + struct.pack("<H", flags) + header[5:]
	header_crc = zlib.crc32(fixed[2:]) & 0xFFFF
	return struct.pack("<H", header_crc) + fixed[2:]

def fix_file_header(file_header, part_crc, timedate_32bit):
	""" fix the headers before the data """
	lenb = len(file_header)
	# fix crc of the RAR part
	before = file_header[:7 + 9]
	after = file_header[7 + 9 + 4:]
	crc_fixed = before + struct.pack("<I", part_crc) + after
	assert lenb == len(crc_fixed) == 86

	# fix the time if necessary
	before = crc_fixed[:7 + 9 + 4]
	after = crc_fixed[7 + 9 + 4 + 4:]
	fixed_crc_header = before + struct.pack("<I", timedate_32bit) + after
	assert lenb == len(fixed_crc_header)

	header_crc = zlib.crc32(fixed_crc_header[2:]) & 0xFFFF
	fixed_crc_header = struct.pack("<H", header_crc) + fixed_crc_header[2:]
	assert lenb == len(fixed_crc_header)
	return fixed_crc_header

def fix_end_header(end_header, crc_all, file_number):
	if not end_header:
		return b""
	before = end_header[:7]
	after = end_header[7 + 4 + 2:]

	# change 12 to the next volume
	fixedh = (before + struct.pack("<I", crc_all) +
	          struct.pack("<H", file_number) + after)
	header_crc = zlib.crc32(fixedh[2:]) & 0xFFFF
	return struct.pack("<H", header_crc) + fixedh[2:]

# path = "D:/weg/Californication.S05E01.DVDSCR.XViD-DOCUMENT/"
# full = path + "Californication.S05E01.DVDSCR.XViD-DOCUMENT.avi"
# part = path + "californication.s05e01.dvdscr.xvid-document.bin"
# todo = path + "californication.s05e01.dvdscr.xvid-document.r00"
# filenb = 1 # r00
# amount = 19999876 # amount of data stored in one volume
# start = amount * filenb
# end = start + amount
#
# # Python 3.2's binascii.unhexlify() requires a byte string
# MARKER = b"526172211a0700"
# archive = b"b2ef7301010d00000000000000"
# fileh = (b"fac074c2905400842c310100a08f0e028044c4d5937c913f14302f0020000000"
#         b"43616c69666f726e69636174696f6e2e5330354530312e4456445343522e5856"
#         b"69442d444f43554d454e542e61766900b00abd02")
# arend = b"0aa67b0f401400351d04bb000000000000000000"

MARKER = binascii.unhexlify(MARKER)
archive = binascii.unhexlify(archive)
fileh = binascii.unhexlify(fileh)
arend = binascii.unhexlify(arend)

# print("Grabbing data from extracted file.")
# extract_part(full, part)


print("Calculating CRC file data.")
with open(part, "rb") as data:
	part_crc = calc_crc(data.read())

print("Fixing flags.")
archive = fix_archive_flags(archive)
fileh = fix_file_flags(fileh)

with open(part, "rb") as fh:
	pdata = fh.read()

# f192 to 3793
# 0x92F1 to 0x9337
# to find: fa92273f 0x3F2792FA

# fixing time
for time_index in range(0x3F2792F1, 0x3F279337):
	print("Fixing file header.")
	fileh = fix_file_header(fileh, part_crc, time_index)

	print("Calculating CRC complete RAR volume.")
	# everything except the last 20 bytes
	start = MARKER + archive + fileh

	crc_all = calc_crc(pdata, calc_crc(start))
# 	crc_all2 = calc_crc(start + pdata)
# 	assert crc_all == crc_all2

# 	print("Fixing archive end header.")
# 	arend = fix_end_header(arend, crc_all, filenb)
#
# 	if zlib.crc32(arend, crc_all) & 0xffffffff == 0xfa6f96b5:
# 		print("found it: %d" % i)
# 		break
	if crc_all & 0xffffffff == sfv_crc:
		print("found it: %d" % time_index)
		break

print("Creating %s." % todo)
with open(todo, "wb") as fh:
	fh.write(start)
	with open(part, "rb") as fpart:
		fh.write(fpart.read())
# 	fh.write(arend)

print("Done!")
