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

import unittest
import os
import tempfile

from resample.main import get_file_type, stsc, FileType

class TestGetFileType(unittest.TestCase):
	"""http://samples.mplayerhq.hu/"""
	def test_mkv(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write("1A45DFA3934282886D6174726F736B6142".decode('hex'))
		f.close()
		self.assertEqual(FileType.MKV, get_file_type(f.name))
		os.unlink(f.name)
	def test_avi(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write("5249464610F66E01415649204C4953547E".decode('hex'))
		f.close()
		self.assertEqual(FileType.AVI, get_file_type(f.name))
		os.unlink(f.name)
	def test_mp4(self):
		f = tempfile.NamedTemporaryFile(delete=False)
		f.write("00000018667479706D703431000000006D".decode('hex'))
		f.close()
		self.assertEqual(FileType.MP4, get_file_type(f.name))
		os.unlink(f.name)
		
class TestStsc(unittest.TestCase):
	def test_normal(self):
		inlist = [(1, 4, 0), (2, 4, 0), (3, 4, 0), (4, 4, 0), ]
		outlist = stsc(inlist)
		self.assertEquals(inlist, outlist)
		
	def test_compact(self):
		inlist = [(1, 4, 0), (2, 4, 7), (5, 8, 0), (7, 4, 0), ]
		outlist = stsc(inlist)
		expected = [(1, 4, 0), (2, 4, 7), (3, 4, 7), (4, 4, 7), (5, 8, 0), 
		            (6, 8, 0), (7, 4, 0), ]
		self.assertEquals(expected, outlist)

if __name__ == "__main__":
	unittest.main()