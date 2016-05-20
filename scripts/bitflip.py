#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""Flip a single bit of a file and check the CRC of the file
until a match is found.

INSTALL
-------

Download zlib compiled DLL from http://zlib.net/ for more speed and 
put it in your PATH. See http://www.computerhope.com/issues/ch000549.htm
Use the pyReScene folder structure or 
copy rescene/crc32combine.py to the same folder as this file.

RUN
---

Run with -OO to disable the asserts. (prevents doing unnecessary checks)
python.exe -O bitflip.py file.mp3 0199AAFF 

Running time: 
less than 10k seconds on a battery powered Windows tablet for a 3.5MB file.
(< 1 hour/megabyte)

To test if it's working: 
make a text file and replace the letter a with the letter c. This byte will
have a single flipped bit in ASCII. Replace it with b to test flipped
adjacent bits.

Possible improvements:
- from multiprocessing import Pool; joblib
  https://docs.python.org/2/library/multiprocessing.html
  http://pythonhosted.org/joblib/parallel.html
  (it's far from using the whole CPU at the moment)
- algorithm optimization: (sub)optimal precalculation step?
- algorithm optimization: better hardcoded values? (needs experimentation)
=> skip parameter can be set differently
- write it all in a fast language?
=> most in zlib now anyway
- is PyPy a speed improvement? (it works with PyPy)
  How does the pure Python combine code compare with calling zlib from Python?
- better output file handling instead of (overwriting) the default .fixed

Author: Gfy"""

import optparse
import sys
import time
import zlib
from os.path import join, dirname, realpath
from struct import pack

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

try:
	from rescene import crc32combine
except ImportError:
	# for users that just copy the file to the same directory as this file
	import crc32combine

def precalculate(table, data, range_start, range_end, skip):
	# ((10k+1) * 2 + 1) large hashtable with tuples for 1MB
	crc32 = zlib.crc32
	for start in range(range_start, range_end + 1, skip):
		end = start + skip
		if end > range_end:
			end = range_end
		# before and after gab
		table[(range_start, start)] = (
		    crc32(data[range_start:start]) & 0xFFFFFFFF, start - range_start)
		table[(end, range_end)] = (
		    crc32(data[end:range_end]) & 0xFFFFFFFF, range_end - end)
	else:
		# the whole range
		table[(range_start, range_end)] = (
		    crc32(data[range_start:range_end]) & 0xFFFFFFFF, range_end - range_start)

def main(options, args):
	file_name = args[0]
	expected_crc32 = int(args[1], 16)  # of the full file
	if len(args) == 4:
		range_start = int(args[2], 10)
		range_end = int(args[3], 10)

	# read complete file into memory
	with open(file_name, 'rb') as volume:
		data = volume.read()

	start = 0
	end = len(data)
	print("File size: %d" % end)
	print("Expected CRC32: %0.X" % expected_crc32)
	if len(args) != 4:
		range_start = start
		range_end = end
	if range_end > end:
		range_end = end
	print("From %d to %d" % (range_start, range_end))
	if not (start <= range_start < range_end <= end):
		print("Invalid search range values provided for the specified file")
	crc32 = zlib.crc32  # dots slow Python down
	comb = crc32combine.crc32_combine_function()
	bitflip = not options.bytecheck and not options.bitswitch

	# memoization: precalculate crc32 hashes
	# 	crc32(crc32(0, seq1, len1), seq2, len2) ==
	# 		crc32_combine(crc32(0, seq1, len1), crc32(0, seq2, len2), len2)
	skip = options.skip  # 100 by default
	lookup = {}
	crc_begin = crc32(data[0:range_start]) & 0xFFFFFFFF
	crc_begin_len = len(data[0:range_start])
	crc_end = crc32(data[range_end:]) & 0xFFFFFFFF  # 0 on no data
	crc_end_len = len(data[range_end:])
	print("Lookup table precalculations ...")
	precalculate(lookup, data, range_start, range_end, skip)
	print("%d records." % len(lookup))

	if options.bytecheck:
		byte_values = [pack("B", i) for i in range(256)]

	def validate_table():
		# check correctness lookup table
		actual = crc32(data[range_start:range_end]) & 0xFFFFFFFF
		for s in range(range_start, range_end + skip, skip):
			if s > range_end:
				s = range_end
			(crc1, _len1) = lookup[(range_start, s)]
			(crc2, len2) = lookup[(s, range_end)]
			combined = comb(crc1, crc2, len2) & 0xFFFFFFFF
			assert actual == combined
			if s == range_end:
				break
		print("Lookup table ok: %d elements" % len(lookup))
		return True
	assert validate_table()

	# algorithm:
	# The CRCs before and after the part in progress within the working range
	# gets precalculated and get combined for testing. The different window
	# borders in the range to search have their hashes precalculated for
	# combination with the working part later on.
	# +----------+----------+----------+ (file to check)
	# +crc_begin-+          +---crc_end+
	# *-> start  |          |    end <-*
	#           /            \
	#      range_start   range_end       [offset from start file]
	#     / skip-sized partitions \
	#     *---|---|---|---|---|---*   => skip_count location index
	# +===========+   |                  crc_before_partition
	#             |   +================+ crc_after_partition + length
	#             *-> part_start         [offset from start file]
	#             |   *-> part_end
	#             / B \                  cur_byte where a bit is flipped
	#           *==+                     bpart_crc
	#                +==*                apart_crc + length
	# +============+                     ball_crc
	#                +=================+ aall_crc + length
	skip_count = part_start = part_end = 0
	crc_before_partition = crc_begin
	crc_after_partition = crc_end
	crc_after_len = crc_end_len
	for cur_byte in range(range_start, range_end):
		if skip_count % (skip) == 0:
			print(skip_count)
		if skip_count % skip == 0:  # a new partition starts
			# use new precalculated info on both sides of the search range
			part_start = range_start + skip_count
			(bpcrc, bplen) = lookup[(range_start, part_start)]
			crc_before_partition = comb(crc_begin, bpcrc, bplen) & 0xFFFFFFFF
			crc_before_len = crc_begin_len + bplen
			assert (crc_before_partition ==
				crc32(data[0:range_start + skip_count]) & 0xffffffff)

			part_end = part_start + skip
			if part_end > range_end:
				part_end = range_end
			(apcrc, aplen) = lookup[(part_end, range_end)]
			crc_after_partition = comb(apcrc, crc_end, crc_end_len) & 0xFFFFFFFF
			crc_after_len = aplen + crc_end_len
			assert (crc_after_partition == crc32(data[part_end:]) & 0xffffffff)
# 		print("CRC before partition %.X" % crc_before_partition)

		# calculate crc32: Before and After
		bpart_crc = crc32(data[part_start:cur_byte]) & 0xFFFFFFFF
		bpart_crc_len = cur_byte - part_start
		ball_crc = comb(crc_before_partition, bpart_crc, bpart_crc_len) & 0xFFFFFFFF
		assert crc_before_len + bpart_crc_len == len(data[0:cur_byte])
		assert (ball_crc == crc32(data[0:cur_byte]) & 0xffffffff)

		apart_crc = crc32(data[cur_byte + 1:part_end]) & 0xFFFFFFFF
		apart_len = part_end - cur_byte - 1
		assert apart_len == len(data[cur_byte + 1:part_end])
		aall_crc = comb(apart_crc, crc_after_partition, crc_after_len) & 0xFFFFFFFF
		aall_len = apart_len + crc_after_len
		assert (aall_crc == crc32(data[cur_byte + 1:]) & 0xffffffff)

		skip_count += 1
		cur_byte_data = ord(data[cur_byte:cur_byte + 1])

# 		crc_b = crc32(data[cur_byte:cur_byte+1], ball_crc) & 0xffffffff
# 		crc_all_orig = comb(crc_b, aall_crc, aall_len) & 0xffffffff
# 		assert crc_all_orig == crc32(data) & 0xffffffff

		if bitflip:
			# 8 bitflips for each byte
			for i in range(8):
				flip = pack("B", cur_byte_data ^ (0x80 >> i))
				assert data[cur_byte:cur_byte + 1] == pack("B", cur_byte_data)
				crcflip = crc32(flip, ball_crc) & 0xFFFFFFFF
				test_crc = comb(crcflip, aall_crc, aall_len) & 0xFFFFFFFF

				if test_crc == expected_crc32:
					print("Found in %d!" % cur_byte)
					print("Bit %d" % i)
					break
			else:
				continue  # executed if the loop ended normally (no break)
		elif options.bytecheck:
			# single byte change
			for i in range(256):
				crcflip = crc32(byte_values[i], ball_crc) & 0xFFFFFFFF
				test_crc = comb(crcflip, aall_crc, aall_len) & 0xFFFFFFFF

				if test_crc == expected_crc32:
					print("Found in %d!" % cur_byte)
					print("Value %d" % i)
					flip = byte_values[i]
					break
			else:
				continue  # executed if the loop ended normally (no break)
		elif options.bitswitch:
			# subset of what bytecheck does, but faster
			# only works within a byte
			# http://graphics.stanford.edu/~seander/bithacks.html#SwappingBitsXOR
			for i in range(7):
				# will also flip 11 to 00
				switch = pack("B", cur_byte_data ^ (0x3 << i))
				assert data[cur_byte:cur_byte + 1] == pack("B", cur_byte_data)
				crcswitch = crc32(switch, ball_crc) & 0xFFFFFFFF
				test_crc = comb(crcswitch, aall_crc, aall_len) & 0xFFFFFFFF

				if test_crc == expected_crc32:
					print("Found in %d!" % cur_byte)
					print("Bit %d" % i)
					flip = switch
					break
			else:
				continue  # executed if the loop ended normally (no break)

		# write out good file
		outfn = file_name + ".fixed"
		print("Writing fixed file to %s" % outfn)
		with open(outfn, 'wb') as result:
			result.write(data[start:cur_byte])
			result.write(flip)
			result.write(data[cur_byte + 1:end])
		break  # executed if 'continue' was skipped (break)
	else:
		print("No change found that matches the provided CRC32.")

def print_assertions_enabled():
	print("Assertions are enabled!")
	print("Run this script with the Python -O or -OO parameters"
		" to disable them for faster execution speed.")
	return True

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog file_name CRC32 [range start] [range end]\n"
		"This tool will flip each bit and stops when a CRC match is found.\n"
		"CRC32: expected hash of the full file\n"
		"range: location in the file to search for a flip\n",
		version="%prog 0.3 (2016-03-01)")  # --help, --version

	parser.add_option("-s", "--skip", help="amount of bytes for window that "
	                  "needs constant crc32 recalculation for evaluation",
					  action="store", dest="skip", type="int", default=1000)
	parser.add_option("--byte", help="check all possibilities for a byte",
					  action="store_true", dest="bytecheck", default=False)
	parser.add_option("--bitswitch", help="two adjacent bits are switched",
					  action="store_true", dest="bitswitch", default=False)

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		assert print_assertions_enabled()
		start_time = time.time()
		(options, args) = parser.parse_args()
		main(options, args)
		print("--- %.3f seconds ---" % (time.time() - start_time))
