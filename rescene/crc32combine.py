#!/usr/bin/env python
# -*- coding: utf-8 -*-

#   zlib.h -- interface of the 'zlib' general purpose compression library
#   version 1.2.3, July 18th, 2005
# 
#   Copyright (C) 1995-2005 Jean-loup Gailly and Mark Adler
# 
#   This software is provided 'as-is', without any express or implied
#   warranty.  In no event will the authors be held liable for any damages
#   arising from the use of this software.
# 
#   Permission is granted to anyone to use this software for any purpose,
#   including commercial applications, and to alter it and redistribute it
#   freely, subject to the following restrictions:
# 
#   1. The origin of this software must not be misrepresented; you must not
#      claim that you wrote the original software. If you use this software
#      in a product, an acknowledgment in the product documentation would be
#      appreciated but is not required.
#   2. Altered source versions must be plainly marked as such, and must not be
#      misrepresented as being the original software.
#   3. This notice may not be removed or altered from any source distribution.
# 
#   Jean-loup Gailly        Mark Adler
#   jloup@gzip.org          madler@alumni.caltech.edu

# Port of crc32_combine() from zlib crc32.c to Python by Gfy

import os
import ctypes
from ctypes import util

def crc32_combine_function():
	"""Returns function to zlib when possible.
	Fallback to Python implementation."""
	if os.name == 'nt':
		libpath = util.find_library('zlib1')
	else:
		libpath = util.find_library('z')

	if libpath:
		zlib = ctypes.cdll.LoadLibrary(libpath)
		return zlib.crc32_combine
	else:
		print("zlib not found in PATH: slow Python implementation used")
		return crc32_combine

def crc32_combine_ctypes(crc1, crc2, len2):
	"""Loads the C library and calls the function."""
	if os.name == 'nt':
		libpath = util.find_library('zlib1')
	else:
		libpath = util.find_library('z')

	if libpath:
		zlib = ctypes.cdll.LoadLibrary(libpath)
		return zlib.crc32_combine(crc1, crc2, len2)
	else:
		raise RuntimeError("zlib not found")

def crc32_combine(crc1, crc2, len2):
	"""Explanation algorithm: http://stackoverflow.com/a/23126768/654160
	crc32(crc32(0, seq1, len1), seq2, len2) == crc32_combine(
        crc32(0, seq1, len1), crc32(0, seq2, len2), len2)"""
	# degenerate case (also disallow negative lengths)
	if len2 <= 0:
		return crc1
	
	# put operator for one zero bit in odd
	# CRC-32 polynomial, 1, 2, 4, 8, ..., 1073741824
	odd = [0xedb88320] + [1 << i for i in range(0, 31)]
	even = [0] * 32
	
	def matrix_times(matrix, vector):
		number_sum = 0
		matrix_index = 0
		while vector != 0:
			if vector & 1:
				number_sum ^= matrix[matrix_index]
			vector = vector >> 1 & 0x7FFFFFFF
			matrix_index += 1
		return number_sum

	# put operator for two zero bits in even - gf2_matrix_square(even, odd)
	even[:] = [matrix_times(odd, odd[n]) for n in range(0, 32)]

	# put operator for four zero bits in odd
	odd[:] = [matrix_times(even, even[n]) for n in range(0, 32)]
	
	# apply len2 zeros to crc1 (first square will put the operator for one
	# zero byte, eight zero bits, in even)
	while len2 != 0:
		# apply zeros operator for this bit of len2
		even[:] = [matrix_times(odd, odd[n]) for n in range(0, 32)]
		if len2 & 1:
			crc1 = matrix_times(even, crc1)
		len2 >>= 1

		# if no more bits set, then done
		if len2 == 0:
			break

		# another iteration of the loop with odd and even swapped
		odd[:] = [matrix_times(even, even[n]) for n in range(0, 32)]
		if len2 & 1:
			crc1 = matrix_times(odd, crc1)
		len2 >>= 1

		# if no more bits set, then done
	# return combined crc
	crc1 ^= crc2
	return crc1