#!/usr/bin/env python
# -*- coding: latin-1 -*-

# osohash.py (MIT license)

# Copyright (c) 2011-2012 pyReScene
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import struct
import unittest
import io
from os.path import join
from rarstream import RarStream

def compute_hash(mfile):
	"""Hash code is based on Media Player Classic. (Gabest)
	
	In natural language it calculates:
		size + 64bit checksum of the first and last 64 KiB
	(even if they overlap because the file is smaller than 128 KiB).
	If a RAR file is supplied, it will calculate the srr_hash of that file.
	
	http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
	"""
	if hasattr(mfile, "seek"): # supplied as a stream/open file handle
		return _osorg_hash(mfile)
	else: # file on hard drive
		stream = open(mfile, mode="rb")
		try:
			return _osorg_hash(stream)
		finally:
			stream.close()
			
def osohash_from(rar_archive, enclosed_file=None):
	"""If enclosed_file is not supplied, the srr_hash will be calculated based
	on the first file in the archive(s). To get a list of the files inside the
	archive, use RarReader.list_files()."""
	return _osorg_hash(RarStream(rar_archive, enclosed_file))
	#TODO: return dict with srr_hash for each file in the archive
	# or list with tuples (path, filename, srr_hash)
	
def _length(stream):
	""" Returns the size of the given file stream. """
	original_offset = stream.tell()
	stream.seek(0, 2) # go to the end of the stream
	size = stream.tell()
	stream.seek(original_offset)
	return size
	
def _osorg_hash(stream):
	"""Expects an open file object. 
	
	How it must be calculated when the file is < 64 KiB is undefined:
	the C and Java implementation behave different.
	Assuming this is the original implementation:
	http://guliverkli.svn.sourceforge.net/viewvc/guliverkli/trunk/guliverkli/
		src/apps/mplayerc/ISDb.cpp?revision=523&view=markup
	http://msdn.microsoft.com/en-us/library/ctka0kks(v=vs.80).aspx
		The number of bytes transferred to the buffer. Note that for all 
		CFile classes, the return value may be less than nCount 
		if the end of file was reached.
	
	On opensubtitles.org is movie file size limited to 
		9000000000 > $moviebytesize > 131072 bytes, (1024*64*2)
	if is there any reason to change these sizes, let us know. """
	HASH_CHUNK_SIZE = 64 * 1024
	srr_hash = filesize = _length(stream)
	
	# TODO: make it work for smaller sizes too
	if filesize < HASH_CHUNK_SIZE:
		raise ValueError("The file is smaller than 64 KiB.")

	buffer_begin = stream.read(HASH_CHUNK_SIZE)
	stream.seek(-HASH_CHUNK_SIZE, 2)
	buffer_end = stream.read(HASH_CHUNK_SIZE)
	bytesize = struct.calcsize("Q") # unsigned long long
	for index in range(0, HASH_CHUNK_SIZE, bytesize):
		srr_hash += struct.unpack_from("<Q", buffer_begin, index)[0]
		srr_hash = srr_hash & 0xFFFFFFFFFFFFFFFF # to remain as 64bit number
		srr_hash += struct.unpack_from("<Q", buffer_end, index)[0]
		srr_hash = srr_hash & 0xFFFFFFFFFFFFFFFF

	return ("%016x" % srr_hash, filesize)

class TestHash(unittest.TestCase):
	"""
	Test these 2 files please to ensure your algorithm is completely OK: 
		AVI file (12 909 756 bytes) 
			srr_hash: 8e245d9679d31e12 
		DUMMY RAR file (2 565 922 bytes, 4 295 033 890 after RAR unpacking) 
			srr_hash: 61f7751fc2a72bfb
	"""
	def test_files(self):
		breakdance = join("..", "test_files", "media", "breakdance.avi")
		(osohash, file_size) = compute_hash(breakdance)
		self.assertEqual("8e245d9679d31e12", osohash)
		self.assertEqual(12909756, file_size)
		#self.assertEqual("61f7751fc2a72bfb", compute_hash("D:\dummy.bin")[0])

	def test_exceptions(self):
		self.assertRaises(TypeError, compute_hash, None)
		self.assertRaises(IOError, compute_hash, "")
		stream = io.BytesIO()
		stream.close()
		self.assertRaises(ValueError, compute_hash, stream)
		
	def test_rars(self):
		rar_file = join("..", "test_files", 
						"store_split_folder_old_srrsfv_windows", 
						"winrar2.80.rar")
		self.assertRaises(ValueError, osohash_from, rar_file)

if __name__ == '__main__':
	unittest.main()
