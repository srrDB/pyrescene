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

class TestRar5Compression(unittest.TestCase):
	path = os.path.join(os.pardir, os.pardir, "test_files")
	folder = "rar5"

	def test_compressed_block_detection(self):
		rfile = os.path.join(self.path, self.folder, "rar5_compressed.rar")
		has_compressed = False
		for rblock in Rar5Reader(rfile):
			header = rblock.header()
			if header.flags & RAR_DATA and rblock.is_file_block():
				if rblock.is_compressed():
					has_compressed = True
					break
		self.assertTrue(has_compressed, "Expected compressed file blocks")


class TestRar5MultiVolumeArchives(unittest.TestCase):
	path = os.path.join(os.pardir, os.pardir, "test_files")

	def _find_block(self, rfile, predicate):
		for block in Rar5Reader(rfile):
			if predicate(block):
				return block
		return None

	def _first_file_block(self, rfile):
		return self._find_block(rfile, lambda block: block.is_file_block())

	def _end_block(self, rfile):
		return self._find_block(rfile, lambda block: isinstance(block, EndArchiveBlock))

	def test_multi_volume_compressed(self):
		part1 = os.path.join(self.path, "rar5-compress-multi", "rar5-compress-multi.part1.rar")
		part2 = os.path.join(self.path, "rar5-compress-multi", "rar5-compress-multi.part2.rar")

		file_block_part1 = self._first_file_block(part1)
		self.assertTrue(file_block_part1, "Expected file block in part1")
		self.assertTrue(file_block_part1.header().flags & RAR_SPLIT_AFTER)
		self.assertTrue(file_block_part1.is_compressed())

		file_block_part2 = self._first_file_block(part2)
		self.assertTrue(file_block_part2, "Expected file block in part2")
		self.assertTrue(file_block_part2.header().flags & RAR_SPLIT_BEFORE)

		end_block = self._end_block(part2)
		self.assertTrue(end_block, "Expected end block in part2")
		self.assertTrue(end_block.is_last_volume())

	def test_multi_volume_no_compression(self):
		part1 = os.path.join(self.path, "rar5-nocompression-multi", "rar5-nocompression-multi.part1.rar")
		part2 = os.path.join(self.path, "rar5-nocompression-multi", "rar5-nocompression-multi.part2.rar")

		file_block_part1 = self._first_file_block(part1)
		self.assertTrue(file_block_part1, "Expected file block in part1")
		self.assertTrue(file_block_part1.header().flags & RAR_SPLIT_AFTER)
		self.assertEqual(file_block_part1.algorithm, 0)
		self.assertEqual(file_block_part1.compression_method_value(), 0)

		file_block_part2 = self._first_file_block(part2)
		self.assertTrue(file_block_part2, "Expected file block in part2")
		self.assertTrue(file_block_part2.header().flags & RAR_SPLIT_BEFORE)

		end_block = self._end_block(part2)
		self.assertTrue(end_block, "Expected end block in part2")
		self.assertTrue(end_block.is_last_volume())

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
		self.assertEqual(len(hcrc32), 4)
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
		hextra_size_enc = encode_vint(len(extra_area))

		hsize = (len(htype_enc) + len(hflags_enc) +
			len(hextra_size_enc) + len(harchive_flags_enc) + 
			len(hvolume_number_enc) + len(extra_area))
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size_enc)
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

	def test_encryption_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_ENCRYPTION
		htype_enc = encode_vint(htype)
		hflags = 0
		hflags_enc = encode_vint(hflags)
		enc_version = 0  # AES-265
		henc_version = encode_vint(enc_version)
		enc_flags = ENCRYPTION_PASSWORD_CHECK
		henc_flags= encode_vint(enc_flags)
		kdf_count = 13
		hkdf_count = struct.pack('<B', kdf_count)  # 1 byte
		salt = b"0123456701234567"  # 16 bytes
		check_value = b"012345678912"  # 12 bytes
		
		hsize = (len(htype_enc) + len(hflags_enc) +
			len(henc_version) + len(henc_flags) + 1 + 16 + 12)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(henc_version)
		stream.write(henc_flags)
		stream.write(hkdf_count)
		stream.write(salt)
		stream.write(check_value)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_enc_block = isinstance(block, FileEncryptionBlock)
		self.assertTrue(is_enc_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_ENCRYPTION)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, 0)
		self.assertEqual(h.size_data, 0)
		self.assertEqual(block.encryption_version, enc_version)
		self.assertEqual(block.encryption_flags, enc_flags)
		self.assertEqual(block.kdf_count, hkdf_count)
		self.assertEqual(block.salt, salt)
		self.assertEqual(block.check_value, check_value)

	def test_file_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_FILE
		htype_enc = encode_vint(htype)
		hflags = RAR_EXTRA ^ RAR_DATA ^ RAR_SPLIT_AFTER
		hflags_enc = encode_vint(hflags)
		extra_size = 11
		data_size = 22
		hextra_size = encode_vint(extra_size)
		hdata_size = encode_vint(data_size)

		hfile_flags = FILE_UNIX_TIME ^ FILE_CRC32 
		hfile_flags_enc = encode_vint(hfile_flags)
		hunpacked_size = data_size
		hunpacked_size_enc = encode_vint(hunpacked_size)
		attributes = 0
		hattributes_enc = encode_vint(attributes)
		mtime = 0
		hmtime = struct.pack('<L', mtime)
		data_crc32 = 0x12345678
		hdata_crc32 = struct.pack('<L', data_crc32)
		compression_info = 0
		hcompression_info_enc = encode_vint(compression_info)
		host_os = 1  # Unix
		hhost_os_enc = encode_vint(host_os)
		name = b"test_file_name.ext"
		name_length = len(name)
		hname_length_enc = encode_vint(name_length)
		
		extra = b"x" * extra_size
		data = b"y" * data_size
		
		# size starts from header type
		hsize = (len(htype_enc) + len(hflags_enc) +
			len(hextra_size) + len(hdata_size) +
			len(hfile_flags_enc) + len(hunpacked_size_enc) +
			len(hattributes_enc) + 8 + len(hcompression_info_enc) +
			len(hhost_os_enc) +
			len(hname_length_enc) + len(name) + 
			extra_size)
		hsize_enc = encode_vint(hsize)

		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size)
		stream.write(hdata_size)
		stream.write(hfile_flags_enc)
		stream.write(hunpacked_size_enc)
		stream.write(hattributes_enc)
		stream.write(hmtime)
		stream.write(hdata_crc32)
		stream.write(hcompression_info_enc)
		stream.write(hhost_os_enc)
		stream.write(hname_length_enc)
		stream.write(name)
		stream.write(extra)
		stream.write(data)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_file_block = isinstance(block, FileServiceBlock)
		self.assertTrue(is_file_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_FILE)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, extra_size)
		self.assertEqual(h.size_data, data_size)

		self.assertEqual(block.file_flags, hfile_flags)
		self.assertEqual(block.unpacked_size, hunpacked_size)
		self.assertEqual(block.attributes, attributes)
		self.assertEqual(block.mtime, mtime)
		self.assertEqual(block.datacrc32, data_crc32)
		self.assertEqual(block.algorithm, 0)
		self.assertEqual(block.solid, 0)
		self.assertEqual(block.method, 0)
		self.assertEqual(block.dict_size, 0)
		self.assertEqual(block.host_os, host_os)
		self.assertEqual(block.name, name)
		self.assertEqual(block.extra_area_size, extra_size)
		self.assertEqual(h.size_data, data_size)

	def test_file_header_compression_settings(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_FILE
		htype_enc = encode_vint(htype)
		hflags = RAR_DATA ^ RAR_EXTRA
		hflags_enc = encode_vint(hflags)
		extra_size = 0
		data_size = 22
		hextra_size = encode_vint(extra_size)
		hdata_size = encode_vint(data_size)

		hfile_flags = FILE_UNIX_TIME ^ FILE_CRC32
		hfile_flags_enc = encode_vint(hfile_flags)
		hunpacked_size = data_size
		hunpacked_size_enc = encode_vint(hunpacked_size)
		attributes = 0
		hattributes_enc = encode_vint(attributes)
		mtime = 0
		hmtime = struct.pack('<L', mtime)
		data_crc32 = 0x12345678
		hdata_crc32 = struct.pack('<L', data_crc32)

		method_value = 3
		dict_value = 4
		compression_info = (method_value << 7) | (dict_value << 10)
		hcompression_info_enc = encode_vint(compression_info)
		host_os = 1  # Unix
		hhost_os_enc = encode_vint(host_os)
		name = b"test_file_name.ext"
		name_length = len(name)
		hname_length_enc = encode_vint(name_length)

		hsize = (len(htype_enc) + len(hflags_enc) +
			len(hextra_size) + len(hdata_size) +
			len(hfile_flags_enc) + len(hunpacked_size_enc) +
			len(hattributes_enc) + 8 + len(hcompression_info_enc) +
			len(hhost_os_enc) +
			len(hname_length_enc) + len(name) +
			extra_size)
		hsize_enc = encode_vint(hsize)

		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size)
		stream.write(hdata_size)
		stream.write(hfile_flags_enc)
		stream.write(hunpacked_size_enc)
		stream.write(hattributes_enc)
		stream.write(hmtime)
		stream.write(hdata_crc32)
		stream.write(hcompression_info_enc)
		stream.write(hhost_os_enc)
		stream.write(hname_length_enc)
		stream.write(name)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		self.assertTrue(block.is_file_block())
		self.assertTrue(block.is_compressed())
		self.assertEqual(block.compression_method_value(), method_value)
		self.assertEqual(block.dictionary_size_value(), dict_value)

class TestParseRarFileRecords(unittest.TestCase):
	def test_file_encryption_record(self):
		rtype = 0x01
		type_enc = encode_vint(rtype)
		version = 0  # AES-265
		version_enc = encode_vint(version)
		flags = RECORD_PASSWORD_CHECK 
		flags_enc = encode_vint(flags)
		kdf_count = S_BYTE.pack(1)
		salt = b"0123456701234567"  # 16 bytes
		iv = b"0123456701234567"  # 16 bytes
		check_value = b"012345678901"  # 12 bytes
		
		size = (len(type_enc) + len(version_enc) + 
			len(flags_enc) + 1 + 16 + 16 + 12)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(version_enc)
		stream.write(flags_enc)
		stream.write(kdf_count)
		stream.write(salt)
		stream.write(iv)
		stream.write(check_value)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.version, version)
		self.assertEqual(record.flags, flags)
		self.assertEqual(record.kdf_count, kdf_count)
		self.assertEqual(record.salt, salt)
		self.assertEqual(record.iv, iv)
		self.assertEqual(record.check_value, check_value)

	def test_file_hash_record(self):
		rtype = 0x02
		type_enc = encode_vint(rtype)
		rhash = 0
		hash_enc = encode_vint(rhash)
		hash_data = b"0" * 32
		
		size = (len(type_enc) + len(hash_enc) + 
			len(hash_data))

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(hash_enc)
		stream.write(hash_data)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.hash, rhash)
		self.assertEqual(record.hash_data, hash_data)

	def test_file_hash_record_future(self):
		"""test else case used for future hashes"""
		rtype = 0x02
		type_enc = encode_vint(rtype)
		rhash = 1
		hash_enc = encode_vint(rhash)
		hash_data = b"E" * 42
		
		size = (len(type_enc) + len(hash_enc) + 
			len(hash_data))

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(hash_enc)
		stream.write(hash_data)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.hash, rhash)
		self.assertEqual(record.hash_data, hash_data)

	def test_file_time_record(self):
		rtype = 0x03
		type_enc = encode_vint(rtype)
		rflags = TIME_UNIX ^ TIME_MODIFICATION ^ TIME_CREATION
		flags_enc = encode_vint(rflags)
		mtime = b"0" * 4
		ctime = b"1" * 4
		
		size = len(type_enc) + len(flags_enc) + len(mtime) + len(ctime)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(mtime)
		stream.write(ctime)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.mtime, mtime)
		self.assertEqual(record.ctime, ctime)

	def test_file_version_record(self):
		rtype = 0x04
		type_enc = encode_vint(rtype)
		rflags = 0
		flags_enc = encode_vint(rflags)
		file_version_number = 42
		version_enc = encode_vint(file_version_number) 
		
		size = len(type_enc) + len(flags_enc) + len(version_enc)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(version_enc)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.version_number, file_version_number)

	def test_file_redirection_record(self):
		rtype = 0x05
		type_enc = encode_vint(rtype)
		redirection_type = 1
		redirection_type_enc = encode_vint(redirection_type)
		rflags = LINK_DIRECTORY
		flags_enc = encode_vint(rflags)
		name = b"test_file_name.ext"
		name_length = len(name)
		name_length_enc = encode_vint(name_length)
		
		size = (len(type_enc) + len(redirection_type_enc) + 
			len(flags_enc) + len(name_length_enc) + name_length)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(redirection_type_enc)
		stream.write(flags_enc)
		stream.write(name_length_enc)
		stream.write(name)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.redirection_type, redirection_type)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.name, name)

	def test_file_unix_owner_record(self):
		rtype = 0x06
		type_enc = encode_vint(rtype)
		rflags = UNIX_USER ^ UNIX_USER_ID ^ UNIX_GROUP ^ UNIX_GROUP_ID
		flags_enc = encode_vint(rflags)
		user_name = b"gfy"
		group_name = b"root"
		user_name_len_enc = encode_vint(len(user_name))
		group_name_len_enc = encode_vint(len(group_name))
		user_id = 1337
		user_id_enc = encode_vint(user_id)
		group_id = 1337
		group_id_enc = encode_vint(group_id)

		size = (len(type_enc) + len(flags_enc) + 
			len(user_name_len_enc) + len(user_name) +
			len(group_name_len_enc) + len(group_name) +
			len(user_id_enc) + len(group_id_enc))

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(user_name_len_enc)
		stream.write(user_name)
		stream.write(group_name_len_enc)
		stream.write(group_name)
		stream.write(user_id_enc)
		stream.write(group_id_enc)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.owner, user_name)
		self.assertEqual(record.group, group_name)
		self.assertEqual(record.user_id, user_id)
		self.assertEqual(record.group_id, group_id)

	def test_file_unix_service_data_record(self):
		rtype = 0x07
		type_enc = encode_vint(rtype)
		data = b"whatever data being here"

		size = len(type_enc) + len(data) 

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(data)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.data, data)

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


class TestEndArchiveBlock(unittest.TestCase):
	"""Tests for EndArchiveBlock is_last_volume logic"""
	
	def test_is_last_volume_true(self):
		"""When END_NOT_LAST_VOLUME flag is NOT set, it IS the last volume"""
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype = BLOCK_END
		htype_enc = encode_vint(htype)
		hflags = RAR_SKIP
		hflags_enc = encode_vint(hflags)
		# No END_NOT_LAST_VOLUME flag = this IS the last volume
		heoa_flags = 0
		heoa_flags_enc = encode_vint(heoa_flags)

		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		
		stream = io.BytesIO()
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(heoa_flags_enc)
		stream.seek(0)
		
		block = BlockFactory.create(stream, is_start_file=False)
		self.assertTrue(block.is_last_volume(), 
			"Should be last volume when END_NOT_LAST_VOLUME is not set")
	
	def test_is_last_volume_false(self):
		"""When END_NOT_LAST_VOLUME flag IS set, it is NOT the last volume"""
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype = BLOCK_END
		htype_enc = encode_vint(htype)
		hflags = RAR_SKIP
		hflags_enc = encode_vint(hflags)
		# END_NOT_LAST_VOLUME flag set = NOT the last volume
		heoa_flags = END_NOT_LAST_VOLUME
		heoa_flags_enc = encode_vint(heoa_flags)

		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		
		stream = io.BytesIO()
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(heoa_flags_enc)
		stream.seek(0)
		
		block = BlockFactory.create(stream, is_start_file=False)
		self.assertFalse(block.is_last_volume(), 
			"Should NOT be last volume when END_NOT_LAST_VOLUME is set")


class TestEOFHandling(unittest.TestCase):
	"""Tests for EOF handling during block parsing"""
	
	def test_eof_on_empty_stream(self):
		"""Empty stream should raise EOFError"""
		stream = io.BytesIO(b"")
		self.assertRaises(EOFError, BlockFactory.create, stream, False)
	
	def test_eof_on_partial_crc(self):
		"""Incomplete CRC (less than 4 bytes) should raise EOFError"""
		stream = io.BytesIO(b"\x12\x34")  # Only 2 bytes, need 4
		self.assertRaises(EOFError, BlockFactory.create, stream, False)
	
	def test_eof_on_zero_header_size(self):
		"""Zero header size should raise EOFError as invalid"""
		stream = io.BytesIO()
		stream.write(struct.pack('<L', 0x12345678))  # CRC
		stream.write(b"\x00")  # header_size = 0 (invalid)
		stream.seek(0)
		self.assertRaises(EOFError, BlockFactory.create, stream, False)
	
	def test_rar5_reader_handles_eof_gracefully(self):
		"""Rar5Reader should handle truncated streams gracefully"""
		# Create a stream with just a marker block (no other blocks)
		stream = io.BytesIO(b"Rar!\x1A\x07\x01\x00")
		reader = Rar5Reader(stream)
		blocks = list(reader)
		self.assertEqual(len(blocks), 1)
		self.assertTrue(blocks[0].is_marker_block())


class TestSrrModeBlockParsing(unittest.TestCase):
	"""Tests for SRR mode where file data is stripped but service data is kept"""
	
	def _create_file_block(self, data_size, name=b"test.bin", is_service=False):
		"""Helper to create a file or service block"""
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_SERVICE if is_service else BLOCK_FILE
		htype_enc = encode_vint(htype)
		hflags = RAR_DATA  # Has data area
		hflags_enc = encode_vint(hflags)
		hdata_size = encode_vint(data_size)

		hfile_flags = FILE_CRC32
		hfile_flags_enc = encode_vint(hfile_flags)
		hunpacked_size = encode_vint(data_size)
		hattributes_enc = encode_vint(0)
		data_crc32 = struct.pack('<L', 0x12345678)
		hcompression_info_enc = encode_vint(0)
		hhost_os_enc = encode_vint(0)
		hname_length_enc = encode_vint(len(name))

		hsize = (len(htype_enc) + len(hflags_enc) + len(hdata_size) +
			len(hfile_flags_enc) + len(hunpacked_size) +
			len(hattributes_enc) + 4 + len(hcompression_info_enc) +
			len(hhost_os_enc) + len(hname_length_enc) + len(name))
		hsize_enc = encode_vint(hsize)

		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hdata_size)
		stream.write(hfile_flags_enc)
		stream.write(hunpacked_size)
		stream.write(hattributes_enc)
		stream.write(data_crc32)
		stream.write(hcompression_info_enc)
		stream.write(hhost_os_enc)
		stream.write(hname_length_enc)
		stream.write(name)
		# Add fake data area
		stream.write(b"X" * data_size)
		stream.seek(0)
		return stream
	
	def test_next_block_offset_normal_file_block(self):
		"""Normal RAR file block should skip data area"""
		stream = self._create_file_block(100, is_service=False)
		block = BlockFactory.create(stream, is_start_file=False, is_srr_block=False)
		header_end = block.header().data_offset()
		# Normal mode: next block is after header + data
		self.assertEqual(block.next_block_offset(), header_end + 100)
	
	def test_next_block_offset_srr_file_block(self):
		"""SRR file block should NOT skip data area (data not present)"""
		stream = self._create_file_block(100, is_service=False)
		block = BlockFactory.create(stream, is_start_file=False, is_srr_block=True)
		header_end = block.header().data_offset()
		# SRR mode with file block: data is NOT present, so next block is at header end
		self.assertEqual(block.next_block_offset(), header_end)
	
	def test_next_block_offset_srr_service_block(self):
		"""SRR service block SHOULD include data area (service data IS stored)"""
		stream = self._create_file_block(100, name=b"QO", is_service=True)
		block = BlockFactory.create(stream, is_start_file=False, is_srr_block=True)
		header_end = block.header().data_offset()
		# SRR mode with service block: data IS present
		self.assertEqual(block.next_block_offset(), header_end + 100)
	
	def test_is_file_block_vs_service_block(self):
		"""Verify is_file_block and is_service_block work correctly"""
		file_stream = self._create_file_block(50, is_service=False)
		file_block = BlockFactory.create(file_stream, is_start_file=False)
		self.assertTrue(file_block.is_file_block())
		self.assertFalse(file_block.is_service_block())
		
		service_stream = self._create_file_block(50, name=b"RR", is_service=True)
		service_block = BlockFactory.create(service_stream, is_start_file=False)
		self.assertFalse(service_block.is_file_block())
		self.assertTrue(service_block.is_service_block())


class TestMultiVolumeFlags(unittest.TestCase):
	"""Tests for multi-volume archive flags"""
	
	def _create_file_block_with_flags(self, hflags):
		"""Helper to create a file block with specific flags"""
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_FILE
		htype_enc = encode_vint(htype)
		hflags_enc = encode_vint(hflags)
		
		has_data = hflags & RAR_DATA
		data_size = 100 if has_data else 0
		
		parts = [htype_enc, hflags_enc]
		if has_data:
			parts.append(encode_vint(data_size))
		
		hfile_flags = FILE_CRC32
		hfile_flags_enc = encode_vint(hfile_flags)
		hunpacked_size = encode_vint(1000)
		hattributes_enc = encode_vint(0)
		data_crc32 = struct.pack('<L', 0x12345678)
		hcompression_info_enc = encode_vint(0)
		hhost_os_enc = encode_vint(0)
		name = b"test.bin"
		hname_length_enc = encode_vint(len(name))

		hsize = sum(len(p) for p in parts) + (
			len(hfile_flags_enc) + len(hunpacked_size) +
			len(hattributes_enc) + 4 + len(hcompression_info_enc) +
			len(hhost_os_enc) + len(hname_length_enc) + len(name))
		hsize_enc = encode_vint(hsize)

		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		for p in parts:
			stream.write(p)
		stream.write(hfile_flags_enc)
		stream.write(hunpacked_size)
		stream.write(hattributes_enc)
		stream.write(data_crc32)
		stream.write(hcompression_info_enc)
		stream.write(hhost_os_enc)
		stream.write(hname_length_enc)
		stream.write(name)
		if has_data:
			stream.write(b"X" * data_size)
		stream.seek(0)
		return stream
	
	def test_split_before_flag(self):
		"""RAR_SPLIT_BEFORE indicates data continues from previous volume"""
		stream = self._create_file_block_with_flags(RAR_DATA | RAR_SPLIT_BEFORE)
		block = BlockFactory.create(stream, is_start_file=False)
		self.assertTrue(block.header().flags & RAR_SPLIT_BEFORE)
	
	def test_split_after_flag(self):
		"""RAR_SPLIT_AFTER indicates data continues in next volume"""
		stream = self._create_file_block_with_flags(RAR_DATA | RAR_SPLIT_AFTER)
		block = BlockFactory.create(stream, is_start_file=False)
		self.assertTrue(block.header().flags & RAR_SPLIT_AFTER)
	
	def test_split_both_flags(self):
		"""Middle volume has both SPLIT_BEFORE and SPLIT_AFTER"""
		flags = RAR_DATA | RAR_SPLIT_BEFORE | RAR_SPLIT_AFTER
		stream = self._create_file_block_with_flags(flags)
		block = BlockFactory.create(stream, is_start_file=False)
		h = block.header()
		self.assertTrue(h.flags & RAR_SPLIT_BEFORE)
		self.assertTrue(h.flags & RAR_SPLIT_AFTER)
	
	def test_no_split_flags_single_volume(self):
		"""Single volume file has neither SPLIT flag"""
		stream = self._create_file_block_with_flags(RAR_DATA)
		block = BlockFactory.create(stream, is_start_file=False)
		h = block.header()
		self.assertFalse(h.flags & RAR_SPLIT_BEFORE)
		self.assertFalse(h.flags & RAR_SPLIT_AFTER)


class TestBlockMetadata(unittest.TestCase):
	"""Tests for block metadata retrieval"""
	
	def test_header_data_preserved(self):
		"""Header data bytes should be preserved exactly"""
		# Create a simple end block
		crc = 0xDEADBEEF
		hcrc32_enc = struct.pack('<L', crc)
		htype_enc = encode_vint(BLOCK_END)
		hflags_enc = encode_vint(RAR_SKIP)
		heoa_flags_enc = encode_vint(0)
		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		
		expected_header = hcrc32_enc + hsize_enc + htype_enc + hflags_enc + heoa_flags_enc
		
		stream = io.BytesIO(expected_header)
		block = BlockFactory.create(stream, is_start_file=False)
		
		self.assertEqual(block.metadata(), expected_header)
		self.assertEqual(block.header().header_data, expected_header)
	
	def test_full_header_size_calculation(self):
		"""full_header_size should include CRC + vint size + header"""
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype_enc = encode_vint(BLOCK_END)
		hflags_enc = encode_vint(0)
		heoa_flags_enc = encode_vint(0)
		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		
		stream = io.BytesIO()
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(heoa_flags_enc)
		stream.seek(0)
		
		block = BlockFactory.create(stream, is_start_file=False)
		expected_full_size = 4 + len(hsize_enc) + hsize
		self.assertEqual(block.full_header_size(), expected_full_size)
	
	def test_data_offset_calculation(self):
		"""data_offset should point to start of data area"""
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype_enc = encode_vint(BLOCK_END)
		hflags_enc = encode_vint(RAR_DATA)
		hdata_size_enc = encode_vint(500)
		heoa_flags_enc = encode_vint(0)
		hsize = len(htype_enc) + len(hflags_enc) + len(hdata_size_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		
		stream = io.BytesIO()
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hdata_size_enc)
		stream.write(heoa_flags_enc)
		stream.seek(0)
		
		block = BlockFactory.create(stream, is_start_file=False)
		expected_data_offset = 4 + len(hsize_enc) + hsize
		self.assertEqual(block.header().data_offset(), expected_data_offset)

