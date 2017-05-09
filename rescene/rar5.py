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

from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
from binascii import hexlify
from rescene.rar import ArchiveNotFoundError
from rescene.utility import _DEBUG, _OFFSETS

import io
import os
import abc
import sys
import struct

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

LOCATOR_RECORD = 1

# flags common to all blocks
RAR_EXTRA = 0x0001  # Extra area is present after the header
RAR_DATA = 0x0002  # Data area is present after the header
RAR_SKIP = 0x0004  # Skip if unknown type when updating
RAR_SPLIT_BEFORE = 0x0008  # Data area is continuing from the previous volume
RAR_SPLIT_AFTER = 0x0010  # Data area is continuing in the next volume
RAR_DEPENDENT = 0x0020  # Block depends on preceding file block
RAR_PRESERVE_CHILD = 0x0040   # Preserve a child block if host block is modified

# archive header specific flags
ARCHIVE_VOLUME = 0x0001  # Volume. Archive is a part of multivolume set
ARCHIVE_NUMBER = 0x0002  # Volume number field is present
ARCHIVE_SOLID = 0x0004  # Solid archive
ARCHIVE_RECOVERY_RECORD = 0x0008  # Recovery record is present
ARCHIVE_LOCKED = 0x0010  # Locked archive

# file and service headers use the same types of extra area records
FILE_ENCRYPTION = 0x01  # File encryption information
FILE_HASH = 0x02  # File data hash
FILE_TIME = 0x03  # High precision file time
FILE_VERSION = 0x04	 # File version number
FILE_REDIRECTION = 0x05 # File system redirection
FILE_UNIX_OWNER = 0x06	# Unix owner and group information
FILE_SERVICE_DATA = 0x07 # Service header data array

END_NOT_LAST_VOLUME = 0x01  # volume and it is not last volume in the set

class SizeTypeHeader(object):
	"""Common size and type field throughout all headers"""
	def __init__(self, stream):
		self.size = read_vint(stream)
		self.type = read_vint(stream)
	# TODO: remove?
		
class Rar5HeaderBase(object):
	__metaclass__ = ABCMeta
	"""abstract base class for headers"""
	@abstractmethod
	def __init__(self, file_position):
		"""file_position: stream location of the block"""
		self.block_position = file_position
		
	def data_offset(self):
		return self.block_position + self.full_header_size()
	
	def full_header_size(self):
		"""CRC32, header size field, header size"""
		return 4 + self._hdrvint_width + self.header_size

	def full_block_size(self):
		return self.full_header_size() + self.size_data

	def flag_format(self, flag):
		return "|   0x%04X " % flag

	def explain(self):
		bname = BLOCK_NAME.get(self.type, "UNKNOWN BLOCK!")
		out = "Block: %s" % bname
		if _OFFSETS:
			out += "; offset: %s" % self.explain_size(self.block_position)
		return out
	
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
			BLOCK_NAME.get(self.type, "Unknown"),
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
		self.header_data = "\x52\x61\x72\x21\x1a\x07\x01\x00"

	def full_header_size(self):
		return 8
	
	def explain(self):
		out = super(Rar5HeaderMarker, self).explain() + "\n"
		hex_string = hexlify(self.header_data).decode('ascii')
		out += "|Header bytes: %s\n" % hex_string
		out += "|Rar5 marker block is always 'Rar!1A070100' (magic number)"
		return out

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
		self._hdrvint_width = stream.tell() - 4 - file_position
		self.type = read_vint(stream)
		self.flags = read_vint(stream)
		self.size_extra = read_vint(stream) if self.flags & RAR_EXTRA else 0
		self.size_data = read_vint(stream) if self.flags & RAR_DATA else 0
		self.offset_specific_fields = stream.tell() - file_position
		
		stream.seek(self.block_position)
		self.header_data = stream.read(self.header_size)
		self.stream = stream
		
	def explain(self):
		out = super(Rar5HeaderBlock, self).explain() + "\n"
		hex_string = hexlify(self.header_data).decode('ascii')
		out += "|Header bytes: %s\n" % hex_string
		out += "|Header CRC32: 0x%04X\n" % self.crc32
		out += "|Header size:  %s\n" % self.explain_size(self.header_size)
		out += "|Header type:  0x%X (%s)\n" % (
			self.type, BLOCK_NAME.get(self.type, "NUKE IT!"))
		out += self.explain_flags()
		return out
	
	def explain_flags(self):
		out = "|Header flags: 0x%04X\n" % self.flags
		if self.flags & RAR_EXTRA == RAR_EXTRA:
			out +="| 0x0001 Extra area present at header end\n"
		if self.flags & RAR_DATA == RAR_DATA:
			out +="| 0x0002 Data area present at header end\n"
		if self.flags & RAR_SKIP == RAR_SKIP:
			out +="| 0x0004 Skip when updating if unknown type\n"
		if self.flags & RAR_SPLIT_BEFORE == RAR_SPLIT_BEFORE:
			out +="| 0x0008 Data area will continue from the previous volume\n"
		if self.flags & RAR_SPLIT_AFTER == RAR_SPLIT_AFTER:
			out +="| 0x0010 Data area continues in the next volume\n"
		if self.flags & RAR_DEPENDENT == RAR_DEPENDENT:
			out +="| 0x0020  Block depends on preceding file block\n"
		if self.flags & RAR_PRESERVE_CHILD == RAR_PRESERVE_CHILD:
			out +="| 0x0040 Preserve a child block if host block is modified\n"
		return out

class BlockFactory(object):
	@staticmethod
	def create(stream, is_srr_block=False):
		"""
		stream: open stream to read the basic block header from
		is_srr_block: RAR block is stripped
		"""
		block_position = stream.tell()

		# byte order: < little-endian
		# Marker block: Rar!\x1A\x07\x01\x00 (magic number)
		#               (0x52 0x61 0x72 0x21 0x1a 0x07 0x01 0x00)
		if stream.read(8) == b"Rar!\x1A\x07\x01\x00":
			header = Rar5HeaderMarker(stream, block_position)
		else:
			stream.seek(block_position, os.SEEK_SET)
			header = Rar5HeaderBlock(stream, block_position)

		if header.is_marker_block():
			block = MarkerBlock(header, is_srr_block)
		elif header.is_main_block():
			block = MainArchiveBlock(header, is_srr_block)
		elif header.is_file_block():
			block = RarBlock(header, is_srr_block)
		elif header.is_service_block():
			block = RarBlock(header, is_srr_block)
		elif header.is_encryption_block():
			block = RarBlock(header, is_srr_block)
		elif header.is_end_block():
			block = EndArchiveBlock(header, is_srr_block)
		else:
			print("Unknown block detected!")
			block = RarBlock(header, is_srr_block)
			
		return block

class SfxModule(object):
	"""Not implemented"""
	pass
			
class RarBlock(object):
	def __init__(self, basic_header, is_srr_block=False):
		self.basic_header = basic_header
		self.is_srr = is_srr_block
		
	def next_block_offset(self):
		location = self.basic_header.data_offset()
		if not self.is_srr:
			location += self.basic_header.size_data
		return location
	
	def full_header_size(self):
		return self.basic_header.full_header_size()

	def full_block_size(self):
		return self.basic_header.full_block_size()

	def move_to_offset_specific_headers(self, stream):
		stream.seek(
		    self.basic_header.block_position +
		    self.basic_header.offset_specific_fields)
	
	def explain(self):
		return self.basic_header.explain()

	def explain_size(self, size):
		return self.basic_header.explain_size(size)
		
	def is_marker_block(self):
		return self.basic_header.is_marker_block()
	
	def is_main_block(self):
		return self.basic_header.is_main_block()

	def is_file_block(self):
		return self.basic_header.is_file_block()

	def is_service_block(self):
		return self.basic_header.is_service_block()

	def is_encryption_block(self):
		return self.basic_header.is_encryption_block()

	def is_endblock(self):
		return self.basic_header.is_end_block()

	def __repr__(self, *args, **kwargs):
		return repr(self.basic_header)

class MarkerBlock(RarBlock):
	pass

class MainArchiveBlock(RarBlock):
	def __init__(self, basic_header, is_srr_block=False):
		super(MainArchiveBlock, self).__init__(basic_header, is_srr_block)
		stream = self.basic_header.stream
		self.move_to_offset_specific_headers(stream)
		self.archive_flags = read_vint(stream)
		self.volume_number = 0  # first volume or none set
		self.quick_open_offset = 0
		self.recovery_record_offset = 0

		if self.archive_flags & ARCHIVE_NUMBER:
			self.volume_number = read_vint(stream)
		
		if self.basic_header.flags & RAR_EXTRA:
			# extra area can contain locator record: service block positions
			self.record_size = read_vint(stream)
			self.record_type = read_vint(stream)
			if self.record_type == 1:  # always true in initial RAR5 spec
				self.quick_open_offset = read_vint(stream)
				self.recovery_record_offset = read_vint(stream)
		
	def explain(self):
		out = self.basic_header.explain()
		out += "+Archive flags: 0x%04X\n" % self.archive_flags
		if self.archive_flags & ARCHIVE_VOLUME:
			out += "+  0x01 Part of multivolume set\n"
		if self.archive_flags & ARCHIVE_NUMBER:
			out += "+  0x02 Volume number field present\n"
		if self.archive_flags & ARCHIVE_SOLID:
			out += "+  0x04 Solid archive\n"
		if self.archive_flags & ARCHIVE_RECOVERY_RECORD:
			out += "+  0x08 Recovery record is present\n"
		if self.archive_flags & ARCHIVE_LOCKED:
			out += "+  0x10 Locked archive\n"
		if self.archive_flags & ARCHIVE_NUMBER:
			out += "+Volume number: %d\n" % self.volume_number
		if self.basic_header.flags & RAR_EXTRA:
			if self.record_type == LOCATOR_RECORD:
				# if one of the fields is not set, zero is shown
				out += "+Extra area with locator record\n"
				out += "+Quick open offset: %s\n" % self.explain_size(
					self.quick_open_offset)
				out += "+Recovery record offset: %s\n" % self.explain_size(
					self.recovery_record_offset)
			else:
				out += "!UNKNOWN extra archive record!\n"
		return out

class FileEncryptionBlock(RarBlock):
	pass

class FileServiceBlock(RarBlock):
	pass

class EndArchiveBlock(RarBlock):
	def __init__(self, basic_header, is_srr_block=False):
		super(EndArchiveBlock, self).__init__(basic_header, is_srr_block)
		stream = self.basic_header.stream
		self.move_to_offset_specific_headers(stream)
		self.end_of_archive_flags = read_vint(stream)

	def is_last_volume(self):
		return bool(self.end_of_archive_flags & END_NOT_LAST_VOLUME)

	def explain(self):
		out = self.basic_header.explain()
		out += "+End of archive flags: 0x%04X\n" % self.end_of_archive_flags 
		if self.is_last_volume():
			out += "+  0x01 Volume is not the last part of the set\n"
		return out
	
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
			curblock = BlockFactory.create(self._rarstream, self.is_srr)
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