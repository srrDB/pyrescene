#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 pyReScene
# zipfile.py
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

ZIP_EXT = (".zip", ".jar", ".odt", ".ods", ".odp",
           "docx", "xlsx", "pptx", ".apk", ".dwf")

# class ArchiveNotFoundError(IOError):
# 	pass
	
structFileHeader = "<4s2B4HL2L2H"
stringFileHeader = b"PK\003\004"
sizeFileHeader = struct.calcsize(structFileHeader)

_FH_SIGNATURE = 0
_FH_EXTRACT_VERSION = 1
_FH_EXTRACT_SYSTEM = 2
_FH_GENERAL_PURPOSE_FLAG_BITS = 3
_FH_COMPRESSION_METHOD = 4
_FH_LAST_MOD_TIME = 5
_FH_LAST_MOD_DATE = 6
_FH_CRC = 7
_FH_COMPRESSED_SIZE = 8
_FH_UNCOMPRESSED_SIZE = 9
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11

class ZipFileBlock():
	"""
	local file header signature	 4 bytes  (0x04034b50)
	version needed to extract    2 bytes
	general purpose bit flag     2 bytes
	compression method           2 bytes
	last mod file time           2 bytes
	last mod file date           2 bytes
	crc-32                       4 bytes
	compressed size              4 bytes
	uncompressed size            4 bytes
	file name length             2 bytes
	extra field length           2 bytes

	file name (variable size)
	extra field (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeFileHeader)
		self.header = struct.unpack(structFileHeader, self.hbytes)
		
		self.file_name = stream.read(self.header[_FH_FILENAME_LENGTH])
		self.hbytes += self.file_name
		if self.header[_FH_EXTRA_FIELD_LENGTH]:
			self.hbytes += stream.read(self.header[_FH_EXTRA_FIELD_LENGTH])
			
	def compressed_size(self):
		return self.header[_FH_COMPRESSED_SIZE]
	
	def has_compression(self):
		return self.header[_FH_COMPRESSION_METHOD] != 0
	
	def has_descriptor_block(self):
		return self.header[_FH_GENERAL_PURPOSE_FLAG_BITS] & 0x2000

class ZipDataDescriptorBlock():
	"""
	0x08074b50 has commonly been adopted as a signature value
	crc-32                          4 bytes
	compressed size                 4 bytes
	uncompressed size               4 bytes	

	ZIP64(tm) format
      archives, the compressed and uncompressed sizes are 8 bytes each.
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(12)
		if self.hbytes[0:4] == b"PK\x07\x08":
			self.hbytes += stream.read(4)
	
structExtraDataRecord = "<4sL"
stringExtraDataRecord = b"PK\x06\x08"
sizeExtraDataRecord = struct.calcsize(structExtraDataRecord)

_EDR_SIGNATURE = 0
_EDR_FIELD_LENGTH = 1

class ZipExtraDataRecordBlock():
	"""
	archive extra data signature    4 bytes  (0x08064b50)
	extra field length              4 bytes
	extra field data                (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeExtraDataRecord)
		self.header = struct.unpack(structExtraDataRecord, self.hbytes)

		self.hbytes += stream.read(self.header[_EDR_FIELD_LENGTH])			

structCentralDir = "<4s4B4HL2L5H2L"
stringCentralDir = b"PK\001\002"
sizeCentralDir = struct.calcsize(structCentralDir)

_CD_SIGNATURE = 0
_CD_CREATE_VERSION = 1
_CD_CREATE_SYSTEM = 2
_CD_EXTRACT_VERSION = 3
_CD_EXTRACT_SYSTEM = 4
_CD_FLAG_BITS = 5
_CD_COMPRESS_TYPE = 6
_CD_TIME = 7
_CD_DATE = 8
_CD_CRC = 9
_CD_COMPRESSED_SIZE = 10
_CD_UNCOMPRESSED_SIZE = 11
_CD_FILENAME_LENGTH = 12
_CD_EXTRA_FIELD_LENGTH = 13
_CD_COMMENT_LENGTH = 14
_CD_DISK_NUMBER_START = 15
_CD_INTERNAL_FILE_ATTRIBUTES = 16
_CD_EXTERNAL_FILE_ATTRIBUTES = 17
_CD_LOCAL_HEADER_OFFSET = 18

class ZipCentralDirBlock():
	"""
	central file header signature   4 bytes  (0x02014b50)
	version made by                 2 bytes
	version needed to extract       2 bytes
	general purpose bit flag        2 bytes
	compression method              2 bytes
	last mod file time              2 bytes
	last mod file date              2 bytes
	crc-32                          4 bytes
	compressed size                 4 bytes
	uncompressed size               4 bytes
	file name length                2 bytes
	extra field length              2 bytes
	file comment length             2 bytes
	disk number start               2 bytes
	internal file attributes        2 bytes
	external file attributes        4 bytes
	relative offset of local header 4 bytes

	file name (variable size)
	extra field (variable size)
	file comment (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeCentralDir)
		self.header = struct.unpack(structCentralDir, self.hbytes)
		
		self.file_name = stream.read(self.header[_CD_FILENAME_LENGTH])
		self.extra = stream.read(self.header[_CD_EXTRA_FIELD_LENGTH])
		self.comment = stream.read(self.header[_CD_COMMENT_LENGTH])
		self.hbytes += self.file_name + self.extra + self.comment

structDigitalSignature = "<4sH"
stringDigitalSignature = b"PK\x05\x05"
sizeDigitalSignature = struct.calcsize(structExtraDataRecord)

_DS_SIGNATURE = 0
_DS_SIZE = 1
		
class ZipDigitalSignatureBlock():
	"""
	header signature                4 bytes  (0x05054b50)
	size of data                    2 bytes
	signature data (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeDigitalSignature)
		self.header = struct.unpack(structDigitalSignature, self.hbytes)

		self.hbytes += stream.read(self.header[_DS_SIZE])
		
structEndArchive64 = "<4sQ2H2L4Q"
stringEndArchive64 = b"PK\x06\x06"
sizeEndArchive64 = struct.calcsize(structEndArchive64)

_CD64_SIGNATURE = 0
_CD64_DIRECTORY_RECSIZE = 1
_CD64_CREATE_VERSION = 2
_CD64_EXTRACT_VERSION = 3
_CD64_DISK_NUMBER = 4
_CD64_DISK_NUMBER_START = 5
_CD64_NUMBER_ENTRIES_THIS_DISK = 6
_CD64_NUMBER_ENTRIES_TOTAL = 7
_CD64_DIRECTORY_SIZE = 8
_CD64_OFFSET_START_CENTDIR = 9

class ZipEndArchive64Block():
	"""
	zip64 end of central dir 
	signature                       4 bytes  (0x06064b50)
	size of zip64 end of central
	directory record                8 bytes
	version made by                 2 bytes
	version needed to extract       2 bytes
	number of this disk             4 bytes
	number of the disk with the 
	start of the central directory  4 bytes
	total number of entries in the
	central directory on this disk  8 bytes
	total number of entries in the
	central directory               8 bytes
	size of the central directory   8 bytes
	offset of start of central
	directory with respect to
	the starting disk number        8 bytes
	zip64 extensible data sector    (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeEndArchive64)
		self.header = struct.unpack(structEndArchive64, self.hbytes)

		self.hbytes += stream.read(self.header[_CD64_DIRECTORY_RECSIZE] - 
		                           sizeEndArchive64 - 12)

structEndArchive64Locator = "<4sLQL"
stringEndArchive64Locator = b"PK\x06\x07"
sizeEndCentDir64Locator = struct.calcsize(structEndArchive64Locator)

class ZipEndArchive64Locator():
	"""
	zip64 end of central dir locator 
	signature                       4 bytes  (0x07064b50)
	number of the disk with the
	start of the zip64 end of 
	central directory               4 bytes
	relative offset of the zip64
	end of central directory record 8 bytes
	total number of disks           4 bytes
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeEndCentDir64Locator)
		self.header = struct.unpack(structEndArchive64Locator, self.hbytes)

structEndArchive = "<4s4H2LH"
stringEndArchive = b"PK\005\006"
sizeEndCentDir = struct.calcsize(structEndArchive)

_ECD_SIGNATURE = 0
_ECD_DISK_NUMBER = 1
_ECD_DISK_START = 2
_ECD_ENTRIES_THIS_DISK = 3
_ECD_ENTRIES_TOTAL = 4
_ECD_SIZE = 5
_ECD_OFFSET = 6
_ECD_COMMENT_SIZE = 7
# These last two indices are not part of the structure as defined in the
# spec, but they are used internally by this module as a convenience
_ECD_COMMENT = 8
_ECD_LOCATION = 9

class ZipEndArchiveBlock():
	"""
	end of central dir signature    4 bytes  (0x06054b50)
	number of this disk             2 bytes
	number of the disk with the
	start of the central directory  2 bytes
	total number of entries in the
	central directory on this disk  2 bytes
	total number of entries in
	the central directory           2 bytes
	size of the central directory   4 bytes
	offset of start of central
	directory with respect to
	the starting disk number        4 bytes
	.ZIP file comment length        2 bytes
	.ZIP file comment               (variable size)
	"""
	def __init__(self, stream):
		self.hbytes = stream.read(sizeEndCentDir)
		self.header = struct.unpack(structEndArchive, self.hbytes)
		
		self.comment = stream.read(self.header[_ECD_COMMENT_SIZE])
		self.hbytes += self.comment


###############################################################################

class ZipReader(object):
	"""A simple Reader class that reads through ZIP files."""
	ZIP, SFX = list(range(2))
	
	def __init__(self, zfile, is_srr=False, file_length=0, enable_sfx=False):
		""" If the file is a part of a stream,
			the file_length must be given. """
		if isinstance(zfile, io.IOBase): 
			# the file is supplied as a stream
			self._zipstream = zfile
		else:  # file on hard drive
			try:
				self._zipstream = open(zfile, mode="rb")
			except (IOError, TypeError) as err:
				raise ArchiveNotFoundError(err)
		
		# get the length of the stream
		self._initial_offset = self._zipstream.tell()
		if not file_length:
			self._zipstream.seek(0, os.SEEK_END)
			self._file_length = self._zipstream.tell() - self._initial_offset
			self._zipstream.seek(self._initial_offset)
		else:
			self._file_length = file_length

		# http://en.wikipedia.org/wiki/ZIP_(file_format) says:
		# "The minimum size of a .ZIP file is 22 bytes."
		if self._file_length < 22:
			raise ValueError("The file is too small. "
							 "The minimum ZIP size is 22 bytes.")
		
		# determine the read mode based on the marker
		marker = self._zipstream.read(2)
		if marker == b"PK":
			self._readmode = self.ZIP
		elif marker == b"MZ" and enable_sfx:
			self._readmode = self.SFX
		else:
			raise ValueError("SFX support not on or not a ZIP archive.")	
		self._zipstream.seek(self._initial_offset)
		self._current_index = 0
		self._data_descriptor = False
		self.is_srr = is_srr

	def __del__(self):
		try:  # close the file/stream
			self._zipstream.close()
		except:
			pass
		
	def _read(self):
		block_start_position = self._zipstream.tell()
		if block_start_position == self._initial_offset + self._file_length:
			return None  # The end.
		
		# 4.3.9  Data descriptor
		if self._data_descriptor:
			block = ZipDataDescriptorBlock(self._zipstream)
			self._data_descriptor = False
		
		marker = self._zipstream.read(4)
		self._zipstream.seek(block_start_position, os.SEEK_SET)
		
		# 4.3.7  Local file header
		if marker == b"PK\x03\x04":
			block = ZipFileBlock(self._zipstream)
			if not self.is_srr:
				self._zipstream.seek(block.compressed_size(), os.SEEK_CUR)
			if block.has_descriptor_block():
				self._data_descriptor = True
				if not self.is_srr:
					# TODO: get file size from central directory
					pass
				raise ValueError("ZIP with data descriptors "
								"currently not supported.")
			
		# 4.3.10  Archive decryption header
		# 4.3.11  Archive extra data record (0x08064b50)
		elif marker == b"PK\x06\x08":
			block = ZipExtraDataRecordBlock(self._zipstream)
			
		# 4.3.12  Central directory header (0x02014b50)
		elif marker == b"PK\x01\x02":
			block = ZipCentralDirBlock(self._zipstream)
			
		# 4.3.13  Digital signature (0x05054b50)
		elif marker == b"PK\x05\x05":
			block = ZipDigitalSignatureBlock(self._zipstream)
			
		# 4.3.14  Zip64 end of central directory record (0x06064b50)
		elif marker == b"PK\x06\x06":
			block = ZipEndArchive64Block(self._zipstream)
			
		# 4.3.15  Zip64 end of central directory locator (0x07064b50)
		elif marker == b"PK\x06\x07":
			block = ZipEndArchive64Locator(self._zipstream)
			
		# 4.3.16  End of central directory record (0x06054b50)
		elif marker == b"PK\x05\x06":
			block = ZipEndArchiveBlock(self._zipstream)
		
		else:
			raise EnvironmentError("ZIP corruption detected")
			
		return block
	
	def read_all(self):
		"""Parse the whole  file. The results are cached.
		Closes the open file. """
		# the list is not empty -> function has been called before: use cache
		try:
			return self._found_blocks 
		except AttributeError:
			self._zipstream.seek(self._initial_offset)
			self._found_blocks = []
			for block in self:
				print(block)
				self._found_blocks.append(block)
			self.__del__()
			return self._found_blocks

	def file_type(self):
		"""Returns whether this ZipReader reads a ZIP or SFX file."""
		return self._readmode
	
	def __next__(self):
		if self._zipstream.closed:
			try:
				self._current_index += 1
				return self._found_blocks[self._current_index - 1]
			except:
				self._current_index = 0
				raise StopIteration
		try:
			block = self._read()
		except EnvironmentError:  # corrupt file found
			self._zipstream.close()  # so it's possible to move the bad file
			raise
		if not block:
			self._zipstream.seek(self._initial_offset)
			raise StopIteration
		return block
	
	def next(self):  # @ReservedAssignment necessary for Python 2
		# http://www.python.org/dev/peps/pep-3114/
		return self.__next__()
	
	def __iter__(self):
		return self

	def close(self):
		self._zipstream.close()
