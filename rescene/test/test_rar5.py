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

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestRar5Reader(unittest.TestCase):
	""" For testing Rar5Reader.
		Rar5Reader parses the incoming file or stream. """

	path = os.path.join(os.pardir, os.pardir, "test_files")
	folder = "rar5"

	def test_read(self):
		rfile = os.path.join(self.path, self.folder, "txt.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			print(r.explain())
		
	def test_read_none(self):
		""" We expect None back if we read one time to much. """
		stream = io.BytesIO()
		stream.name = "name to imitate real file"
# 		stream.write(RAR_MARKER_BLOCK)
# 		stream.write(TestRarBlocks.FIRST_VOLUME)
		stream.seek(0)

class TestRar5Vint(unittest.TestCase):
	"""Tests the rar 5 vint"""
	def test_read_vint(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x81")
		stream.write(b"\x01")
		stream.seek(0)
		number = read_vint(stream)
		self.assertEquals(number, 16384 + 129, "128 bit is in the next byte")

	def test_read_vint_single_byte_all_bits(self):
		stream = io.BytesIO()
		stream.write(b"\x7F")  # first bit not set
		stream.seek(0)
		number = read_vint(stream)
		self.assertEquals(number, 255 - 128, "max value single vint byte")

	def test_read_vint_zeros(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x82")
		stream.write(b"\x00")  # allocated bits without influence
		stream.seek(0)
		number = read_vint(stream)
		self.assertEquals(number, 257, "256 bit is in the next byte")
		
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
		self.assertEquals(tnumber, number, "encoding to vint and back failed")
