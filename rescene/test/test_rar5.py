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

# Enable Unicode string literals by default because non-ASCII strings are
# used and Python 3.2 does not support the u"" syntax. Also, Python 2.6's
# bytearray.fromhex() only accepts Unicode strings. However the "struct"
# module does not support Unicode format strings until Python 3, so they have
# to be wrapped in str() calls.
from __future__ import unicode_literals

import unittest
from rescene.rar5 import *
from rescene import rar5

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestRar5Reader(unittest.TestCase):
	""" For testing Rar5Reader.
		Rar5Reader parses the incoming file or stream. """

	path = os.path.join(os.pardir, os.pardir, "test_files")
	folder = "rar5"
	
	def test_read_rar4(self):
		rfile = os.path.join(self.path, "store_little", "store_little.rar")
		rr = Rar5Reader(rfile)
		self.assertRaises(ValueError, rr.next)

	def test_read_nothing(self):
		"""We expect None back if we read one time to much."""
		rfile = os.path.join(self.path, "whatever", "file.rar")
		self.assertRaises(ArchiveNotFoundError, Rar5Reader, rfile)

	def test_read_sfx(self):
		stream = io.BytesIO()
		stream.write(b"Random binary data...")
		stream.name = "name to imitate real file"
		rr = Rar5Reader(stream)
		self.assertRaises(StopIteration, rr.next)
		stream.seek(0, os.SEEK_SET)
		rr = Rar5Reader(stream)
		self.assertRaises(StopIteration, rr.next)
		# TODO: SFX support not implemented

	def test_read_all_blocks(self):
		rfile = os.path.join(self.path, self.folder, "rar5_compressed.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
		rfile = os.path.join(self.path, self.folder, "rar5_test.rar")
		for r in Rar5Reader(rfile):
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			
	def test_read_more(self):
		rfile = os.path.join(self.path, self.folder, "rar5_test.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			print(r.explain())
		
	def test_read_more_weird(self):
		rfile = os.path.join(self.path, self.folder, "txt.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			print(r.explain())

	def test_stackoverflow(self):
		data = b"\x33\x92\xb5\xe5\x0a\x01\x05\x06\x00\x05\x01\x01\x00"
		stream = io.BytesIO(data)
		block = BlockFactory.create(stream, False)

class TestParseRarBlocks(unittest.TestCase):
	""" For use with Rar5Reader.
		Rar5Reader parses the incoming file or stream. """

	def test_marker_rar5_start(self):
		header = b"Rar!\x1A\x07\x01\x00"
		stream = io.BytesIO(header)
		block = BlockFactory.create(stream, is_start_file=True)
		self.assertTrue(isinstance(block, MarkerBlock), "incorrect block type")
		self.assertTrue(isinstance(block.basic_header, Rar5HeaderMarker),
			"marker block: bad type for header")
		self.assertTrue(not block.is_srr, "bad default file format")
		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.header_size, 8)
		self.assertEqual(h.size_data, 0)
		self.assertEqual(h.size_extra, 0)
		self.assertEqual(h.type, BLOCK_MARKER)

	def test_marker_rar4_start(self):
		header = b"Rar!\x1A\x07\x00"
		stream = io.BytesIO(header)
		self.assertRaises(
			ValueError, 
			BlockFactory.create,
			stream,
			is_start_file=True)
		
	def test_end_of_archive_header(self):
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype = BLOCK_END
		htype_enc = encode_vint(htype)
		hflags = RAR_SKIP
		hflags_enc = encode_vint(hflags)
		heoa_flags = END_NOT_LAST_VOLUME
		heoa_flags_enc = encode_vint(heoa_flags)

		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(b"whatever")
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(heoa_flags_enc)
		stream.seek(len(b"whatever"), os.SEEK_SET)
		block = BlockFactory.create(stream, is_start_file=False)
		is_end_block = isinstance(block, EndArchiveBlock)
		self.assertTrue(is_end_block, "archive end block expected")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, len(b"whatever"))
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_END)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(block.end_of_archive_flags, heoa_flags)
		self.assertEqual(block.is_last_volume(), False)

	def test_main_archive_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_MAIN
		htype_enc = encode_vint(htype)
		hflags = RAR_EXTRA ^ RAR_SPLIT_AFTER
		self.assertFalse(hflags & RAR_DATA, "never possible on main")
		hflags_enc = encode_vint(hflags)
		harchive_flags = ARCHIVE_VOLUME ^ ARCHIVE_NUMBER
		harchive_flags_enc = encode_vint(harchive_flags)
		hvolume_number = 1
		hvolume_number_enc = encode_vint(hvolume_number)

		locator_record = io.BytesIO()
		ltype = encode_vint(LOCATOR_RECORD)
		lflags = encode_vint(LOCATOR_QUICK ^ LOCATOR_RR)
		quick_open_offset = 12345
		lqoo = encode_vint(quick_open_offset)
		recovery_record_offset = 23456
		lrro = encode_vint(recovery_record_offset)
		lsize = len(ltype) + len(lflags) + len(lqoo) + len(lrro)
		locator_record.write(encode_vint(lsize))
		locator_record.write(ltype)
		locator_record.write(lflags)
		locator_record.write(lqoo)
		locator_record.write(lrro)
		locator_record.seek(0)
		extra_area = locator_record.read()
		hextra_size = encode_vint(len(extra_area))

		hsize = (4 + 3 + len(htype_enc) + len(hflags_enc) +
			len(hextra_size) + len(harchive_flags_enc) + 1)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size)
		stream.write(harchive_flags_enc)
		stream.write(hvolume_number_enc)
		stream.write(extra_area)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_main_block = isinstance(block, MainArchiveBlock)
		self.assertTrue(is_main_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_MAIN)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, len(extra_area))

		self.assertEqual(block.archive_flags, harchive_flags)
		self.assertEqual(block.volume_number, hvolume_number)
		self.assertEqual(block.quick_open_offset, quick_open_offset)
		self.assertEqual(block.recovery_record_offset, recovery_record_offset)
		self.assertEqual(block.undocumented_value, 0)
		
		self.assertEqual(h.size_data, 0)

	def test_encryption_block(self):
		pass

class TestRar5Vint(unittest.TestCase):
	"""Tests the rar 5 vint"""
	def test_read_vint(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x81")
		stream.write(b"\x01")
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 16384 + 129, "128 bit is in the next byte")

	def test_read_vint_single_byte_all_bits(self):
		stream = io.BytesIO()
		stream.write(b"\x7F")  # first bit not set
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 255 - 128, "max value single vint byte")

	def test_read_vint_zeros(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x82")
		stream.write(b"\x00")  # allocated bits without influence
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 257, "256 bit is in the next byte")
		
	def test_write_vint(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\xF1")
		stream.write(b"\x81")
		stream.write(b"\x01")
		stream.seek(0)
		number = read_vint(stream)
		serialized = encode_vint(number)
		tnumber = read_vint(io.BytesIO(serialized))
		self.assertEqual(tnumber, number, "encoding to vint and back failed")
