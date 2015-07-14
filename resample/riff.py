#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2012-2015 pyReScene
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

# http://www.jmcgowan.com/avitech.html#AVISpec

import struct
import re
import os

from rescene.utility import is_rar, _DEBUG
from rescene.rarstream import RarStream

S_BYTE = struct.Struct('<B') # unsigned char: 1 byte
S_LONG = struct.Struct('<L') # unsigned long: 4 bytes

# https://msdn.microsoft.com/en-us/library/windows/desktop/dd318189(v=vs.85).aspx
# A FOURCC (four-character code) is a 32-bit unsigned integer created by 
# concatenating four ASCII characters. FOURCCs can contain space characters.
fourCCValidator = re.compile(b"^[ 0-9A-Za-z]{4}$")

class InvalidDataException(ValueError):
	pass

class InvalidMatchOffsetException(ValueError):
	pass

# RiffReader.cs ---------------------------------------------------------------
class RiffReadMode(object):
	"""The read mode for the RiffReader.
	
	AVI: .avi file
	Sample: same as AVI, but used for detecting corruption with samples
	SRS: used for the meta data files
	"""
	AVI, Sample, SRS = list(range(3))

class RiffChunkType(object):
	List, Movi, SrsFile, SrsTrack, Index, Unknown = list(range(6))

class RiffChunk(object):
	fourcc = b""
	length = 0
	raw_header = b""
	chunk_start_pos = 0
	
class MoviChunk(RiffChunk):
	stream_number = 0
	
class RiffList(RiffChunk):
	list_type = 0

class RiffReader(object):
	"""Implements a simple Reader class that reads through AVI 
	or AVI-SRS files one chunk at a time."""
	def __init__(self, read_mode, path=None, stream=None, match_offset=0,
			archived_file_name=""):
		if path:
			if is_rar(path):
				self._riff_stream = RarStream(path, archived_file_name)
			else:
				self._riff_stream = open(path, 'rb')
		elif stream:
			self._riff_stream = stream
		else:
			assert False
		self._riff_stream.seek(0, os.SEEK_END)
		self._file_length = self._riff_stream.tell()
		self.mode = read_mode
		
		self.read_done = True
		self.current_chunk = None
		self.chunk_type = None
		self.has_padding = False
		self.padding_byte = ""
		
		# faster reconstructing when match_offset is provided
		if match_offset >= 8 and match_offset < self._file_length:
			# -8 is there to add the chunk header for read()
			if self._is_valid_chunk_location(match_offset - 8):
				# yes! reconstruction will be fast
				self._riff_stream.seek(match_offset - 8, os.SEEK_SET)
			else:
				# match offset is not at the start boundary of a chunk
				chunk_offset = self._find_chunk_offset(match_offset)
				if _DEBUG:
					print("Match offset doesn't start on a nice boundary.")
					print("Chunk offset: {0}".format(chunk_offset))
					print("Match offset: {0}".format(match_offset))
				assert chunk_offset < match_offset
				self._riff_stream.seek(chunk_offset, os.SEEK_SET)
				
			# re-initialisation 
			self.read_done = True
			self.current_chunk = None
			self.chunk_type = None
			self.has_padding = False
			self.padding_byte = ""
		elif match_offset >= self._file_length:
			msg = "Invalid match offset for video: {0}".format(match_offset)
			raise InvalidMatchOffsetException(msg)
		else:
			# no useful matching offset against the main movie file
			self._riff_stream.seek(0)

	def _is_valid_chunk_location(self, offset):
		"""Checks whether a certain offset is a valid chunk location to
		start processing from. Based on Four Character Code."""
		self._riff_stream.seek(offset, os.SEEK_SET)
		fourcc = self._riff_stream.read(4)
		return fourCCValidator.match(fourcc)
		
	def _find_chunk_offset(self, match_offset):
		"""Finds the start offset of the chunk for the match_offset. It uses
		the index at the end of the file."""
		self._riff_stream.seek(0, os.SEEK_SET)
		index_data = ""
		movi_start = 0
		
		while self.read():
			fourcc = self.current_chunk.fourcc
			if fourcc == b"AVI ":
				# the index is in here
				self.move_to_child()
			elif fourcc == b"movi":
				# location where the index is relative to
				movi_start = self.current_chunk.chunk_start_pos
			elif self.chunk_type == RiffChunkType.Index:
				index_data = self.read_contents()
				break
			self.skip_contents()
		
		# https://msdn.microsoft.com/en-us/library/windows/desktop/dd318181(v=vs.85).aspx
		# we've found the index
		if movi_start and len(index_data):
			# read chunk positions until an _absolute_ file position larger
			# than our match offset is found
			offsets = []
			offset = 0
			idxpos = 0
			while offset < match_offset and idxpos + 16 <= len(index_data):
				(offset,) = S_LONG.unpack(index_data[idxpos+8:idxpos+12])
				offsets.append(offset)
				idxpos += 16 # ckid, dwFlags, dwChunkOffset, dwChunkLength
			
			# choose the last _relative_ chunk smaller than the match offset
			# the match offset is absolute form the beginning of the file
			for offset in reversed(offsets):
				start_offset = movi_start + 8 + offset
				if start_offset < match_offset:
					if self._is_valid_chunk_location(start_offset):
						return start_offset
					else:
						if _DEBUG:
							print("AVI doesn't follow the 'idx1' spec.")
						break 
			
			# assume the AVI doesn't follow the specification
			for offset in reversed(offsets):
				if offset < match_offset:
					if self._is_valid_chunk_location(offset):
						return offset
					else:
						if _DEBUG:
							print("The index offset wasn't usable.")
						return 0
		return 0
	
	def read(self):
		# "Read() is invalid at this time", "MoveToChild(), ReadContents(), or 
		# SkipContents() must be called before Read() can be called again");
		assert self.read_done or (self.mode == RiffReadMode.SRS and
		                          self.chunk_type == RiffChunkType.Movi)
		
		# includes 8 byte header
		chunk_start_position = self._riff_stream.tell()
		self.current_chunk = None
		self.read_done = False
		
		if chunk_start_position + 8 > self._file_length:
			return False
		
		chunk_header = self._riff_stream.read(8)
		# 4 bytes for fourcc, 4 for chunk length
		fourcc = chunk_header[:4]
		(chunk_length,) = S_LONG.unpack_from(chunk_header, 4)
		
		# might not keep this check
		# the length check should catch corruption on its own...
		if not fourCCValidator.match(fourcc):
			raise InvalidDataException("Invalid FourCC value (%r) at 0x%08X" % 
			                           (fourcc, chunk_start_position))
		
		# sanity check on chunk length
		# Skip check on RIFF list so we can still report expected size.
		# This is only applied on samples,
		# since a partial movie might still be useful.
		endOffset = chunk_start_position + 8 + chunk_length
		if (self.mode == RiffReadMode.Sample and
			fourcc != b"RIFF" and endOffset > self._file_length):
			raise InvalidDataException("Invalid chunk length at 0x%08X" % 
			                           (chunk_start_position + 4))
		
		# Lists
		if fourcc == b"RIFF" or fourcc == b"LIST":
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
			if chunk_header[:2].isdigit():
				self.current_chunk = MoviChunk()
				self.current_chunk.stream_number =  int(fourcc[:2])
				self.chunk_type = RiffChunkType.Movi
			elif fourcc == b"idx1":
				self.current_chunk = RiffChunk()
				self.chunk_type = RiffChunkType.Index
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
			self._riff_stream.seek(-self.current_chunk.length - 
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
	
	def close(self):
		try: # close the file/stream
			self._riff_stream.close()
		except:
			pass
		
	def __del__(self):
		try: # close the file/stream
			self._riff_stream.close()
		except:
			pass
