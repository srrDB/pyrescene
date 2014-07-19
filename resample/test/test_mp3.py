#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2014 pyReScene
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

import io
import unittest

from resample import mp3

class TestDoubleId3v2(unittest.TestCase):
	"""Test for bad data in (angelmoon)-hes_all_i_want_cd_pg2k-bmi
	VLC and mpc-hc can only play it after removing the crap of first ID3 tag 
	fpcalc fails on it too, but succeeds when bad tag is removed."""
	def test_parse(self):
		mp3stream = io.BytesIO()
		
		# bad ID3 tag (10 bytes)
		mp3stream.write(b"ID3")
		mp3stream.write(b"N" * 7) # nfo data or other crap in file
		
		# good ID3 tag (20 bytes)
		mp3stream.write(b"ID3")
		mp3stream.write(b"\x03\x00\x00") # version info and flags
		mp3stream.write(b"\x00\x00\x00\x0A") # size
		mp3stream.write(b"I" * 10) # data
		
		# mp3 stuff (8 bytes)
		mp3stream.write(b"\xFF\xE7") # mp3 frame marker (11 bits)
		mp3stream.write(b"M" * 8)
		
		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=mp3stream)
		generator = mr.read()
		id3 = next(generator)
		self.assertEqual(0, id3.start_pos)
		self.assertEqual(10 + 20, id3.size)
		
		mp3data = next(generator)
		self.assertEqual(30, mp3data.start_pos)
		self.assertEqual(10, mp3data.size)
		
		self.assertRaises(StopIteration, next, generator)
		
if __name__ == "__main__":
	unittest.main()