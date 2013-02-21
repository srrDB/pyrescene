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
import io

from rescene.rarstream import RarStream, FakeFile
from rescene.rar import ArchiveNotFoundError

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestRarStream(unittest.TestCase):
	"""For testing the RarStream class."""

	path = os.path.join(os.pardir, os.pardir, "test_files")
	folder = "store_split_folder_old_srrsfv_windows"
	
	def test_folder_multiple(self):	
		# with path and multiple files in folder / split volumes
		rs = RarStream(os.path.join(self.path, self.folder, 
		                            "store_split_folder.rar"), 
		                            "txt/users_manual4.00.txt")
		with open(os.path.join(self.path, "txt", "users_manual4.00.txt"),
				  "rb") as txt_file:
			# + other tests to increase code coverage
			self.assertEqual(rs.read(), txt_file.read())
			self.assertEqual(rs.tell(), txt_file.tell())
			self.assertEqual(rs.length(), txt_file.tell())
			self.assertEqual(rs.readable(), True)
			self.assertEqual(rs.seekable(), True)
			self.assertEqual(rs.read(), "")
			self.assertRaises(EOFError, rs.read, 999999)
			rs.seek(0, os.SEEK_SET)
			rs.read(2)
			rs.seek(0, os.SEEK_END)
			self.assertRaises(IndexError, rs.seek, -1)
		self.assertEquals(rs.list_files(), 
						  ["txt\\empty_file.txt", 
						   "txt\\little_file.txt", 
						   "txt\\users_manual4.00.txt"])
		self.assertRaises(NotImplementedError, rs.readinto, "")
		
	def test_file(self):
		""" Tests if the file in the rar archive is the same as the
			extracted version. """
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		txt_file = os.path.join(self.path, "txt", "little_file.txt")
		rs = RarStream(rar_file)
		with open(txt_file) as tfile:
			self.assertEqual(rs.read(), tfile.read())
			
		rar_file = os.path.join(self.path, 
				"store_split_folder_old_srrsfv_windows", "winrar2.80.rar")
		txt_file = os.path.join(self.path, "txt", "unicode_dos.nfo")
		rs = RarStream(rar_file, "unicode_dos.nfo") # 3.316 bytes
		with open(txt_file, "rb") as tfile:
			rs.seek(3316)
			self.assertEqual(rs.seek(6316), rs.tell())
			rs.seek(3312)
			tfile.seek(3336, os.SEEK_SET)
			tfile.seek(6336, os.SEEK_SET)
			rs.read(4)
			rs.seek(0)
			tfile.seek(0)
			self.assertEqual(rs.read(), tfile.read())
			tfile.seek(-20, os.SEEK_END)
			self.assertEqual(rs.seek(-20, os.SEEK_END), tfile.tell())
			self.assertEqual(rs.read(), tfile.read())
		rs.close()
		self.assertEqual(rs.closed, True, "Stream not closed")
	
		txt_file = os.path.join(self.path, "txt", "unicode_mac.nfo")
		rs = RarStream(rar_file, "unicode_mac.nfo")
		with open(txt_file) as tfile:
			tfile.seek(3000)
			tfile.read()
			tfile.seek(333)
			rs.seek(333)
			self.assertEqual(rs.read(), tfile.read())
			
	def test_read_nothing(self):
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		rs = RarStream(rar_file)
		self.assertEquals("", rs.read(0))
		
	def test_not_first_rar(self):
		# AttributeError: You must start with the first volume from a RAR set
		self.assertRaises(AttributeError, RarStream, os.path.join(self.path, 
						  "store_split_folder_old_srrsfv_windows",
						  "store_split_folder.r00"))
	
	def test_error_srr_file(self):
		# AttributeError: The extension must be one form a rar archive.
		self.assertRaises(AttributeError, RarStream, os.path.join(self.path, 
						  "store_split_folder_old_srrsfv_windows",
						  "store_split_folder.srr"))
		
	def test_error_unknown_file(self):
		rar_file = os.path.join(self.path, "store_little", "store_little.rar")
		self.assertRaises(AttributeError, RarStream, rar_file, "file.txt")
	
	def test_error_archive_not_found(self):
		# ArchiveNotFoundError: [Errno 2] No such file or directory: '/'
		self.assertRaises(ArchiveNotFoundError, RarStream, "/")
		#TODO: test in Linux
		
	def test_error_compressed_rar(self):
		compr = os.path.join(os.pardir, os.pardir, "test_files", 
		                     "best_little", "best_little.rar")
		# AttributeError: Compressed RARs are not supported
		self.assertRaises(AttributeError, RarStream, compr)
		RarStream(compr, compressed=True)
		
	def test__check_function(self):
		# http://superuser.com/questions/325643/how-do-i-create-a-null-rar/
		small_rar = io.BytesIO()
		small_rar.write("Rar!\x1a\x07\x00")
		small_rar.write("\xF1\xFB\x73\x01\x00\x0D\x00\x00\x00\x00\x00\x00\x00")
		small_rar.seek(0)
		small_rar.name = "name"
		# AttributeError: Archive without stored files.
		self.assertRaises(AttributeError, RarStream, small_rar)

class TestFakeFile(unittest.TestCase):
	"""For testing the FakeFile class."""
	
	def test_error(self):
		ff = FakeFile(100)
		self.assertRaises(IndexError, ff.seek, 101)
		self.assertRaises(IndexError, ff.seek, -1, os.SEEK_SET)
		
	def test_fake_file(self):
		ff = FakeFile(100)
		self.assertEqual(ff.length(), 100)
		self.assertEqual(ff.tell(), 0, "Does not start at zero.")
		self.assertTrue(ff.readable(), "The file isn't readable.")
		self.assertTrue(ff.seekable(), "The file isn't seekable.")
		data = ff.read(50)
		self.assertEqual(ff.tell(), 50)
		self.assertEqual(data, "\x00" * 50)
		data = ff.read(51)
		self.assertEqual(ff.tell(), 100)
		self.assertEqual(data, "\x00" * 50)
		ff.seek(-5, os.SEEK_END)
		self.assertEqual(ff.tell(), 95)
		data = ff.read()
		self.assertEqual(len(data), 5)
		ff.seek(0)
		ff.seek(33, os.SEEK_CUR)
		self.assertEqual(len(ff.read()), 67)
		ff.read(0)