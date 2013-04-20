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

import os
import struct

from rescene.utility import is_rar
from rescene.rarstream import RarStream

S_LONG = struct.Struct('<L') # unsigned long: 4 bytes
BE_SHORT = struct.Struct('>H')
BE_LONG = struct.Struct('>L') # unsigned long: 4 bytes

class InvalidDataException(ValueError):
	pass
	
class Block(object):
	def __init__(self, size, block_type, start_pos):
		self.size = size
		self.type = block_type
		self.start_pos = start_pos
	
	def __repr__(self, *args, **kwargs):
		return "<Block type=%s size=%d start_pos=%d>" % (self.type, 
		                                self.size, self.start_pos)
		
class Mp3Reader(object):
	"""Implements a simple Reader class that reads through MP3 
	or MP3-SRS files one block at a time."""
	def __init__(self, path=None, stream=None):
		assert path or stream
		if path:
			if is_rar(path):
				self._mp3_stream = RarStream(path)
			else:
				self._mp3_stream = open(path, 'rb')
		elif stream:
			self._mp3_stream = stream
		self._mp3_stream.seek(0, 2)
		self._file_length = self._mp3_stream.tell()
		self._mp3_stream.seek(0)

		self.current_block = None
		
		self.blocks = []
		begin_main_content = 0
		
		# parse the whole file immediately!
		# 1) check for IDv2 (beginning of mp3 file)
		#The ID3v2 tag size is the size of the complete tag after
		#unsychronisation, including padding, excluding the header but not
		#excluding the extended header (total tag size - 10). Only 28 bits
		#(representing up to 256MB) are used in the size description to avoid
		#the introduction of 'false syncsignals'.
		first = self._mp3_stream.read(3)
		if first == "ID3":
			self._mp3_stream.seek(3, os.SEEK_CUR)
			sbytes = self._mp3_stream.read(4)
			# "This size is encoded using 28 bits rather than a multiple of 8, 
			# such as 32 bits, because an ID3 tag can't contain the byte #xff 
			# followed by a byte with the top 3 bits on because that pattern 
			# has a special meaning to MP3 decoders. None of the other fields
			# in the ID3 header could possibly contain such a byte sequence, 
			# but if you encoded the tag size as a regular unsigned-integer, 
			# it might. To avoid that possibility, the size is encoded using 
			# only the bottom seven bits of each byte, with the top bit always
			# zero."
			size = reduce(lambda x, y: x*128 + y, (ord(i) for i in sbytes))
			
			begin_main_content = size + 10
			idv2_block = Block(begin_main_content, "ID3", 0)
			self.blocks.append(idv2_block)
			
		# 2) check for IDv1 (last 128 bytes of mp3 file)
		self._mp3_stream.seek(-128, os.SEEK_END)
		idv1_start_offset = self._mp3_stream.tell()
		first = self._mp3_stream.read(3)
		idv1_block = None
		if first == "TAG":
			idv1_block = Block(128, "TAG", idv1_start_offset)
		
		# 3) in between is SRS or MP3 data
		self._mp3_stream.seek(begin_main_content, os.SEEK_SET)
		(sync,) = BE_SHORT.unpack(self._mp3_stream.read(2))
		if idv1_block:
			main_size = idv1_start_offset - begin_main_content
		else:
			main_size = idv1_start_offset + 128 - begin_main_content
		if sync & 0xFFE0 == 0xFFE0:
			mp3_data_block = Block(main_size, "MP3", begin_main_content)
			self.blocks.append(mp3_data_block)
		else: # SRS data blocks
			cur_pos = begin_main_content
			while(cur_pos < begin_main_content + main_size):
				self._mp3_stream.seek(cur_pos, os.SEEK_SET)
				# SRSF, SRST and SRSP
				try:
					marker = self._mp3_stream.read(4)
					# size includes the 8 bytes header
					(size,) = S_LONG.unpack(self._mp3_stream.read(4))
				except:
					raise InvalidDataException("Not enough SRS data")
				srs_block = Block(size, marker, cur_pos)
				self.blocks.append(srs_block)
				cur_pos += size
				if size == 0:
					raise InvalidDataException("SRS size field is zero")
				
		if idv1_block:
			self.blocks.append(idv1_block)
			
	def read(self):
		for block in self.blocks:
			self.current_block = block
			yield block
	
	def read_contents(self):
		self._mp3_stream.seek(self.current_block.start_pos, os.SEEK_SET)
		return self._mp3_stream.read(self.current_block.size)

	def read_part(self, size, offset=0):
		if (self.current_block.start_pos + offset + size >
			self.current_block.start_pos + self.current_block.size):
			raise ValueError("Can't read beyond end of block.")
		self._mp3_stream.seek(self.current_block.start_pos + offset, os.SEEK_SET)
		return self._mp3_stream.read(size)
		
	def close(self):
		try: # close the file/stream
			self._mp3_stream.close()
		except:
			pass	
		
	def __del__(self):
		try: # close the file/stream
			self._mp3_stream.close()
		except:
			pass
			