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
import io
import os
from os.path import join
from errno import ENOENT

from rescene.osohash import compute_hash, osohash_from

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestHash(unittest.TestCase):
	"""
	Test these 2 files please to ensure your algorithm is completely OK: 
		AVI file (12 909 756 bytes) 
			srr_hash: 8e245d9679d31e12 
		DUMMY RAR file (2 565 922 bytes, 4 295 033 890 after RAR unpacking) 
			srr_hash: 61f7751fc2a72bfb
	"""
	def test_files(self):
		breakdance = join("..", "..", "test_files", "media", "breakdance.avi")
		try:
			(osohash, file_size) = compute_hash(breakdance)
		except EnvironmentError as ex:
			if ex.errno != ENOENT:
				raise
			url = "http://www.opensubtitles.org/addons/avi/breakdance.avi"
			msg = "Need {0} from {1}".format(breakdance, url)
			self.fail(msg)
		self.assertEqual("8e245d9679d31e12", osohash)
		self.assertEqual(12909756, file_size)
		# self.assertEqual("61f7751fc2a72bfb", compute_hash("D:\dummy.bin")[0])

	def test_exceptions(self):
		self.assertRaises(TypeError, compute_hash, None)
		self.assertRaises(IOError, compute_hash, "")
		stream = io.BytesIO()
		stream.close()
		self.assertRaises(ValueError, compute_hash, stream)

	def test_rars(self):
		rar_file = join("..", "..", "test_files",
						"store_split_folder_old_srrsfv_windows",
						"winrar2.80.rar")
		self.assertRaises(ValueError, osohash_from, rar_file)
