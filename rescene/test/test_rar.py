#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2013 pyReScene
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

# Enable Unicode string literals by default because non-ASCII strings are
# used and Python 3.2 does not support the u"" syntax. Also, Python 2.6's
# bytearray.fromhex() only accepts Unicode strings. However the "struct"
# module does not support Unicode format strings until Python 3, so they have
# to be wrapped in str() calls.
from __future__ import unicode_literals

import unittest
from rescene.rar import *

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))	

class TestRarReader(unittest.TestCase):
	""" For testing RarReader.
		RarReader parses the incoming file or stream. """

	def test_read_none(self):
		""" We expect None back if we read one time to much. """
		stream = io.BytesIO()
		stream.name = "name to imitate real file"
		stream.write(RAR_MARKER_BLOCK)
		stream.write(TestRarBlocks.FIRST_VOLUME)
		stream.seek(0)
		
		rr = RarReader(stream)
#		self.assertEqual(stream.__sizeof__(), 32)
		self.assertEqual(rr._file_length, len(RAR_MARKER_BLOCK) +
						 len(TestRarBlocks.FIRST_VOLUME))
		
		next(rr)
		next(rr)
		self.assertFalse(rr._read())

		self.assertTrue(len(rr.read_all()) == 2)
		
	def test_error_no_file(self):
		""" RarReader could not find the file. """
		self.assertRaises(ArchiveNotFoundError, RarReader, "")
		self.assertRaises(ArchiveNotFoundError, RarReader, None)
			
	def test_error_short_header(self):
		""" The header received has not the minimum length.
			'Can not read basic block header.' """
		stream = io.BytesIO()
		stream.name = "name to imitate real file"
		# reach the minimum size
		stream.write(RAR_MARKER_BLOCK)
		stream.write(TestRarBlocks.FIRST_VOLUME)
		# must be smaller than 7 bytes
		stream.write(TestRarBlocks.FIRST_VOLUME[:6])
		stream.seek(0)

		rr = RarReader(stream)
		next(rr)
		next(rr)
		self.assertRaises(EnvironmentError, next, rr)
		
	def test_error_bad_length_header(self):
		""" The length flag of the header is not the same 
			as the actual length.
			'Invalid RAR block length at offset 0xc' """
		stream = io.BytesIO()
		stream.write(RAR_MARKER_BLOCK) # 7 bytes
		stream.write(TestRarBlocks.FIRST_VOLUME)
		
		# set the length field to a bigger value
		stream.seek(12) # 0x0D 0x00
		stream.write(b"\x0E\x00")
		stream.seek(0)

		rr = RarReader(stream)
		next(rr) # Marker block OK
		self.assertRaises(EnvironmentError, next, rr)
		
	def test_error_bad_size(self):
		""" The file is too small. The minimum RAR size is 20 bytes. """
		stream = io.BytesIO()
		stream.write(RAR_MARKER_BLOCK)
		stream.seek(0)
		self.assertRaises(ValueError, RarReader, stream)

	def test_error_bad_data(self):
		""" The file is not a valid rar archive or srr file. """
		stream = io.BytesIO()
		stream.write(bytearray(20))
		stream.seek(0)
		self.assertRaises(ValueError, RarReader, stream)
		
	def test_read_files(self):
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
					"store_little", "store_little_srrfile_with_path.srr"))
		self.assertEqual(rr.list_files(), 
						 ['store_little/store_little.srr'])
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
						  "store_little", "store_little.rar"))
		self.assertEqual(rr.list_files(), ['little_file.txt'])
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
			"store_split_folder_old_srrsfv_windows", "store_split_folder.srr"))
		self.assertEqual(rr.list_files(), ['store_split_folder.sfv'])
		
	def test_iterator(self):
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
					"store_little", "store_little_srrfile_with_path.srr"))
		for block in rr:
			self.assertTrue(block)
		
	def test_read_sfx(self):
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
					"best_little", "best_little_sfxgui.exe"), enable_sfx=True)
		read = rr.read_all()
		self.assertEqual(len(read), 4, "No 4 blocks found.")
		self.assertEqual(type(read[0]), RarBlock)
		self.assertEqual(read[0].rawtype, BlockType.RarMin)
		self.assertEqual(read[len(read) - 1].rawtype, BlockType.RarMax)
		for r in read:
			if r.rawtype == BlockType.RarPackedFile:
				self.assertEqual(r.file_name, "little_file.txt")
				self.assertEqual(r.file_datetime, (2011, 3, 6, 15, 14, 12))

class TestSrrHeaderBlock(unittest.TestCase): # 0x69
	def test_srr_header_read(self):
		data = (b"\x69\x69\x69\x01\x00\x1d\x00"
			b"\x14\x00\x52\x65\x53\x63\x65\x6e\x65\x20\x2e"
			b"\x4e\x45\x54\x20\x42\x65\x74\x61\x20\x31\x31")
		srrh = SrrHeaderBlock(data)
		self.assertEqual(srrh.crc, struct.unpack_from(str("<H"), data, 0)[0])
		self.assertEqual(srrh.rawtype, struct.unpack_from(str("<B"), data, 2)[0])
		self.assertEqual(srrh.flags, struct.unpack_from(str("<H"), data, 3)[0])
		self.assertEqual(srrh.header_size, struct.unpack_from(str("<H"), data, 5)[0])
		self.assertEqual(srrh.appname, "ReScene .NET Beta 11")
		
		# old C implementation causes issues because of minimal header
		# //char name[] = "rescene_0.4_c";
		data = b"\x69\x69\x69\x00\x00\x07\x00"
		srrh = SrrHeaderBlock(data)
		self.assertFalse(srrh.flags & SrrHeaderBlock.SRR_APP_NAME_PRESENT)
		self.assertFalse(srrh.flags & SrrHeaderBlock.LONG_BLOCK)
		self.assertEqual(srrh.crc, struct.unpack_from(str("<H"), data, 0)[0])
		self.assertEqual(srrh.rawtype, struct.unpack_from(str("<B"), data, 2)[0])
		self.assertEqual(srrh.flags, struct.unpack_from(str("<H"), data, 3)[0])
		self.assertEqual(srrh.header_size, struct.unpack_from(str("<H"), data, 5)[0])
		self.assertEqual(srrh.appname, "")
		
		hblock = SrrHeaderBlock(appname="Application Name")
		self.assertTrue(hblock.flags & SrrHeaderBlock.SRR_APP_NAME_PRESENT)
		# actually never a long block
		self.assertFalse(hblock.flags & RarBlock.LONG_BLOCK)
		mhblock = SrrHeaderBlock(appname="")
		self.assertFalse(mhblock.flags & SrrHeaderBlock.SRR_APP_NAME_PRESENT)
		self.assertFalse(mhblock.flags & RarBlock.LONG_BLOCK)
		self.assertEqual(mhblock.block_bytes(), data)
		
	def test_srr_header_write(self):
		data = (b"\x69\x69\x69\x01\x00\x1d\x00"
			b"\x14\x00\x52\x65\x53\x63\x65\x6e\x65\x20\x2e"
			b"\x4e\x45\x54\x20\x42\x65\x74\x61\x20\x31\x31")
		srrh = SrrHeaderBlock(appname="ReScene .NET Beta 11")
		self.assertEqual(srrh.block_bytes(), data)
		
		# empty application name
		srrh = SrrHeaderBlock(appname="")
		self.assertEqual(srrh.appname, "")

class TestSrrFileBlocks(unittest.TestCase): # 0x6A
	def test_srr_stored_file_read(self):
		"""
		\x23\x00
		>>> int('23', 16)
		35
		>>> int('0174', 16)
		372
		>>> int('0016', 16)
		22
		"""
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files", 
					   "store_split_folder_old_srrsfv_windows",
					   "store_split_folder.srr"))
		sfb = [s for s in rr.read_all() 
			   if isinstance(s, SrrStoredFileBlock)][0]
		self.assertEqual(sfb.file_size, 372)
		self.assertEqual(sfb.file_name, "store_split_folder.sfv")
		self.assertEqual(len(sfb.file_name), 22)
		self.assertEqual(sfb.block_position + sfb.header_size, 0x3C)
		self.assertEqual(sfb.header_size, sfb.header_size)
		
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
					   "store_little", "store_little_srrfile_with_path.srr"))
		sfb = [s for s in rr.read_all() 
			   if isinstance(s, SrrStoredFileBlock)][0]
		self.assertEqual(sfb.file_size, 124)
		self.assertEqual(sfb.file_name, 
						 "store_little/store_little.srr")
		self.assertEqual(len(sfb.file_name), 29)
		self.assertEqual(sfb.block_position + sfb.header_size, 0x43)
		
		# Unicode tests
		rr = RarReader(os.path.join(os.pardir, os.pardir, "test_files",
					   "store_utf8_comment", "utf8_filename_added.srr"))
		sfb = [s for s in rr.read_all() 
			   if isinstance(s, SrrStoredFileBlock)][0]
		self.assertEqual(sfb.file_name, "Κείμενο στην ελληνική γλώσσα.txt")

	def test_srr_stored_file_write(self):
		# data from store_split_folder.srr SrrStoredFileBlock
		# 7 byte header, size, filename length, filename
		data = (b"\x6a\x6a\x6a\x00\x80\x23\x00"
				b"\x74\x01\x00\x00" + b"\x16\x00"
				b"\x73\x74\x6f\x72\x65\x5f\x73\x70\x6c\x69\x74"
				b"\x5f\x66\x6f\x6c\x64\x65\x72\x2e\x73\x66\x76")
		sfb = SrrStoredFileBlock(file_name="store_split_folder.sfv", 
								 file_size=372)
		self.assertEqual(sfb.block_bytes(), data)
		
		self.assertRaises(AttributeError, SrrStoredFileBlock, 
						  file_name="dir?/file.name", file_size=42)
		self.assertRaises(AttributeError, SrrStoredFileBlock, 
						  file_name="file.sfv", file_size=-7)
		
		# Unicode tests
		sfb = SrrStoredFileBlock(file_name="Κείμενο στην ελληνική γλώσσα.txt",
								 file_size=65)
		# tests file name attribute
		self.assertEqual(sfb.file_name,
			"Κείμενο στην ελληνική γλώσσα.txt")
		# tests full block (including the previous test)
		data = bytearray.fromhex("6A 6A 6A 00 80 46 00 41 00 00 00 39 00 CE 9A CE B5 CE AF"
		" CE BC CE B5 CE BD CE BF 20 CF 83 CF 84 CE B7 CE BD 20 CE B5 CE"
		" BB CE BB CE B7 CE BD CE B9 CE BA CE AE 20 CE B3 CE BB CF 8E CF"
		" 83 CF 83 CE B1 2E 74 78 74")
		self.assertEqual(sfb.block_bytes(), data)
		
		rfile = io.BytesIO()
		rfile.write(b"\x69\x69\x69\x00\x00\x07\x00") # minimal header
		sfb = SrrStoredFileBlock(file_name="file name.ext", file_size=100)
		rfile.write(sfb.block_bytes())
		rfile.write(bytearray(100)) # 100 bytes null file
		rfile.seek(0)
		rfile.name = "bogus file name to make RarReader work with a stream"
		RarReader(rfile).read_all() # it doens't give an error

	def test_srr_stored_file_error(self):
		# max possible file name length
		SrrStoredFileBlock(file_name="j" * 0xFFF2, file_size=1911)
		self.assertRaises(AttributeError, SrrStoredFileBlock, 
		                  file_name="j" * 0xFFF3, file_size=1337)
		self.assertRaises(AttributeError, SrrStoredFileBlock,
		                  file_name="", file_size=31337)
		
class TestOsoHashBlocks(unittest.TestCase):
	def test_create_oso_hash_block(self):
		block = SrrOsoHashBlock(file_name="breakdance.avi",
							file_size=12909756, oso_hash="8e245d9679d31e12")
		self.assertEqual(block.file_name, "breakdance.avi")
		self.assertEqual(block.file_size, 12909756)
		self.assertEqual(block.oso_hash, "8e245d9679d31e12")
		
		block2 = SrrOsoHashBlock(bbytes=block.block_bytes())
		self.assertEqual(block2.file_name, "breakdance.avi")
		self.assertEqual(block2.file_size, 12909756)
		self.assertEqual(block2.oso_hash, "8e245d9679d31e12")
		
class TestRarBlocks(unittest.TestCase):
	""" For testing all RAR block classes. """
	
	# first volume flag set, nothing else. Archive header ( MAIN_HEAD )
	FIRST_VOLUME = b"\xF1\xFB\x73\x01\x00\x0D\x00\x00\x00\x00\x00\x00\x00"
	
	def test_srr_rar_file_read(self): #0x71
		# from store_empty.srr
		# Before Python 3, there is no bytes.fromhex(), and the
		# "struct" module does not unpack from bytearray() objects
		data = bytes(bytearray.fromhex("71 71 71 01 00 18 00"
		"0F 00 73 74 6F 72 65 5F 65 6D 70 74 79 2E 72 61 72 52 61 72 21"
		"1A 07 00 CF 90 73 00 00 0D 00 00 00 00 00 00 00 07 47 74 20 80"
		"2E 00 00 00 00 00 00 00 00 00 03 00 00 00 00 26 7B 66 3E 14 30"
		"0E 00 A4 81 00 00 65 6D 70 74 79 5F 66 69 6C 65 2E 74 78 74 C4"
		"3D 7B 00 40 07 00"))
		srrrfb = SrrRarFileBlock(data, 0)
		self.assertEqual(srrrfb.crc, 0x7171)
		self.assertEqual(srrrfb.rawtype, int("0x71", 16))
		self.assertEqual(srrrfb.flags, struct.unpack(str("<H"), b"\x01\x00")[0])
		self.assertEqual(srrrfb.file_name, "store_empty.rar")
	
	def test_srr_rar_file_write(self): #0x71
		srrrfb = SrrRarFileBlock(file_name="store_empty.rar")
		self.assertEqual(srrrfb.crc, 0x7171)
		self.assertEqual(srrrfb.rawtype, int("0x71", 16))
		self.assertEqual(srrrfb.flags, struct.unpack(str("<H"), b"\x01\x00")[0])
		self.assertEqual(srrrfb.file_name, "store_empty.rar")
		self.assertEqual(srrrfb.block_bytes(), b"\x71\x71\x71\x01\x00"
						 b"\x18\x00\x0F\x00\x73\x74\x6F\x72\x65\x5F\x65"
						 b"\x6D\x70\x74\x79\x2E\x72\x61\x72")

	def test_rar_volume_header(self): # 0x73
		stream = io.BytesIO()
		stream.write(RAR_MARKER_BLOCK)
		stream.write(self.FIRST_VOLUME)
		stream.seek(0)
		stream.name = "test"
		rr = RarReader(stream)
		next(rr)
		vh = next(rr)
		self.assertEqual(vh.header_size, len(self.FIRST_VOLUME))
		self.assertEqual(vh.rawtype, BlockType.RarVolumeHeader)
		
		# test with (old) archive comments included?
		
	
	def test_packed_file(self):
		pass
	
	def test_newsubblock(self):
		""" RR, CMT, AV """
		pass

	def test_old_recovery(self):
		pass
	
""" RR, but has not a 2 char filename:
619f7a00c036007e0400007e04000002a8360e17000000001d30020000000000525250726f746563742b020000003f00000000000000

CMT header blocks
82237a00802300180000000d00000003c4f74343000000001d33030000000000434d54
(3,)
82237a00802300180000000d00000003c4f74343000000001d33030000000000434d54
(3,)
'\x82#z\x00\x80#\x00\x18\x00\x00\x00\r\x00\x00\x00\x03\xc4\xf7CC\x00\x00\x00\x00\x1d3\x03\x00\x00\x00\x00\x00CMT'
"""

