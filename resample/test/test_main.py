#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2014 pyReScene
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

from __future__ import division

import unittest
import tempfile
import shutil
import os.path
import struct
import sys
from os import SEEK_CUR

from resample.main import file_type_info, stsc, FileType, sample_class_factory
from resample.main import profile_wmv, FileData
from resample import asf
import resample.srs
import rescene

class TempDirTest(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp(prefix="pyReScene-")
	def tearDown(self):
		shutil.rmtree(self.dir)

class TestGetFileType(unittest.TestCase):
	"""http://samples.mplayerhq.hu/
	http://archive.org/details/2012.10.samples.mplayerhq.hu"""
	def test_mkv(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x1A\x45\xDF\xA3\x93\x42\x82\x88"
		        b"\x6D\x61\x74\x72\x6F\x73\x6B\x61\x42")
		f.close()
		self.assertEqual(FileType.MKV, file_type_info(f.name).file_type)
		os.unlink(f.name)

	def test_avi(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x52\x49\x46\x46\x10\xF6\x6E\x01"
		        b"\x41\x56\x49\x20\x4C\x49\x53\x54\x7E")
		f.close()
		self.assertEqual(FileType.AVI, file_type_info(f.name).file_type)
		os.unlink(f.name)

	def test_mp4(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x00\x00\x00\x18\x66\x74\x79\x70"
		        b"\x6D\x70\x34\x31\x00\x00\x00\x00\x6D")
		f.close()
		self.assertEqual(FileType.MP4, file_type_info(f.name).file_type)
		os.unlink(f.name)

	def test_wmv(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x30\x26\xB2\x75\x8E\x66\xCF\x11"
		        b"\xA6\xD9\x00\xAA\x00\x62\xCE\x6C")
		f.close()
		self.assertEqual(FileType.WMV, file_type_info(f.name).file_type)
		os.unlink(f.name)

class TestStsc(unittest.TestCase):
	"""Help function for decompressing data structure in MP4 files."""
	def test_normal(self):
		inlist = [(1, 4, 0), (2, 4, 0), (3, 4, 0), (4, 4, 0), ]
		outlist = stsc(inlist)
		self.assertEqual(inlist, outlist)

	def test_compact(self):
		inlist = [(1, 4, 0), (2, 4, 7), (5, 8, 0), (7, 4, 0), ]
		outlist = stsc(inlist)
		expected = [(1, 4, 0), (2, 4, 7), (3, 4, 7), (4, 4, 7), (5, 8, 0),
		            (6, 8, 0), (7, 4, 0), ]
		self.assertEqual(expected, outlist)

class TestProfileWmv(TempDirTest):
	def runTest(self):
		wmv = os.path.join(self.dir, "sample.wmv")
		with open(wmv, "w+b") as f:
			f.write(asf.GUID_HEADER_OBJECT)
			f.write(struct.pack("< Q 6x", 0))  # Dummy size

			f.write(asf.GUID_FILE_OBJECT)
			f.write(struct.pack("< Q 16x", 24 + 16 + 8))
			size_fixup = f.tell()
			f.seek(+8, SEEK_CUR)

			for track in range(2):
				f.write(asf.GUID_STREAM_OBJECT)
				void = 16 + 16 + 8 + 4 + 4
				f.write(struct.pack("<Q", 24 + void + 2))
				f.write(bytearray(void))
				f.write(struct.pack("<H", 1 + track))

			f.write(asf.GUID_DATA_OBJECT)
			header = struct.Struct("< Q 16x Q")
			f.write(header.pack(24 + 26 + 100 * 100, 100))
			f.write(bytearray(8 + 26 - header.size))
			for _packet in range(100):
				header = struct.Struct("< B 2x BB BLH B")
				payload1 = struct.Struct("< B BLB 8x H 20x")
				payload2 = struct.Struct("< B BLB 1x H B30x")
				padding = (100 - header.size -
					payload1.size - payload2.size)

				f.write(header.pack(
					0x82,
					0x09,  # Byte for padding size field
					0x5D,
					padding,
					0, 0,
					0x82,  # 2 payloads
				))
				f.write(payload1.pack(
					0x01,  # Track 1
					0, 0,
					8,
					20,
				))
				f.write(payload2.pack(
					0x02,  # Track 2
					0, 0,
					1,
					1 + 30,
					30,
				))
				f.write(bytearray(padding))

			size = f.tell()
			f.seek(size_fixup)
			f.write(struct.pack("<Q", size))

		file_data = FileData(file_name=wmv)
		tracks = profile_wmv(file_data)

		self.assertEqual(5276, file_data.other_length)
		self.assertEqual(10276, file_data.size)
		self.assertEqual(0x4BCABBC7, file_data.crc32 & 0xFFFFFFFF)

		self.assertEqual(2, len(tracks))
		self.assertEqual(1, tracks[1].track_number)
		self.assertEqual(2000, tracks[1].data_length)
		self.assertEqual(2, tracks[2].track_number)
		self.assertEqual(3000, tracks[2].data_length)

class TestMp4CreateSrs(TempDirTest):
	def runTest(self):
		ftyp = (b"ftyp", b"")
		mdat = (b"mdat", bytearray(100 * 100))
		tkhd = (b"tkhd", struct.pack(">LLLL", 0, 0, 0, 1))
		stsc = (b"stsc", struct.pack(">LL LLL", 0, 1, 1, 1, 1))
		stsz = (b"stsz", struct.pack(">LLL", 0, 100, 100))
		stco = (b"stco", struct.pack(">LL", 0, 100) +
			struct.pack(">L", 0) * 100)
		data = serialize_atoms((
			ftyp,
			mdat,
			(b"moov", (
				(b"trak", (
					tkhd,
					(b"mdia", (
						(b"minf", (
							(b"stbl", (
								stsc,
								stsz,
								stco,
							)),
						)),
					)),
				)),
			)),
		))

		sample = os.path.join(self.dir, "sample.mp4")
		with open(sample, "wb") as f:
			f.write(data)

		actualstdout = sys.stdout
		sys.stdout = open(os.devnull, "w")
		argv = [sample, "-y", "-o", self.dir]
		resample.srs.main(argv, no_exit=True)
		sys.stdout = actualstdout

		size = os.path.getsize(os.path.join(self.dir, "sample.srs"))
		msg = "SRS size {0} should be much less than sample size {1}"
		msg = msg.format(size, len(data))
		self.assertTrue(size < len(data) / 2, msg)

def serialize_atoms(atoms):
	abuffer = bytearray()
	for atom in atoms:
		(atom_type, data) = atom
		if not isinstance(data, (bytes, bytearray)):
			data = serialize_atoms(data)
		abuffer.extend(struct.pack("> L 4s", 8 + len(data), atom_type))
		abuffer.extend(data)
	return abuffer

class TestLoad(TempDirTest):
	def runTest(self):
		srr = os.path.join(
			os.path.dirname(__file__),
			os.pardir, os.pardir, "test_files",
			"bug_detected_as_being_different3",
"Akte.2012.08.01.German.Doku.WS.dTV.XViD-FiXTv_f4n4t.srr",
		)
		srs = os.path.join("sample",
			"fixtv-akte.2012.08.01.sample.srs")
		((srs, success),) = rescene.extract_files(srr, self.dir,
			packed_name=srs)
		self.assertTrue(success)

		ftype = file_type_info(srs).file_type
		self.assertEqual(FileType.AVI, ftype)

		sample = sample_class_factory(ftype)
		srs_data, tracks = sample.load_srs(srs)

		self.assertEqual("MKV/AVI ReSample 1.2", srs_data.appname)
		self.assertEqual("fixtv-akte.2012.08.01.sample.avi",
			srs_data.name)
		self.assertEqual(4375502, srs_data.size)
		self.assertEqual(0xC7FB72A8, srs_data.crc32)

		self.assertEqual(3385806, tracks[0].data_length)
		self.assertFalse(tracks[0].match_offset)
		self.assertEqual(917376, tracks[1].data_length)
		self.assertFalse(tracks[1].match_offset)

if __name__ == "__main__":
	unittest.main()
