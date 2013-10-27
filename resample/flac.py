#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013 pyReScene
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

# Docs for a quicker understanding:
# http://flac.sourceforge.net/format.html#format_overview

import os
import struct

from rescene.utility import is_rar
from rescene.rarstream import RarStream
from .mp3 import decode_id3_size

# All numbers are big-endian coded.
# All numbers are unsigned unless otherwise specified.
BE_BYTE = struct.Struct('>B') # unsigned char: 1 byte
BE_LONG = struct.Struct('>L') # unsigned long: 4 bytes
	
class InvalidDataException(ValueError):
	pass
	
class Block(object):
	def __init__(self, size, block_type):
		"""Block type is either an ASCII text string or an integer"""
		self.size = size
		self.type = block_type
		self.raw_header = b""
		self.start_pos = -1
		
	def is_last_block(self):
		"""Last block before the frame data."""
		# Never last block when self.type is a decoded string
		return not isinstance(self.type, str) and self.type & 0x80
	
	def is_frame_data(self):
		"""It isn't actually a block."""
		# Sync code '11111111 111110'
		return self.type == 0xFF
	
	def __repr__(self, *args, **kwargs):
		return "<Block type=%s size=%d start_pos=%d>" % (self.type, 
		                                self.size, self.start_pos)
		
class FlacReader(object):
	"""Implements a simple Reader class that reads through FLAC  
	or FLAC-SRS files one block at a time."""
	def __init__(self, path=None, stream=None):
		assert path or stream
		if path:
			if is_rar(path):
				self._flac_stream = RarStream(path)
			else:
				self._flac_stream = open(path, 'rb')
		elif stream:
			self._flac_stream = stream
		self._flac_stream.seek(0, 2)
		self._file_length = self._flac_stream.tell()
		self._flac_stream.seek(0)

		self.read_done = True
		self.current_block = None
		self.block_type = None

	def read(self):
		assert self.read_done
		
		block_start_position = self._flac_stream.tell()
		self.current_block = None
		self.read_done = False
		
		if block_start_position == self._file_length:
			return False
		
		self._block_header = self._flac_stream.read(4)
		# METADATA_BLOCK_HEADER
		# <1>    Last-metadata-block flag: '1' if this block is the last 
		#        metadata block before the audio blocks, '0' otherwise.
		# <7>    BLOCK_TYPE
		# <24>   Length (in bytes) of metadata to follow 
		#        (does not include the size of the METADATA_BLOCK_HEADER)
		
		if self._block_header == b"fLaC":
			self.block_type = "fLaC"
			self.current_block = Block(0, self.block_type)
			self.current_block.raw_header = b"fLaC"
			self.current_block.start_pos = block_start_position
			self._flac_stream.seek(block_start_position, os.SEEK_SET)
			return True
		
		# ID3v2
		if self._block_header.startswith(b"ID3"):
			self.block_type = "ID3"
			self._flac_stream.seek(block_start_position, os.SEEK_SET)
			raw_header = self._flac_stream.read(10)
			size = decode_id3_size(raw_header[6:10])
			self.current_block = Block(size, self.block_type)
			self.current_block.raw_header = raw_header
			self.current_block.start_pos = block_start_position
			self._flac_stream.seek(block_start_position, os.SEEK_SET)
			return True
		
		# ID3v1
		if self._block_header.startswith(b"TAG"):
			self.block_type = "TAG"
			self.current_block = Block(128, self.block_type)
			self.current_block.raw_header = b""
			self.current_block.start_pos = block_start_position
			self._flac_stream.seek(block_start_position, os.SEEK_SET)
			return True

		(self.block_type,) = BE_BYTE.unpack_from(self._block_header, 0)
		if self.block_type == 0xFF: # frame data
			block_length = self._file_length - block_start_position
			# check for ID3v1 tag
			self._flac_stream.seek(self._file_length - 128)
			if self._flac_stream.read(3) == b"TAG":
				block_length -= 128
			self._block_header = b""
		else:
			(block_length,) = BE_LONG.unpack(b"\x00" + self._block_header[1:])
		
		# sanity check on block length
		end_offset = block_start_position + block_length
		if (end_offset > self._file_length):
			raise InvalidDataException("Invalid block length at 0x%08X" % 
			                           block_start_position)
			
		self.current_block = Block(block_length, self.block_type)
		self.current_block.raw_header = self._block_header
		self.current_block.start_pos = block_start_position
		
		self._flac_stream.seek(block_start_position, os.SEEK_SET)

		return True
	
	def read_contents(self):
		# if read_done is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
			self._flac_stream.seek(self.current_block.start_pos, os.SEEK_SET)

		self.read_done = True

		# skip header bytes
		hl = len(self.current_block.raw_header)
		self._flac_stream.seek(hl, os.SEEK_CUR)
		buff = self._flac_stream.read(self.current_block.size)
		return buff
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			self._flac_stream.seek(self.current_block.start_pos + 
			                       len(self.current_block.raw_header) +
				                   self.current_block.size, os.SEEK_SET)

	def read_part(self, size, offset=0):
		"""idempotent operation"""
		hl = len(self.current_block.raw_header)
		initial_offset = self._flac_stream.tell()
		if initial_offset != self.current_block.start_pos:
			self._flac_stream.seek(self.current_block.start_pos, os.SEEK_SET)
		self._flac_stream.seek(offset + hl, os.SEEK_CUR)
		data = self._flac_stream.read(size)
		self._flac_stream.seek(initial_offset, os.SEEK_SET)
		return data
		
	def close(self):
		try: # close the file/stream
			self._flac_stream.close()
		except:
			pass	
		
	def __del__(self):
		try: # close the file/stream
			self._flac_stream.close()
		except:
			pass
			