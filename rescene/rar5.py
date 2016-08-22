#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 pyReScene
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

import io
import os
import sys
import struct

from rescene.rar import ArchiveNotFoundError

S_BYTE = struct.Struct("<B")

class Rar5Block(object):
	"""Represents basic header used in all RAR archive blocks.
	
	composition?
	size/type read
	
	header_size
	extra_size
	data_size
	"""
	pass


def read_vint(stream):
	"""Reads a variable int from a stream. See RAR5 file format.
	
	The integer is stored little endian, but the first bit of every byte
	contains the continuation flag. It always reads the next lower 7 bits,
	but won't read the next byte when the current flag is 0.
	Similar to mp3 ID3 size int, but not stored big endian and
	the flag is not always 0."""
	size = 0
	shift = 0
	continuation_flag = True
	while continuation_flag:
		byte = S_BYTE.unpack(stream.read(1))[0]
		size += (byte & 0x7F) << (shift * 7)  # little endian
		shift += 1
		continuation_flag = byte & 0x80  # first bit 1: continue
	return size

def encode_vint(amount):
	"""Packs an integer to store it as RAR5 vint to a bytearray"""
	vint = bytearray()
	more = True
	while more:
		new_bits = amount & 0x7F
		amount = amount >> 7
		more = amount != 0
		vint.append(S_BYTE.pack(new_bits + (0x80 if more else 0)))
	return vint

###############################################################################

class Rar5Reader(object):
	"""A simple reader class that reads through RAR5 files."""
	RAR, SFX = list(range(2))
	
	def __init__(self, rfile, is_srr=False, file_length=0, enable_sfx=False):
		""" If the file is a part of a stream,
			the file_length must be given. """
		if isinstance(rfile, io.IOBase): 
			# the file is supplied as a stream
			self._rarstream = rfile
		else:  # file on hard drive
			try:
				self._rarstream = open(rfile, mode="rb")
			except (IOError, TypeError) as err:
				raise ArchiveNotFoundError(err)
		
		# get the length of the stream
		self._initial_offset = self._rarstream.tell()
		if not file_length:
			self._rarstream.seek(0, os.SEEK_END)
			self._file_length = self._rarstream.tell() - self._initial_offset
			self._rarstream.seek(self._initial_offset)
		else:
			self._file_length = file_length

		# TODO: find out minimum size
# 		if self._file_length < 22:
# 			raise ValueError("The file is too small. "
# 							 "The minimum ZIP size is 22 bytes.")
		
		self._rarstream.seek(self._initial_offset)
		self._current_index = 0
		self.is_srr = is_srr

	def __del__(self):
		try:  # close the file/stream
			self._rarstream.close()
		except:
			pass
	