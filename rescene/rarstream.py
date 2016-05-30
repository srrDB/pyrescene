#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011-2012 pyReScene
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

# Development started after ReScene .NET 1.2
#   RarStream.cs
# Port based on the above file: MIT license

# The unit tests provide 100% code coverage for this file!

import io
import os
from rescene import rar, utility

def _check(first_rar):
	"""Check if first RAR file is given. 
	Raises ArchiveNotFoundError or
	       AttributeError (not the first rar archive is given).
	Returns True if all is OK.
	Returns False when we have an empty archive."""
	rar_reader = rar.RarReader(first_rar)
	blocks = rar_reader.read_all()
	rar_reader.close()
	for block in blocks:
		if block.rawtype == rar.BlockType.RarPackedFile:
			if block.flags & rar.RarPackedFileBlock.SPLIT_BEFORE:
				raise AttributeError(
					"You must start with the first volume from a RAR set")
			return True  # we have what we wanted
	return False

class RarStream(io.IOBase):
	"""Implements a read-only Stream that can read a packed file from
	a RAR archive set. Only store-mode (m0) RAR sets are supported.
	The compressed bytes will be returned for m1 - m5 compression."""

	def __init__(self, first_rar, packed_file_name=None,
	             middle=False, compressed=False):
		"""
		If middle is set, the check for being the first RAR volume is skipped.
		This can be the case when generating OSO/ISDb hashes.
		If compressed is set, no errors will be thrown for using
		compressed RAR files.
		"""
		self._rar_volumes = list()
		self._current_volume = None
		self._packed_file_length = 0
		self._current_position = 0
		self._closed = False

		# don't do the first RAR check if told not to
		# this is only when we know that the previous RARs are not needed
		if not middle and not _check(first_rar):
			raise AttributeError("Archive without stored files.")

		rar_file = first_rar
		while os.path.isfile(rar_file):
			is_old = self._process(rar_file, packed_file_name, compressed)
			rar_file = utility.next_archive(rar_file, is_old)

		try:
			# choose the first archive with the rar_file to start with
			self._current_volume = self._rar_volumes[0]
		except IndexError:
			# IndexError: list index out of range
			raise AttributeError("File not found in the archive.")

	def _process(self, rar_file, packed_file_name=None, compressed=False):
		"""Checks if the rar_file has the packed_file and adds 
		the _RarVolumes it creates to the list.
		If packed_file_name is not supplied, the first file will be used.
		Returns true if old style volume naming is used."""
		if packed_file_name:
			# / is an illegal character in Windows
			# We support POSIX paths, but the path structure in RAR files
			# is always Windows style.
			packed_file_name = packed_file_name.replace("/", "\\")
		is_old_style_naming = False
		reader = rar.RarReader(rar_file)
		for block in reader.read_all():
			if block.rawtype == rar.BlockType.RarVolumeHeader:
				# necessary for when the file name is ambiguous
				if not block.flags & block.NEW_NUMBERING:
					is_old_style_naming = True
			if block.rawtype == rar.BlockType.RarPackedFile:
				if (block.compression_method != rar.COMPR_STORING and
					not compressed):
					raise AttributeError("Compressed RARs are not supported")

				if not packed_file_name:
					packed_file_name = block.file_name
				if packed_file_name == block.file_name:
					cvol = self._RarVolume()
					cvol.archive_path = rar_file
					cvol.pfile_start = self._packed_file_length
					cvol.pfile_end = \
						self._packed_file_length + block.packed_size - 1
					cvol.pfile_offset = \
						block.block_position + block.header_size

					self._rar_volumes.append(cvol)
					self._packed_file_length += block.packed_size
		reader.close()
		self.packed_file_name = packed_file_name
		return is_old_style_naming

	def length(self):
		"""Length of the packed file being accessed."""
		return self._packed_file_length

	def tell(self):
		"""Return the current stream position."""
		return self._current_position

	def readable(self):
		"""Return True if the stream can be read from. 
		If False, read() will raise IOError."""
		return not self._closed
	def seekable(self):
		"""Return True if the stream supports random access. 
		If False, seek(), tell() and truncate() will raise IOError."""
		return not self._closed

	def close(self):
		"""Flush and close this stream. Disable all I/O operations. 
		This method has no effect if the file is already closed. 
		Once the file is closed, any operation on the file 
		(e.g. reading or writing) will raise a ValueError.

		As a convenience, it is allowed to call this method more than once; 
		only the first call, however, will have an effect."""
		for vol in self._rar_volumes:
			try:
				vol.file_stream.close()
			except:
				"The rar volume had no file stream yet."
		self._closed = True

	@property
	def closed(self):
		"""closed: bool.  True iff the file has been closed.

		For backwards compatibility, this is a property, not a predicate.
		"""
		return self._closed

	def seek(self, offset, origin=0):
		"""
		Change the stream position to the given byte offset. offset is 
		interpreted relative to the position indicated by origin. 
		Values for whence are:
	
			* SEEK_SET or 0 - start of the stream (the default); 
							  offset should be zero or positive
			* SEEK_CUR or 1 - current stream position; offset may be negative
			* SEEK_END or 2 - end of the stream; offset is usually negative
	
		Return the new absolute position.
		"""
		destination = 0
		if origin == os.SEEK_SET:  # 0
			destination = offset
		elif origin == os.SEEK_CUR:  # 1
			destination = self._current_position + offset
		elif origin == os.SEEK_END:  # 2
			destination = self._packed_file_length + offset

		if destination < 0:
			raise IndexError("Negative index.")
		self._current_position = destination

		# we do not have a RAR volume assigned yet
		# OR our current position is out of the range of the file
		if not self._current_volume  \
			or self._current_position < self._current_volume.pfile_start  \
			or self._current_position > self._current_volume.pfile_end:
			self._current_volume = None

			# find the RAR volume that has the current position of the file
			for vol in self._rar_volumes:
				if (self._current_position >= vol.pfile_start and
					self._current_position <= vol.pfile_end):
					self._current_volume = vol
					break  # found it: stop iterating

		# return the new absolute position
		return self._current_position

	def read(self, size=-1):
		"""
		read([size]) 
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Return an empty string at EOF.
		"""
		# Nothing to read anymore. We are through all archives in the list.
		if not self._current_volume:
			return b""

		file_bytes_read = 0
		dbuffer = b""
		size_set = True if size >= 0 else False

		while True:
			try:
				self._current_volume.file_stream
			except:  # no stream defined/opened yet
				self._current_volume.file_stream = \
							open(self._current_volume.archive_path, "rb")

			# point to begin of file inside archive
			self._current_volume.file_stream.seek(
				self._current_volume.pfile_offset +
				(self._current_position - self._current_volume.pfile_start), 0)

			# check how many bytes we still need to read
			file_bytes_read = self._current_volume.pfile_end  \
								 - self._current_position + 1
			if size_set:  # maybe reaching read size first
				file_bytes_read = min(size, file_bytes_read)
				size -= file_bytes_read

			dbuffer += self._current_volume.file_stream.read(file_bytes_read)

			# set global offset further
			self.seek(file_bytes_read, os.SEEK_CUR)

			# we are at the end of the file to read
			if file_bytes_read <= 0 or (size <= 0 and size_set)  \
				or self._current_position >= self._packed_file_length:
				break

		return dbuffer

	def readinto(self, byte_array):
		"""
		 |  readinto(...)
		 |	  readinto(bytearray) -> int.  Read up to len(b) bytes into b.
		 |	  
		 |	  Returns number of bytes read (0 for EOF), or None if the object
		 |	  is set not to block as has no data to read.
		 class io.RawIOBase
		 
		 readinto(b)
			Read up to len(b) bytes into bytearray b and return 
			the number of bytes read. If the object is in non-blocking mode 
			and no bytes are available, None is returned.
		"""
		raise NotImplementedError()

	def list_files(self):
		"""Returns a list of files stored in the RAR archive set."""
		return rar.RarReader(self._rar_volumes[0].archive_path).list_files()

	def __exit__(self, *args, **kwargs):
		# http://effbot.org/zone/python-with-statement.htm
		self.close()

	class _RarVolume(object):
		"""Represents a RAR archive/file.
		For internal use in RarStream. 
			
		archive_path
			The full path to the file name of the archive.
		pfile_offset
			The offset of the packed file in the archive.
		pfile_start
			Packed file range start.
		pfile_end
			Packed file range end.
		file_stream
			A file stream of the archive that has the packed file.
		"""

class SrrStream(io.IOBase):
	""" TODO: Direct file like access (read-only) + change name?
		to files stored in the SRR file.
		To support SRR files in a nfoviewer."""
	pass

class FakeFile(io.IOBase):
	"""Fake file that exists only of null bytes."""
	def __init__(self, file_size):
		self._file_size = file_size
		self._current_position = 0

	def length(self):
		"""Length of the fake file."""
		return self._file_size

	def tell(self):
		"""Return the current stream position."""
		return self._current_position

	def readable(self):
		"""Return True if the stream can be read from. 
		If False, read() will raise IOError."""
		return True

	def seekable(self):
		"""Return True if the stream supports random access. 
		If False, seek(), tell() and truncate() will raise IOError."""
		return True

	def seek(self, offset, origin=0):
		"""
		Change the stream position to the given byte offset. offset is 
		interpreted relative to the position indicated by origin. 
		Values for whence are:
	
			* SEEK_SET or 0 - start of the stream (the default); 
			                  offset should be zero or positive
			* SEEK_CUR or 1 - current stream position; offset may be negative
			* SEEK_END or 2 - end of the stream; offset is negative
	
		Return the new absolute position.
		"""
		destination = 0
		if origin == os.SEEK_SET:
			destination = offset
		elif origin == os.SEEK_CUR:
			destination = self._current_position + offset
		elif origin == os.SEEK_END:
			destination = self._file_size + offset

		if destination < 0:
			raise IndexError("Negative index.")
		if destination >= self._file_size:
			raise IndexError("Beyond end of file.")
		self._current_position = destination
		return self._current_position

	def read(self, size=-1):
		"""
		read([size])
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Returns an empty string at EOF.
		"""
		def gennull(size):
			return bytes(bytearray(size))

		if size < 0:
			old = self._current_position
			self._current_position = self._file_size
			return gennull(self._file_size - old)
		remainder = self._file_size - self._current_position
		if remainder == 0:
			return gennull(0)
		elif remainder >= size:
			self._current_position += size
			return gennull(size)
		else:
			self._current_position = self._file_size
			return gennull(remainder)
