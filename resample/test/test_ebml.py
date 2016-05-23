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

from resample.ebml import (GetUIntLength, GetEbmlElementID, GetEbmlUIntStream,
                           GetEbmlUInt)

class TestHelperFunctions(unittest.TestCase):
	def test_get_uint_length(self):
		self.assertEqual(1, GetUIntLength(0x80))  # 1000 0000
		self.assertEqual(1, GetUIntLength(0xFF))  # 1111 1111
		self.assertEqual(2, GetUIntLength(0x42))  # 0100 0000 ...
		self.assertEqual(3, GetUIntLength(0x21))  # 0010 0000 ... ...
		self.assertEqual(4, GetUIntLength(0x18))  # 0001 0000 ... ... ...
		self.assertEqual(5, GetUIntLength(0x8))
		self.assertEqual(5, GetUIntLength(0x9))
		self.assertEqual(6, GetUIntLength(0x5))
		self.assertEqual(6, GetUIntLength(0x4))
		self.assertEqual(7, GetUIntLength(0x2))
		self.assertEqual(8, GetUIntLength(0x1))
		self.assertEqual(4, GetUIntLength(26))

	def test_get_ebml_element_id(self):
		stream = io.BytesIO()
		stream.write(b"\x20")
		stream.write(b"\xBA\xBE\x00\x00")
		stream.seek(0, os.SEEK_SET)
		self.assertEqual(b"\x20\xBA\xBE", GetEbmlElementID(stream))
		stream.write(b"\xAA")
		stream.seek(0, os.SEEK_SET)
		self.assertEqual(b"\x20\xBA\xBE", GetEbmlElementID(stream))
		stream.seek(0, os.SEEK_SET)
		stream.write(b"\x1F\xBA\xBE\xAA\x00\x11\x11\x11\x11")
		stream.seek(0, os.SEEK_SET)
		self.assertEqual(b"\x1F\xBA\xBE\xAA", GetEbmlElementID(stream))

	def test_get_ebml_uint(self):
		buff = b"\xBA\xBE\x32\xC6\x54\xBA\xBE"
		self.assertEqual(1230420, GetEbmlUInt(buff, 2, 3))

	def test_get_ebml_uint_stream(self):
		stream = io.BytesIO()
		stream.write(b"\x32")  # 3 bytes
		stream.write(b"\xC6\x54")
		stream.seek(0, os.SEEK_SET)
		self.assertEqual((1230420, 3), GetEbmlUIntStream(stream))

if __name__ == "__main__":
	unittest.main()
