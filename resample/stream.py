#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2015 pyReScene
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

"""Bare SRS files for samples without specific file format container."""

import os
import struct

from rescene.utility import is_rar, _DEBUG
from rescene.rarstream import RarStream

S_LONG = struct.Struct('<L')  # unsigned long: 4 bytes
STREAM_MARKER = b"STRM"

class InvalidDataException(ValueError):
	pass
	
class Block(object):
	def __init__(self, size, block_type, start_pos):
		self.size = size
		self.type = block_type
		self.start_pos = start_pos
	
	def __repr__(self, *args, **kwargs):
		return "<Block type={0} size={1} start_pos={2}>".format(
			self.type, self.size, self.start_pos)
		
class StreamReader(object):
	"""Implements a simple Reader class that reads STREAM-SRS files."""
	def __init__(self, path=None, stream=None, archived_file_name=""):
		assert path or stream
		if path:
			if is_rar(path):
				self._stream = RarStream(path, archived_file_name)
			else:
				self._stream = open(path, 'rb')
		elif stream:
			self._stream = stream
		self._stream.seek(0, 2)
		self._file_length = self._stream.tell()
		self._stream.seek(0)

		self.current_block = None
		self.blocks = []
		
		pos = 0
		while pos < self._file_length:
			if pos + 8 > self._file_length:
				raise InvalidDataException("SRS file too small!")

			# header: block signature
			marker = self._stream.read(4)
			if pos == 0 and marker != STREAM_MARKER:
				raise InvalidDataException("Not a stream SRS file!")
			if marker not in (b"STRM", b"SRSF", b"SRST"):
				print("Unknown header block encountered")
			else:
				marker = marker.decode("ascii")

			# header: block size
			(size,) = S_LONG.unpack(self._stream.read(4))
			block = Block(size, marker, pos)
			self.blocks.append(block)
			if _DEBUG:
				print(block)

			if size == 0 and pos != 0:
				# only allowed for the marker block
				raise InvalidDataException("SRS size field is zero")

			pos += size
			if pos > self._file_length:
				raise InvalidDataException("SRS file too small!")
			
			self._stream.seek(pos)
		self._stream.seek(0)

	def read(self):
		for block in self.blocks:
			self.current_block = block
			yield block
	
	def read_contents(self):
		"""Skips the marker and size fields"""
		self._stream.seek(self.current_block.start_pos + 8, os.SEEK_SET)
		return self._stream.read(self.current_block.size - 8)

	def close(self):
		try:  # close the file/stream
			self._stream.close()
		except:
			pass	
		
	def __del__(self):
		try:  # close the file/stream
			self._stream.close()
		except:
			pass	