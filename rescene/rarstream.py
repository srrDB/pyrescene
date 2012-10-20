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
import unittest
from rescene import rar, utility

def _check(first_rar):
	"""Check if first RAR file is given. 
	Raises ArchiveNotFoundError or
	       AttributeError (not the first rar archive is given).
	Returns True if all is OK.
	Returns False when we have an empty archive."""
	for block in rar.RarReader(first_rar):
		if block.rawtype == rar.BlockType.RarPackedFile:
			if block.flags & rar.RarPackedFileBlock.SPLIT_BEFORE:
				raise AttributeError(
					"You must start with the first volume from a RAR set")
			return True # we have what we wanted
	return False

class RarStream(io.IOBase):
	"""Implements a read-only Stream that can read a packed file from
	a RAR archive set. Only store-mode (m0) RAR sets are supported.
	The compressed bytes will be returned for m1 - m5 compression."""
	
	def __init__(self, first_rar, packed_file_name=None):
		self._rar_volumes = list()
		self._current_volume = None
		self._packed_file_length = 0
		self._current_position = 0
		self._closed = False

		if not _check(first_rar):
			raise AttributeError("Archive without stored files.")
		
		rar_file = first_rar
		while os.path.isfile(rar_file):
			self._process(rar_file, packed_file_name)
			rar_file = utility.next_archive(rar_file)

		try:
			# choose the first archive with the rar_file to start with
			self._current_volume = self._rar_volumes[0]
		except IndexError:
			# IndexError: list index out of range
			raise AttributeError("File not found in the archive.")
		
	def _process(self, rar_file, packed_file_name=None):
		"""Checks if the rar_file has the packed_file and adds 
		the _RarVolumes it creates to the list.
		If packed_file_name is not supplied, the first file will be used."""
		if packed_file_name:
			# / is an illegal character in Windows
			# We support POSIX paths, but the path structure in RAR files
			# is always Windows style.
			packed_file_name = packed_file_name.replace("/", "\\")
		reader = rar.RarReader(rar_file)
		for block in reader.read_all():
			if block.rawtype == rar.BlockType.RarPackedFile:
				if block.compression_method != rar.COMPR_STORING:
					raise AttributeError("Compressed RARs are not supported")
				
				if not packed_file_name:
					packed_file_name = block.file_name
				if packed_file_name == block.file_name:
					cvol = self._RarVolume()
					cvol.archive_path = rar_file
					cvol.pfile_start = self._packed_file_length
					cvol.pfile_end =  \
						self._packed_file_length + block.packed_size - 1
					cvol.pfile_offset =  \
						block.block_position + block.header_size
					
					self._rar_volumes.append(cvol)
					self._packed_file_length += block.packed_size

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
		if origin == os.SEEK_SET: # 0
			destination = offset
		elif origin == os.SEEK_CUR: # 1
			destination =  self._current_position + offset
		elif origin == os.SEEK_END: # 2
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
					break # found it: stop iterating
	
		# return the new absolute position
		return self._current_position
	
	def read(self, size=-1):
		"""
		read([size]) 
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Return an empty string at EOF.
			
		size > self._packed_file_length: EOFError
		"""
		if self._current_position + size > self._packed_file_length:
			raise EOFError("Trying to read beyond end of file.")
		
		# Nothing to read anymore. We are through all archives in the list.
		if not self._current_volume:
			return ""

		file_bytes_read = 0
		dbuffer = ""
		size_set = True if size >= 0 else False

		while True:
			try:
				self._current_volume.file_stream
			except: # no stream defined/opened yet
				self._current_volume.file_stream =  \
							open(self._current_volume.archive_path, "rb")
			
			# point to begin of file inside archive
			self._current_volume.file_stream.seek(
				self._current_volume.pfile_offset + 
				(self._current_position - self._current_volume.pfile_start), 0)	  
			
			# check how many bytes we still need to read
			file_bytes_read = self._current_volume.pfile_end  \
								 - self._current_position + 1
			if size_set: # maybe reaching read size first
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
			destination =  self._current_position + offset
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
			return bytes("\x00" * size)
		
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
		
###############################################################################

class TestRarStream(unittest.TestCase):
	"""For testing the RarStream class."""

	path = os.path.join(os.pardir, "test_files")
	folder = "store_split_folder_old_srrsfv_windows"
	
	def test_folder_multiple(self):	
		# with path and multiple files in folder / split volumes
		rs = RarStream(os.path.join(self.path, self.folder, 
		                            "store_split_folder.rar"), 
		                            "txt/users_manual4.00.txt")
		with open(os.path.join(self.path, "txt", "users_manual4.00.txt"),
				  "rb") as txt_file:
			# + other tests to increase code coverage
			self.assertEqual(rs.read(), txt_file.read())
			self.assertEqual(rs.tell(), txt_file.tell())
			self.assertEqual(rs.length(), txt_file.tell())
			self.assertEqual(rs.readable(), True)
			self.assertEqual(rs.seekable(), True)
			self.assertEqual(rs.read(), "")
			self.assertRaises(EOFError, rs.read, 999999)
			rs.seek(0, os.SEEK_SET)
			rs.read(2)
			rs.seek(0, os.SEEK_END)
			self.assertRaises(IndexError, rs.seek, -1)
		self.assertEquals(rs.list_files(), 
						  ["txt\\empty_file.txt", 
						   "txt\\little_file.txt", 
						   "txt\\users_manual4.00.txt"])
		self.assertRaises(NotImplementedError, rs.readinto, "")
		
	def test_file(self):
		""" Tests if the file in the rar archive is the same as the
			extracted version. """
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		txt_file = os.path.join(self.path, "txt", "little_file.txt")
		rs = RarStream(rar_file)
		with open(txt_file) as tfile:
			self.assertEqual(rs.read(), tfile.read())
			
		rar_file = os.path.join(self.path, 
				"store_split_folder_old_srrsfv_windows", "winrar2.80.rar")
		txt_file = os.path.join(self.path, "txt", "unicode_dos.nfo")
		rs = RarStream(rar_file, "unicode_dos.nfo") # 3.316 bytes
		with open(txt_file, "rb") as tfile:
			rs.seek(3316)
			self.assertEqual(rs.seek(6316), rs.tell())
			rs.seek(3312)
			tfile.seek(3336, os.SEEK_SET)
			tfile.seek(6336, os.SEEK_SET)
			rs.read(4)
			rs.seek(0)
			tfile.seek(0)
			self.assertEqual(rs.read(), tfile.read())
			tfile.seek(-20, os.SEEK_END)
			self.assertEqual(rs.seek(-20, os.SEEK_END), tfile.tell())
			self.assertEqual(rs.read(), tfile.read())
		rs.close()
		self.assertEqual(rs.closed, True, "Stream not closed")
	
		txt_file = os.path.join(self.path, "txt", "unicode_mac.nfo")
		rs = RarStream(rar_file, "unicode_mac.nfo")
		with open(txt_file) as tfile:
			tfile.seek(3000)
			tfile.read()
			tfile.seek(333)
			rs.seek(333)
			self.assertEqual(rs.read(), tfile.read())
			
	def test_read_nothing(self):
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		rs = RarStream(rar_file)
		self.assertEquals("", rs.read(0))
		
	def test_not_first_rar(self):
		# AttributeError: You must start with the first volume from a RAR set
		self.assertRaises(AttributeError, RarStream, os.path.join(self.path, 
						  "store_split_folder_old_srrsfv_windows",
						  "store_split_folder.r00"))
	
	def test_error_srr_file(self):
		# AttributeError: The extension must be one form a rar archive.
		self.assertRaises(AttributeError, RarStream, os.path.join(self.path, 
						  "store_split_folder_old_srrsfv_windows",
						  "store_split_folder.srr"))
		
	def test_error_unknown_file(self):
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		self.assertRaises(AttributeError, RarStream, rar_file, "file.txt")
	
	def test_error_archive_not_found(self):
		# ArchiveNotFoundError: [Errno 2] No such file or directory: '/'
		self.assertRaises(rar.ArchiveNotFoundError, RarStream, "/")
		#TODO: test in Linux
		
	def test_error_compressed_rar(self):
		# AttributeError: Compressed RARs are not supported
		self.assertRaises(AttributeError, RarStream, os.path.join(os.pardir, 
			"test_files", "best_little", "best_little.rar"))
		
	def test__check_function(self):
		# http://superuser.com/questions/325643/how-do-i-create-a-null-rar/
		small_rar = io.BytesIO()
		small_rar.write("Rar!\x1a\x07\x00")
		small_rar.write("\xF1\xFB\x73\x01\x00\x0D\x00\x00\x00\x00\x00\x00\x00")
		small_rar.seek(0)
		small_rar.name = "name"
		# AttributeError: Archive without stored files.
		self.assertRaises(AttributeError, RarStream, small_rar)

class TestFakeFile(unittest.TestCase):
	"""For testing the FakeFile class."""
	
	def test_error(self):
		ff = FakeFile(100)
		self.assertRaises(IndexError, ff.seek, 101)
		self.assertRaises(IndexError, ff.seek, -1, os.SEEK_SET)
		
	def test_fake_file(self):
		ff = FakeFile(100)
		self.assertEqual(ff.length(), 100)
		self.assertEqual(ff.tell(), 0, "Does not start at zero.")
		self.assertTrue(ff.readable(), "The file isn't readable.")
		self.assertTrue(ff.seekable(), "The file isn't seekable.")
		data = ff.read(50)
		self.assertEqual(ff.tell(), 50)
		self.assertEqual(data, "\x00" * 50)
		data = ff.read(51)
		self.assertEqual(ff.tell(), 100)
		self.assertEqual(data, "\x00" * 50)
		ff.seek(-5, os.SEEK_END)
		self.assertEqual(ff.tell(), 95)
		data = ff.read()
		self.assertEqual(len(data), 5)
		ff.seek(0)
		ff.seek(33, os.SEEK_CUR)
		self.assertEqual(len(ff.read()), 67)
		ff.read(0)
		
if __name__ == "__main__":
	os.chdir(os.path.dirname(__file__))
	unittest.main()