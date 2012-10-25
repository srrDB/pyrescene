#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2012 pyReScene
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

import struct
import re
import os

from rescene.utility import is_rar
from rescene.rarstream import RarStream

S_BYTE = struct.Struct('<B') # unsigned char: 1 byte
S_LONG = struct.Struct('<L') # unsigned long: 4 bytes

class InvalidDataException(ValueError):
	pass

# RiffReader.cs ---------------------------------------------------------------
class RiffReadMode(object):
	AVI, Sample, SRS = list(range(3))

class RiffChunkType(object):
	List, Movi, SrsFile, SrsTrack, Unknown = list(range(5))

class RiffChunk(object):
	fourcc = ""
	length = 0
	raw_header = ""
	chunk_start_pos = 0
	
class MoviChunk(RiffChunk):
	stream_number = 0
	
class RiffList(RiffChunk):
	list_type = 0

fourCCValidator = re.compile("^[ 0-9A-Za-z]{4}$")

class RiffReader(object):
	"""Implements a simple Reader class that reads through AVI 
	or AVI-SRS files one chunk at a time."""
	def __init__(self, read_mode, path=None, stream=None):
		if path:
			if is_rar(path):
				self._riff_stream = RarStream(path)
			else:
				self._riff_stream = open(path, 'rb')
		elif stream:
			self._riff_stream = stream
		else:
			assert False
		self._riff_stream.seek(0, 2)
		self._file_length = self._riff_stream.tell()
		self._riff_stream.seek(0)
		self.mode = read_mode
		
		self.read_done = True
	
		self.current_chunk = None
		self.chunk_type = None
		self.has_padding = False
		self.padding_byte = ""		

	def read(self):
		# "Read() is invalid at this time", "MoveToChild(), ReadContents(), or 
		# SkipContents() must be called before Read() can be called again");
		assert self.read_done or (self.mode == RiffReadMode.SRS and
		                          self.chunk_type == RiffChunkType.Movi)
		
		
		chunk_start_position = self._riff_stream.tell()
		self.current_chunk = None
		self.read_done = False
		
		if chunk_start_position + 8 > self._file_length:
			return False
		
		chunk_header = self._riff_stream.read(8)
		# 4 bytes for fourcc, 4 for chunk length
		fourcc = chunk_header[:4]
		(chunk_length,) = S_LONG.unpack(chunk_header[4:])
		
		# might not keep this check
		# the length check should catch corruption on its own...
		if not fourCCValidator.match(str(fourcc)):
			raise InvalidDataException("Invalid FourCC value (%s) at 0x%08X" % 
			                           (fourcc, self.chunkStartPos))
		
		# sanity check on chunk length
		# Skip check on RIFF list so we can still report expected size.
		# This is only applied on samples,
		# since a partial movie might still be useful.
		endOffset = chunk_start_position + 8 + chunk_length
		if (self.mode == RiffReadMode.Sample and fourcc != "RIFF" and 
			endOffset > self._file_length):
			raise InvalidDataException("Invalid chunk length at 0x%08X" % 
			                           (chunk_start_position + 4))
		
		# Lists
		if fourcc == "RIFF" or fourcc == "LIST":
			# if the fourcc indicates a list type (RIFF or LIST), 
			# there is another fourcc code in the next 4 bytes
			listType = fourcc
			chunk_header += self._riff_stream.read(4)
			fourcc = chunk_header[8:12]
			chunk_length -= 4 # extra dwFourCC 
			
			self.chunk_type = RiffChunkType.List
			self.current_chunk = RiffList()
			self.current_chunk.list_type = listType # RIFF list specific
			self.current_chunk.fourcc = fourcc
			self.current_chunk.length = chunk_length
			self.current_chunk.raw_header = chunk_header
			self.current_chunk.chunk_start_pos = chunk_start_position
		else: # Chunks
			# Chunk containing video, audio or subtitle data
			if (chunk_header[0].isdigit() and 
				chunk_header[1].isdigit()):
				self.current_chunk = MoviChunk()
				self.current_chunk.stream_number =  int(fourcc[:2])
				self.chunk_type = RiffChunkType.Movi
			else:
				self.current_chunk = RiffChunk()
				self.chunk_type = RiffChunkType.Unknown
			self.current_chunk.fourcc = fourcc
			self.current_chunk.length = chunk_length
			self.current_chunk.raw_header = chunk_header
			self.current_chunk.chunk_start_pos = chunk_start_position
		self.has_padding = chunk_length % 2 == 1

		return True
	
	def read_contents(self):
		# if read_done is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
			self._riff_stream.seek(-self.current_element.length - 
			                       (1 if self.has_padding else 0), os.SEEK_CUR)

		self.read_done = True
		buff = None

		if (self.mode != RiffReadMode.SRS or 
			self.chunk_type != RiffChunkType.Movi):
			buff = self._riff_stream.read(self.current_chunk.length)
		
		if self.has_padding:
			(self.padding_byte,) = S_BYTE.unpack(self._riff_stream.read(1))
		
		return buff
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			if (self.mode != RiffReadMode.SRS 
				or self.chunk_type != RiffChunkType.Movi):
				self._riff_stream.seek(self.current_chunk.length, os.SEEK_CUR)

			if self.has_padding:
				(self.padding_byte,) = S_BYTE.unpack(self._riff_stream.read(1))
	
	def move_to_child(self):
		# "MoveToChild() should only be called on a RIFF List");
		assert self.chunk_type == RiffChunkType.List
		self.read_done = True
	
	def __del__(self):
		try: # close the file/stream
			self._riff_stream.close()
		except:
			pass
