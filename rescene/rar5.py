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

from binascii import hexlify
from rescene.rar import ArchiveNotFoundError
from rescene.utility import _DEBUG, _OFFSETS

S_BYTE = struct.Struct("<B")
S_LONG = struct.Struct('<L')  # unsigned long: 4 bytes

# S_BYTE = struct.Struct('<B')  # 1 byte
# S_SHORT = struct.Struct('<H')  # 2 bytes
# S_LONGLONG = struct.Struct('<Q')  # unsigned long long: 8 bytes

BLOCK_MARKER = 0x0
BLOCK_MAIN = 0x1
BLOCK_FILE = 0x2
BLOCK_SERVICE = 0x3
BLOCK_ENCRYPTION = 0x4
BLOCK_END = 0x5

BLOCK_NAME = {
	BLOCK_MARKER: "RAR5 marker",
	BLOCK_MAIN: "Main archive header",
	BLOCK_FILE: "File header",
	BLOCK_SERVICE: "Service header",
	BLOCK_ENCRYPTION: "Encryption header",
	BLOCK_END: "End of archive header",
}

# flags common to all blocks
RAR_EXTRA = 0x0001  # Extra area is present after the header
RAR_DATA = 0x0002  # Data area is present after the header
RAR_SKIP = 0x0004  # Skip if unknown type when updating
RAR_SPLIT_BEFORE = 0x0008  # Data area is continuing from the previous volume
RAR_SPLIT_AFTER = 0x0010  # Data area is continuing in the next volume
RAR_DEPENDENT = 0x0020  # Block depends on preceding file block
RAR_PRESERVE_CHILD = 0x0040   # Preserve a child block if host block is modified

# file and service headers use the same types of extra area records
FILE_ENCRYPTION = 0x01  # File encryption information
FILE_HASH = 0x02  # File data hash
FILE_TIME = 0x03  # High precision file time
FILE_VERSION = 0x04	 # File version number
FILE_REDIRECTION = 0x05 # File system redirection
FILE_UNIX_OWNER = 0x06	# Unix owner and group information
FILE_SERVICE_DATA = 0x07 # Service header data array

class SizeTypeHeader(object):
	"""Common size and type field throughout all headers"""
	def __init__(self, stream):
		self.size = read_vint(stream)
		self.type = read_vint(stream)
	# TODO: remove?
		
class Rar5HeaderBase(object):
	"""'abstract' base class"""
	def __init__(self, file_position):
		"""file_position: stream location of the block"""
		self.block_position = file_position
		
	def data_offset(self):
		return self.block_position + self.full_header_size()
	
	def full_header_size(self):
		"""CRC32, header size field, header size"""
		return 4 + self._hdrvintsize + self.header_size

	def full_block_size(self):
		return self.full_header_size() + self.size_data

	def flag_format(self, flag):
		return "|   0x%04X " % flag
	
	def explain_size(self, size):
		return "0x%X (%u bytes)" % (size, size)

	def is_marker_block(self):
		return self.type == BLOCK_MARKER

	def is_main_block(self):
		return self.type == BLOCK_MAIN

	def is_file_block(self):
		return self.type == BLOCK_FILE

	def is_service_block(self):
		return self.type == BLOCK_SERVICE

	def is_encryption_block(self):
		return self.type == BLOCK_ENCRYPTION

	def is_end_block(self):
		return self.type == BLOCK_END

	def __repr__(self):
		return "%s %dB+%dB @ %d" % (
			BLOCK_NAME[self.type],
			self.full_header_size(),
			self.size_data,
			self.block_position)

class Rar5HeaderMarker(Rar5HeaderBase):
	def __init__(self, stream, file_position):
		"""
		stream: open stream to read the basic block header from
		file_position: location of marker block in the stream
		"""
		super(Rar5HeaderMarker, self).__init__(file_position)
		self.crc32 = 561144146
		self.type = 0  # marker
		self.header_size = 8
		self.flags = 0
		self.size_extra = 0
		self.size_data = 0
		self._headerdata = "\x52\x61\x72\x21\x1a\x07\x01\x00"

	def full_header_size(self):
		return 8

class Rar5HeaderBlock(Rar5HeaderBase):
	"""Represents basic header used in all RAR archive blocks,
	but not the marker.
	"""
	def __init__(self, stream, file_position):
		"""
		stream: open stream to read the basic block header from
		file_position: location of the block in the stream
		"""
		super(Rar5HeaderBlock, self).__init__(file_position)
		self.crc32 = S_LONG.unpack_from(stream.read(4))
		self.header_size = read_vint(stream)
		self._hdrvintsize = stream.tell() - 4 - file_position
		self.type = read_vint(stream)
		self.flags = read_vint(stream)
		self.size_extra = read_vint(stream) if self.flags & RAR_EXTRA else 0
		self.size_data = read_vint(stream) if self.flags & RAR_DATA else 0
		
		stream.seek(self.block_position)
		self._headerdata = stream.read(self.header_size)
		
	def explain(self):
		bname = BLOCK_NAME.get(self.type, "UNKNOWN BLOCK! NUKE IT!")
		out = "Block: %s" % bname
		if _OFFSETS:
			out += "; offset: %s\n" % (self.explain_size(self.block_position))
		else:
			out += "\n"
		hex_string = hexlify(self._headerdata).decode('ascii')
		out += "|Header bytes: %s\n" % hex_string
# 		if self.rawtype == BlockType.RarMin:
# 			out += "|Rar marker block is always 'Rar!1A0700' (magic number)\n"
		out += "|HEAD_CRC:   0x%04X\n" % self.crc32
		out += "|HEAD_SIZE:  %s\n" % self.explain_size(self.header_size)
		out += "|HEAD_TYPE:  0x%X (%s)\n" % (self.type, bname)
		out += self.explain_flags()
		return out
	
# 	def explain_flags(self, parent):
	def explain_flags(self):
		out = "|HEAD_FLAGS: 0x%04X\n" % self.flags
		flagresult = (self.SUPPORTED_FLAG_MASK & self.flags) ^ self.flags
# 		if flagresult != 0 and self.rawtype != BlockType.RarMin:
# 			out += "UNSUPPORTED FLAG DETECTED! %04X\n" % flagresult
# 		if self.flags & RarBlock.LONG_BLOCK:
# 			out += self.flag_format(RarBlock.LONG_BLOCK) +  \
# 				"LONG_BLOCK (ADD_SIZE field present)\n"
# 		if self.flags & RarBlock.SKIP_IF_UNKNOWN:
# 			out += self.flag_format(RarBlock.SKIP_IF_UNKNOWN) +  \
# 				"SKIP_IF_UNKNOWN (older RAR versions will ignore this block)\n"
		return out

class BlockFactory(object):
	def __init__(self, stream, is_srr_block=False):
		"""
		stream: open stream to read the basic block header from
		is_srr_block: RAR block is stripped
		"""
		# byte order: < little-endian
		# Marker block: Rar!\x1A\x07\x01\x00 (magic number)
		#               (0x52 0x61 0x72 0x21 0x1a 0x07 0x01 0x00)
		block_position = stream.tell()
		if stream.read(8) == b"Rar!\x1A\x07\x01\x00":
			self.header = Rar5HeaderMarker(stream, block_position)
		else:
			stream.seek(block_position, os.SEEK_SET)
			self.header = Rar5HeaderBlock(stream, block_position)
			
		self.is_srr = is_srr_block
		self._stream = stream

	def create(self):
		if self.header.is_marker_block():
			block = MarkerBlock(self.header, self.is_srr)
		elif self.header.is_main_block():
			block = RarBlock(self.header, self.is_srr)
		elif self.header.is_file_block():
			block = RarBlock(self.header, self.is_srr)
		elif self.header.is_service_block():
			block = RarBlock(self.header, self.is_srr)
		elif self.header.is_encryption_block():
			block = RarBlock(self.header, self.is_srr)
		elif self.header.is_end_block():
			block = RarBlock(self.header, self.is_srr)
		else:
			print("Unknown block detected!")
			block = RarBlock(self.header, self.is_srr)
			
		self._stream.seek(block.next_block_offset(), os.SEEK_SET)

		return block
			
class RarBlock(object):
	def __init__(self, rarheader, is_srr_block=False):
		self.basic_header = rarheader
		self.is_srr = is_srr_block
		
	def next_block_offset(self):
		location = self.basic_header.data_offset()
		if not self.is_srr:
			location += self.basic_header.size_data
		return location
		
	def is_markerblock(self):
		return self.basic_header.is_marker_block()

	def is_endblock(self):
		return self.basic_header.is_end_block()

	def __repr__(self, *args, **kwargs):
		return repr(self.basic_header)

class MarkerBlock(RarBlock):
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
	"""A simple reader class that reads through a RAR5 file or
	the RAR5 meta data stored in the RAR5 SRR block."""
# 	RAR, SRR, SFX = list(range(3))
	
	def __init__(self, rfile, is_srr=False, file_length=0, enable_sfx=False):
		""" If the file is a part of a stream,
			the file_length must be given. """
		if isinstance(rfile, io.IOBase):  # stream supplied
			self._rarstream = rfile
		else:  # file on hard drive or network disk
			try:
				self._rarstream = open(rfile, mode="rb")
			except (IOError, TypeError) as err:
				raise ArchiveNotFoundError(err)
		
		self._initial_offset = self._rarstream.tell()

		if file_length:
			self._file_length = file_length  # size in SRR RAR5 block
		else:
			# get the length of the stream
			self._rarstream.seek(0, os.SEEK_END)
			self._file_length = self._rarstream.tell() - self._initial_offset
			self._rarstream.seek(self._initial_offset, os.SEEK_SET)

		self._rarstream.seek(self._initial_offset)
		self._current_index = 0
		self._found_blocks = []
		self.is_srr = is_srr
		
	def _read(self):
		block_start_position = self._rarstream.tell()
		
		if block_start_position == self._initial_offset + self._file_length:
			return None  # The end.
		elif block_start_position >= self._initial_offset + self._file_length:
			assert False, "Invalid state"
	
		try:
			fac = BlockFactory(self._rarstream, self.is_srr)
			curblock = fac.create()
		except Exception as e:
			print(e)
			curblock = None
			raise
		
		self._rarstream.seek(curblock.next_block_offset(), os.SEEK_SET)

		return curblock
	
	def read_all(self):
		"""Parse the whole rar5 file. The results are cached.
		Closes the open file."""
		# the list is not empty -> function has been called before
		if not self._found_blocks:
			return self._found_blocks  # use cache
		else:
			self._rarstream.seek(self._initial_offset)
			for block in self:
#				print(block)
				self._found_blocks.append(block)
			self.__del__()
			return self._found_blocks
	
# 	def list_files(self):
# 		""" 
# 		RAR, SFX: returns a list of archived files.
# 		SRR:	  returns a list of stored files.
# 				  (not the archives that can be reconstructed)
# 		"""
# 		self.read_all()
# 		
# 		if self._readmode in (self.RAR, self.SFX):
# 			files = [b.file_name for b in self._found_blocks
# 			                     if isinstance(b, RarPackedFileBlock)]
# 		else:
# 			files = [b.file_name for b in self._found_blocks
# 			                     if isinstance(b, SrrStoredFileBlock)]
# 		return files

	def __del__(self):
		try:  # close the file/stream
			self._rarstream.close()
		except:
			pass
	
# 	def file_type(self):
# 		"""Returns whether this RarReader reads a RAR, SRR or SFX file."""
# 		return self._readmode
	
	def __next__(self):
		if self._rarstream.closed:
			try:
				self._current_index += 1
				return self._found_blocks[self._current_index - 1]
			except IndexError:
				self._current_index = 0
				raise StopIteration
		try:
			block = self._read()
			if not block:
				self._rarstream.seek(self._initial_offset)
				raise StopIteration
			self._found_blocks.append(block)
		except EnvironmentError:  # corrupt file found
			self._rarstream.close()  # so it's possible to move the bad file
			raise
		return block
	
	def next(self):  #@ReservedAssignment necessary for Python 2
		# http://www.python.org/dev/peps/pep-3114/
		return self.__next__()
	
	def __iter__(self):
		return self

	def close(self):
		self._rarstream.close()