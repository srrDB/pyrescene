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
until a match is found."""

import optparse
import sys
import time
import zlib

def main(options, args):
	file_name = args[0]
	crc32 = int(args[1], 16)
	if len(args) == 4:
		range_start = int(args[2], 10)
		range_end = int(args[3], 10)
	
	# http://www.catonmat.net/blog/low-level-bit-hacks-you-absolutely-must-know/
	# https://docs.python.org/2/library/mmap.html
	
	# read complete file into memory
	with open(file_name, 'rb') as volume:
		data = volume.read()
		
	start = 0
	end = len(data)
	print("File size: %d" % end)
	print("Expected CRC32: %0.X" % crc32)
	if len(args) != 4:
		range_start = start
		range_end = end
	if range_end > end:
		range_end = end
	print("From %d to %d" % (range_start, range_end))
	
	# naive way and flipping it all
	for cur_byte in range(range_start, range_end):
		if cur_byte % 10 == 0:
			print(cur_byte)
			
		# calculate crc32
		first_crc = zlib.crc32(data[start:cur_byte])
		# TODO: use lookup table instead of recalculation previous ranges
		
		# 8 bit flips for each byte
		cur_byte_data = ord(data[cur_byte])
		for i in range(8):
			flip = chr(cur_byte_data ^ (0x80 >> i))
			test_crc = zlib.crc32(flip + data[cur_byte+1:end], first_crc)
			
			if test_crc == crc32:
				print("Found in %d!" % cur_byte)
				print("Bit %d" % i)
				
				# write out good file
				outfn = file_name + ".bin"
				with open(outfn, 'wb') as result:
					result.write(data[start:cur_byte])
					result.write(flip)
					result.write(data[cur_byte+1:end])
				print("Fixed result written to %s" % outfn)
				break
		else:
			continue  # executed if the loop ended normally (no break)
		break  # executed if 'continue' was skipped (break)			
	else:
		print("No single bitflip found that matches the provided CRC32.")
		
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog file_name CRC32 [range start] [range end]\n"
		"This tool will flip each bit and stops when a CRC match is found.\n",
		version="%prog 0.1 (2014-10-07)") # --help, --version
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		start_time = time.time()
		(options, args) = parser.parse_args()
		main(options, args)
		print("--- %s seconds ---" % (time.time() - start_time))