#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012 pyReScene
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
import os
import tempfile
import shutil
import os.path
import struct

from resample.main import get_file_type, stsc, FileType
import resample.srs

class TestGetFileType(unittest.TestCase):
	"""http://samples.mplayerhq.hu/
	http://archive.org/details/2012.10.samples.mplayerhq.hu"""
	def test_mkv(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x1A\x45\xDF\xA3\x93\x42\x82\x88"
		        b"\x6D\x61\x74\x72\x6F\x73\x6B\x61\x42")
		f.close()
		self.assertEqual(FileType.MKV, get_file_type(f.name))
		os.unlink(f.name)
		
	def test_avi(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x52\x49\x46\x46\x10\xF6\x6E\x01"
		        b"\x41\x56\x49\x20\x4C\x49\x53\x54\x7E")
		f.close()
		self.assertEqual(FileType.AVI, get_file_type(f.name))
		os.unlink(f.name)
		
	def test_mp4(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x00\x00\x00\x18\x66\x74\x79\x70"
		        b"\x6D\x70\x34\x31\x00\x00\x00\x00\x6D")
		f.close()
		self.assertEqual(FileType.MP4, get_file_type(f.name))
		os.unlink(f.name)
		
	def test_wmv(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write(b"\x30\x26\xB2\x75\x8E\x66\xCF\x11"
		        b"\xA6\xD9\x00\xAA\x00\x62\xCE\x6C")
		f.close()
		self.assertEqual(FileType.WMV, get_file_type(f.name))
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

class TestMp4CreateSrs(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp(prefix="pyrescene-")
	def tearDown(self):
		shutil.rmtree(self.dir)
	
	def runTest(self):
		ftyp = (b"ftyp", b"")
		mdat = (b"mdat", bytearray(100 * 100))
		tkhd = (b"tkhd", struct.pack(">LLLL", 0, 0, 0, 1))
		stsc = (b"stsc", struct.pack(">LL LLL", 0, 1, 1, 1, 1))
		stsz = (b"stsz", struct.pack(">LLL", 0, 100, 100))
		stco = (b"stco", struct.pack(">LL", 0, 100) +
			struct.pack(">L", 0) * 100)
		data = serialise_atoms((
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
		
		argv = [sample, "-y", "-o", self.dir]
		resample.srs.main(argv, no_exit=True)
		
		size = os.path.getsize(os.path.join(self.dir, "sample.srs"))
		msg = "SRS size {0} should be much less than sample size {1}"
		msg = msg.format(size, len(data))
		self.assertTrue(size < len(data) / 2, msg)

def serialise_atoms(atoms):
	buffer = bytearray()
	for atom in atoms:
		(type, data) = atom
		if not isinstance(data, (bytes, bytearray)):
			data = serialise_atoms(data)
		buffer.extend(struct.pack("> L 4s", 8 + len(data), type))
		buffer.extend(data)
	return buffer

if __name__ == "__main__":
	unittest.main()