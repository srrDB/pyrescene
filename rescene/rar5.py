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
from contextlib import contextmanager

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
LOCATOR_QUICK = 0x0001
LOCATOR_RR = 0x0002
UNDOCUMENTED_RECORD = 126

# flags common to all blocks
RAR_EXTRA = 0x0001  # Extra area is present after the header
RAR_DATA = 0x0002  # Data area is present after the header
RAR_SKIP = 0x0004  # Skip if unknown type when updating
RAR_SPLIT_BEFORE = 0x0008  # Data area is continuing from the previous volume
RAR_SPLIT_AFTER = 0x0010  # Data area is continuing in the next volume
RAR_DEPENDENT = 0x0020  # Block depends on preceding file block
RAR_PRESERVE_CHILD = 0x0040   # Preserve a child block if host block is modified

# encryption header specific flags
ENCRYPTION_PASSWORD_CHECK = 0x0001

# archive header specific flags
ARCHIVE_VOLUME = 0x0001  # Volume. Archive is a part of multivolume set
ARCHIVE_NUMBER = 0x0002  # Volume number field is present
ARCHIVE_SOLID = 0x0004  # Solid archive
ARCHIVE_RECOVERY_RECORD = 0x0008  # Recovery record is present
ARCHIVE_LOCKED = 0x0010  # Locked archive

# file (and service header) flags
FILE_DIRECTORY = 0x0001  # Directory file system object (file header only)
FILE_UNIX_TIME = 0x0002  # Time field in Unix format is present
FILE_CRC32 = 0x0004  # CRC32 field is present
FILE_NOSIZE = 0x0008  # Unpacked size is unknown

# host OS
OS_WINDOWS = 0x0000
OS_UNIX = 0x0001

# file and service headers use the same types of extra area records
FILEX_ENCRYPTION = 0x01  # File encryption information
FILEX_HASH = 0x02  # File data hash
FILEX_TIME = 0x03  # High precision file time
FILEX_VERSION = 0x04	 # File version number
FILEX_REDIRECTION = 0x05 # File system redirection
FILEX_UNIX_OWNER = 0x06	# Unix owner and group information
FILEX_SERVICE_DATA = 0x07 # Service header data array

RECORD_PASSWORD_CHECK = 0x0001  # pwd check data is present
RECORD_USE_MAC = 0x0002  # use MAC instead of plain checksums

TIME_UNIX = 0x0001
TIME_MODIFICATION = 0x0002
TIME_CREATION = 0x0004
TIME_ACCESS = 0x0008

LINK_UNIX_SYMLINK = 0x0001
LINK_WINDOWS_SYMLINK = 0x0002
LINK_WINDOWS_JUNCTION = 0x0003
LINK_HARD_LINK = 0x0004
LINK_FILE_COPY = 0x0005
LINK_DIRECTORY = 0x0001

UNIX_USER = 0x0001
UNIX_GROUP = 0x0002
UNIX_USER_ID = 0x0004
UNIX_GROUP_ID = 0x0008

END_NOT_LAST_VOLUME = 0x0001  # volume and it is not last volume in the set

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
	
	def metadata(self):
		return self.header_data

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
		self.header_data = b"\x52\x61\x72\x21\x1a\x07\x01\x00"
		self.stream = io.BytesIO(b"\x52\x61\x72\x21\x1a\x07\x01\x00")

	def full_header_size(self):
		return 8
	
	def explain(self):
		out = super(Rar5HeaderMarker, self).explain() + "\n"
		hex_string = hexlify(self.header_data).decode('ascii')
		out += "|Header bytes: %s\n" % hex_string
		out += "|Rar5 marker block is always 'Rar!1A070100' (magic number)\n"
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
		(self.crc32,) = S_LONG.unpack_from(stream.read(4))
		self.header_size = read_vint(stream)
		self._hdrvint_width = stream.tell() - 4 - self.block_position
		self.type = read_vint(stream)
		self.flags = read_vint(stream)
		self.size_extra = read_vint(stream) if self.flags & RAR_EXTRA else 0
		self.size_data = read_vint(stream) if self.flags & RAR_DATA else 0
		self.offset_specific_fields = stream.tell() - file_position

		stream.seek(self.block_position, os.SEEK_SET)
		self.header_data = stream.read(self.full_header_size())

		# make memory copy of meta data and stop referring to file 
		self.mstream = io.BytesIO()
		self.mstream.write(self.header_data)
		self.mstream.seek(0, os.SEEK_SET)

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
	def create(stream, is_start_file, is_srr_block=False):
		"""
		stream: open stream to read the basic block header from
		The stream position is at the start of the next block.
		is_start_file: use only to try and read the marker (SFX)
		is_srr_block: RAR block is stripped
		"""
		block_position = stream.tell()

		# byte order: < little-endian
		# Marker block: Rar!\x1A\x07\x01\x00 (magic number)
		#               (0x52 0x61 0x72 0x21 0x1a 0x07 0x01 0x00)
		if is_start_file:
			data = stream.read(8)
			if data == b"Rar!\x1A\x07\x01\x00":
				header = Rar5HeaderMarker(stream, block_position)
			elif data[0:7] == b"Rar!\x1A\x07\x00":
				raise ValueError("Input stream is RAR4 format")
			else:
				raise ValueError("SFX files not supported")
		else:
			header = Rar5HeaderBlock(stream, block_position)
			if not is_srr_block:
				stream.seek(header.size_data, os.SEEK_CUR)

		if header.is_marker_block():
			block = MarkerBlock(header, is_srr_block)
		elif header.is_main_block():
			block = MainArchiveBlock(header, is_srr_block)
		elif header.is_file_block() or header.is_service_block():
			block = FileServiceBlock(header, is_srr_block)
		elif header.is_encryption_block():
			block = FileEncryptionBlock(header, is_srr_block)
		elif header.is_end_block():
			block = EndArchiveBlock(header, is_srr_block)
		else:
			print("Unknown block detected!")
			block = RarBlock(header, is_srr_block)

		assert stream.tell() == block_position + header.full_block_size()
			
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
		stream.seek(self.basic_header.offset_specific_fields, os.SEEK_SET)
	
	def metadata(self):
		return self.basic_header.srr_metadata()
	
	def explain(self):
		return self.basic_header.explain()

	def explain_size(self, size):
		return self.basic_header.explain_size(size)
	
	def ftime(self, unix_time_stamp):
		return str(unix_time_stamp)  # TODO: proper string for displaying
		
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
		stream = self.basic_header.mstream
		self.move_to_offset_specific_headers(stream)
		self.archive_flags = read_vint(stream)
		self.volume_number = 0  # first volume == none set
		# extra area fields
		self.quick_open_offset = 0
		self.recovery_record_offset = 0
		self.undocumented_value = 0

		if self.archive_flags & ARCHIVE_NUMBER:
			self.volume_number = read_vint(stream)
		
		extra_records = bool(self.basic_header.flags & RAR_EXTRA)
		def another_record():
			return stream.tell() < self.basic_header.full_header_size()

		while extra_records and another_record():
			# extra area can contain locator record: service block positions
			record_size = read_vint(stream)
			record_data_start = stream.tell()
			self.record_type = read_vint(stream)

			# only Locator record in initial RAR5 spec
			if self.record_type & LOCATOR_RECORD:
				flags = read_vint(stream)
				
				if flags & LOCATOR_QUICK:
					self.quick_open_offset = read_vint(stream)
				if flags & LOCATOR_RR:
					self.recovery_record_offset = read_vint(stream)
			elif self.record_type & UNDOCUMENTED_RECORD:
				self.undocumented_value = read_vint(stream)
			else:
				print("Unknown extra record in main archive header found")
				
			stream.seek(record_data_start + record_size, os.SEEK_SET)
		self.move_to_offset_specific_headers(stream)
		
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
			# if one of the fields is not set, zero is shown
			out += "+Extra area with locator record\n"
			out += "+Quick open offset: %s\n" % self.explain_size(
				self.quick_open_offset)
			out += "+Recovery record offset: %s\n" % self.explain_size(
				self.recovery_record_offset)
		if self.basic_header.flags & UNDOCUMENTED_RECORD:
			out += "+Extra area with Undocumented record\n"
			out += "+Undocumented value: %s\n" % self.explain_size(
				self.undocumented_value)
		return out

class FileEncryptionBlock(RarBlock):
	"""This header is present only in archives with encrypted headers.
	Every next header after this one is started from 16 byte AES-256
	initialization vector followed by encrypted header data. Size of
	encrypted header data block is aligned to 16 byte boundary."""
	def __init__(self, basic_header, is_srr_block=False):
		super(FileEncryptionBlock, self).__init__(basic_header, is_srr_block)
		stream = self.basic_header.mstream
		self.move_to_offset_specific_headers(stream)
		self.encryption_version = read_vint(stream)
		self.encryption_flags = read_vint(stream)
		has_pwd_check = bool(self.encryption_flags & ENCRYPTION_PASSWORD_CHECK)
		self.kdf_count = stream.read(1)
		self.salt = stream.read(16)
		self.check_value = b""
		if has_pwd_check:
			self.check_value = stream.read(12)

class FileServiceBlock(RarBlock):
	def __init__(self, basic_header, is_srr_block=False):
		super(FileServiceBlock, self).__init__(basic_header, is_srr_block)
		stream = self.basic_header.mstream
		self.move_to_offset_specific_headers(stream)
		self.file_flags = read_vint(stream)
		self.unpacked_size = read_vint(stream)
		self.attributes = read_vint(stream)
		self.mtime = 0
		if self.file_flags & FILE_UNIX_TIME:
			(self.mtime,) = S_LONG.unpack_from(stream.read(4))
		self.datacrc32 = 0
		if self.file_flags & FILE_CRC32:
			(self.datacrc32,) = S_LONG.unpack_from(stream.read(4))
		compression_info = read_vint(stream)
		self.algorithm = compression_info & 0x003f  # lower 6 bits
		self.solid = bool(compression_info & 0x0040)  # bit 7
		self.method = compression_info & 0x0380  # bit 8-10
		self.dict_size = compression_info & 0x3c00  # bit 11-14
		self.host_os = read_vint(stream)
		name_length = read_vint(stream)
		self.name = stream.read(name_length)

		# extra area
		self.records = []
		extra_records = self.file_flags & RAR_EXTRA
		self.extra_area_size = self.basic_header.data_offset() - stream.tell()
		def another_record():
			return stream.tell() < self.basic_header.data_offset()

		while extra_records and another_record():
			record = file_service_record_factory(stream)
			self.records.append(record)
			print(record)

		# data area
		if self.file_flags & RAR_DATA:
			pass

	def explain(self):
		out = self.basic_header.explain()
		out += "+File flags: 0x%04X\n" % self.file_flags 
		if self.file_flags & FILE_DIRECTORY:
			out += "+  0x0001 Directory file system object\n"
		if self.file_flags & FILE_DIRECTORY:
			out += "+  0x0002 Time field in Unix format is present\n"
		if self.file_flags & FILE_DIRECTORY:
			out += "+  0x0004 CRC32 field is present\n"
		if self.file_flags & FILE_DIRECTORY:
			out += "+  0x0008 Unpacked size is unknown\n"
		out += "+Unpacked size: %s\n" % self.explain_size(self.unpacked_size)
		out += "+Attributes: %d (operating system specific)\n" % self.attributes
		out += "+Modification time: %s\n" % self.ftime(self.mtime)
		out += "+Data CRC32: %08X\n" % self.datacrc32
		out += "+Compression algorithm (0-63): %d\n" % self.algorithm
		out += "+Solid: %s\n" % ("yes" if self.solid else "no")
		out += "+Compression method (0-5): %d\n" % self.method
		out += "+Minimum dictionary size: %d\n" % (128 * (2 ** self.dict_size))
		out += "+Host OS: "
		if self.host_os & OS_WINDOWS == 0:
			out += "Windows"
		elif self.host_os & OS_UNIX == 1:
			out += "Unix"
		# what with hidden range utf8?
		out += "\n+Name: %s" % self.name.decode('utf-8', 'replace')
		if self.name == b"CMT": 
			out += " -> Archive comment"
		elif self.name == b"QO": 
			out += " -> Archive quick open data"
		elif self.name == b"ACL": 
			out += " -> NTFS file permissions"
		elif self.name == b"STM": 
			out += " -> NTFS alternate data stream"
		elif self.name == b"RR": 
			out += " -> Recovery record"
		if self.records:
			out += "\n" + reduce(lambda x, y: x + y.explain(), self.records)
		else:
			out += "\n+no extra file/service records\n"

		return out

def file_service_record_factory(stream):
	"""stream: pointer at start record location
	stream pointer moves up after the record
	a single record object will be created and returned"""
	record = Record(stream)

	if record.type == FILEX_ENCRYPTION:
		# File encryption information
		record = FileEncryptionRecord(record, stream)
	elif record.type == FILEX_HASH:
		# File data hash
		record = FileHashRecord(record, stream)
	elif record.type == FILEX_TIME:
		# High precision file time
		record = FileTimeRecord(record, stream)
	elif record.type == FILEX_VERSION:
		# File version number
		record = FileVersionRecord(record, stream)
	elif record.type == FILEX_REDIRECTION:
		# File system redirection
		record = FileRedirectionRecord(record, stream)
	elif record.type == FILEX_UNIX_OWNER:
		# Unix owner and group information
		record = FileUnixOwnerRecord(record, stream)
	elif record.type == FILEX_SERVICE_DATA:
		# Service header data array
		record = FileServiceDataRecord(record, stream)
	else:
		print("Unknown extra record in main archive header found")
		
	return record
	
class Record(object):	
	"""Two common fields: size and type"""
	def __init__(self, stream):
		self.stream_offset = stream.tell()
		self.size = read_vint(stream)  # starts from Type field
		self.type_offset = stream.tell()
		self.type = read_vint(stream)
		self.data_offset = stream.tell()
		
	def move_pointer_after_record(self, stream):
		end_record = self.type_offset + self.size
		stream.seek(end_record, os.SEEK_SET)
		
	def explain(self):
		size = self.size + (self.type_offset - self.stream_offset)
		return "+<Record offset=%s, size=%s>".format(self.stream_offset, size)
	
	def set_record_properties(self, record):
		self.stream_offset = record.stream_offset
		self.size = record.size
		self.type_offset = record.type_offset
		self.type = record.type
		self.data_offset = record.data_offset

class FileEncryptionRecord(Record):  # 0x01
	def __init__(self, record, stream):
		self.set_record_properties(record)
		self.version = read_vint(stream)
		self.flags = read_vint(stream)
		self.password_check_data = bool(self.flags & RECORD_PASSWORD_CHECK)
		self.use_mac = bool(self.flags & RECORD_USE_MAC)
		self.kdf_count = stream.read(1)
		self.salt = stream.read(16)
		self.iv = stream.read(16)
		self.check_value = ""
		if self.password_check_data:
			self.check_value = stream.read(16)
		self.move_pointer_after_record(stream)

class FileHashRecord(Record):  # 0x02
	def __init__(self, record, stream):
		self.set_record_properties(record)
		self.hash = read_vint(stream)
		if self.hash == 0:
			amount = 32  # BLAKE2sp
		else:  # for future use within RAR5
			amount = self.size - (self.data_offset - self.type_offset)
		self.hash_data = stream.read(amount)
		self.move_pointer_after_record(stream)

class FileTimeRecord(Record):  # 0x03
	def __init__(self, record, stream):
		self.set_record_properties(record)
		self.flags = read_vint(stream)
		self.is_unix = bool(self.flags & TIME_UNIX)
		self.mtime = 0  # 0x2
		self.ctime = 0  # 0x4
		self.atime = 0  # 0x8

		def read_time():
			# fields size: uint32 or uint64	
			if self.flags & TIME_UNIX:
				unix_time = stream.read(4)
				return unix_time
			else:
				windows_time = stream.read(8)
				return windows_time

		if self.flags & TIME_MODIFICATION:
			self.mtime = read_time()
		if self.flags & TIME_CREATION:
			self.ctime = read_time()
		if self.flags & TIME_ACCESS:
			self.atime = read_time()
		
		self.move_pointer_after_record(stream)

class FileVersionRecord(Record):  # 0x04
	def __init__(self, record, stream):
		self.set_record_properties(record)
		self.flags = read_vint(stream)  # always 0
		self.version_number = read_vint(stream)
		self.move_pointer_after_record(stream)

class FileRedirectionRecord(Record):  # 0x05
	def __init__(self, record, stream):
		self.set_record_properties(record)
		"""	
		0x0001   Unix symlink
		0x0002   Windows symlink
		0x0003   Windows junction
		0x0004   Hard link
		0x0005   File copy
		"""	
		self.redirection_type = read_vint(stream)
		self.flags = read_vint(stream)
		name_length = read_vint(stream)
		self.name = stream.read(name_length)  # UTF-8
		self.move_pointer_after_record(stream)

class FileUnixOwnerRecord(Record):  # 0x06
	def __init__(self, record, stream):
		self.set_record_properties(record)
		self.flags = read_vint(stream)
		if self.flags & UNIX_USER:
			name_length = read_vint(stream)
			self.owner = stream.read(name_length)  # UTF-8
		if self.flags & UNIX_GROUP:
			name_length = read_vint(stream)
			self.group = stream.read(name_length)  # UTF-8
		if self.flags & UNIX_USER_ID:
			self.user_id = read_vint(stream)
		if self.flags & UNIX_GROUP_ID:
			self.group_id = read_vint(stream)
		self.move_pointer_after_record(stream)

class FileServiceDataRecord(Record):  # 0x07
	def __init__(self, record, stream):
		self.set_record_properties(record)
		size_vint_type = self.data_offset - self.type_offset
		self.data = stream.read(self.size - size_vint_type)
		# Concrete contents of service data depends on service header type.
		self.move_pointer_after_record(stream)
	
class EndArchiveBlock(RarBlock):
	def __init__(self, basic_header, is_srr_block=False):
		super(EndArchiveBlock, self).__init__(basic_header, is_srr_block)
		stream = self.basic_header.mstream
		self.move_to_offset_specific_headers(stream)
		self.end_of_archive_flags = read_vint(stream)

	def is_last_volume(self):
		return bool(self.end_of_archive_flags & END_NOT_LAST_VOLUME)

	def explain(self):
		out = self.basic_header.explain()
		out += "+End of archive flags: 0x%04X\n" % self.end_of_archive_flags 
		if self.is_last_volume():
			out += "+  0x0001 Volume is not the last part of the set\n"
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
		(byte,) = S_BYTE.unpack(stream.read(1))
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

@contextmanager
def parse_rar5(*args, **kwargs):
	reader = Rar5Reader(*args, **kwargs)
	try:
		yield reader
	finally:
		del reader

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
			self._file_length = file_length  # size in SRR for RAR5 block
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
			start_file = block_start_position == self._initial_offset
			curblock = BlockFactory.create(
				self._rarstream, start_file, self.is_srr)
		except Exception as e:
			print(e)
			curblock = None
			raise

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