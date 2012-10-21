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
import sys

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behaviour
	range = xrange #@ReservedAssignment
	str = unicode #TODO: hmmm @ReservedAssignment
	# py2.6 has broken bytes()
	def bytes(foo, enc): #@ReservedAssignment
		return str(foo) # XXX: not used?
else:
	unicode = str #@ReservedAssignment

from rescene.utility import (SfvEntry, parse_sfv_file, same_sfv, is_rar, 
							next_archive, is_good_srr, first_rars)

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestSfv(unittest.TestCase):
	"""For testing all objects and functions defined in this file."""
	unsorted_list = [SfvEntry("test.r02","00000000"),
					 SfvEntry("test.rar","00000000"),
					 SfvEntry("test.r00","00000000"),
					 SfvEntry("test.r01","00000000"),
					 SfvEntry("test.001","00000000"),
					 SfvEntry("test.002","00000000"),
					 SfvEntry("a.part02.rar","00000000"),
					 SfvEntry("a.part01.rar","00000000"),]

	sorted_list = [SfvEntry("a.part01.rar","00000000"),
				   SfvEntry("a.part02.rar","00000000"),
				   SfvEntry("test.001","00000000"),
				   SfvEntry("test.002","00000000"),
				   SfvEntry("test.rar","00000000"),
				   SfvEntry("test.r00","00000000"),
				   SfvEntry("test.r01","00000000"),
				   SfvEntry("test.r02","00000000"),]
	
	def test_sort(self):
		correct = [e.file_name for e in self.sorted_list]
		# sorted(): yields sorted list
		test = [e.file_name for e in sorted(self.unsorted_list)]
		self.assertEquals(correct, test, "Sorting does not work.")
		# sort(): in-place sort
		self.unsorted_list.sort()
		test = [e.file_name for e in self.unsorted_list]
		self.assertEquals(correct, test, "Sorting does not work.")
		
	def test_sort_bug(self):
		# multiple .rar files from different sets
		slist = [SfvEntry("group-begin.rar", "00000000"),
				SfvEntry("group-begin.r00", "00000000"),
				SfvEntry("group-other.rar", "00000000"),
				SfvEntry("group-other.r00", "00000000"),]
		self.assertEquals(slist, sorted(slist), "Sorting does not work.")
		
	def test_sfv_entry(self):
		self.assertRaises(ValueError, SfvEntry, "file_name", "11aa33XX")
		self.assertRaises(ValueError, SfvEntry, "file_name", "11aa11aa  ")
		
	def test_parse_sfv(self):
		output = io.StringIO()
		output.write(str("  ; sfv raped by teh skilled thugs\n"
		"test.r00 aabb0099  \n"
		"test.r01	  AABBCCDD\n"
		"test.rar	AABBCCDD\n" # \t only
		"test.rar\tAABBDD\n"
		"test name with spaces.rar AABBCCDD\n"
		"test name with more spaces.rar	   AABBCCDD\n"
		"test name with ;.rar AABBCCDD\n"
		"  \n"
		"----------------------------------\n"))
		output.write(str("illegal.rar AABBCCDD ; comment\n"))
		
		(entries, comments, errors) = parse_sfv_file(output)
		print([str(e) for e in entries])
		print(comments)
		print(errors)
		self.assertTrue(len(entries) == 7)
		self.assertTrue(len(comments) == 1)
		self.assertTrue(len(errors) == 2)
		
		# test __str__ method
		self.assertEqual(str(entries[0]), 'test.r00 aabb0099')
		
		# just supply the data
		output.seek(0)
		(entries, comments, errors) = parse_sfv_file(output.read())
		self.assertTrue(len(entries) == 7)
		self.assertTrue(len(comments) == 1)
		self.assertTrue(len(errors) == 2)
	
	def test_parse_sfv_file(self):
		sfv = os.path.join(os.pardir, os.pardir, "test_files", 
			"store_split_folder_old_srrsfv_windows", "store_split_folder.sfv")
		(entries, comments, _errors) = parse_sfv_file(sfv)
		self.assertTrue(len(entries) == 3)
		self.assertTrue(len(comments) == 9)

	def test_sfv_diff(self):
		txtdir = os.path.join(os.pardir, os.pardir, "test_files", "txt")
		one = os.path.join(txtdir, "checksum.sfv") # Unicode content
		two = os.path.join(txtdir, "checksum_copy.sfv")
		
		self.assertTrue(same_sfv(one, two), "SFV files not the same.")
		one, _, _ = parse_sfv_file(os.path.join(txtdir, "checksum.sfv"))
		two, _, _ = parse_sfv_file(os.path.join(txtdir, "checksum_copy.sfv"))
		one.append(SfvEntry("name"))
		self.assertFalse(one == two)
		
class TestUtility(unittest.TestCase):
	def test_is_rar_file(self):
		self.assertTrue(is_rar(".rar"))
		self.assertTrue(is_rar("test.r00"))
		self.assertTrue(is_rar("test.s00"))
		self.assertTrue(is_rar("test.000"))
		self.assertTrue(is_rar("test.999"))
		self.assertTrue(is_rar("test.v99"))
		self.assertTrue(is_rar("test.part1.rar"))
		self.assertFalse(is_rar("test.w66"))
		self.assertFalse(is_rar("testrar"))

	def test_next_rar(self):
		self.assertEqual(next_archive("a.rar"), "a.r00")
		self.assertEqual(next_archive(".r00"), ".r01")
		self.assertEqual(next_archive("a.r09"), "a.r10")
		self.assertEqual(next_archive("a.r99"), "a.s00")
		self.assertEqual(next_archive(".part1.rar"), ".part2.rar")
		self.assertEqual(next_archive(".part09.rar"), ".part10.rar")
		self.assertRaises(AttributeError, next_archive, "comic.cbr")
		self.assertRaises(AttributeError, next_archive, "comic.cbz")
		
	def test_is_good(self):
		self.assertTrue(is_good_srr("good- #@&$§£~(){}[]!çéè"))
		for char in """\:*?"<>|""":
			self.assertFalse(is_good_srr("not" + char + "good"))
			
	def test_first_rars(self):
		t = ["name.r00", "name.r01", "name.rar"]
		self.assertEqual(["name.rar"], first_rars(t))
		t = ["test.part03.rar", "test.part20.rar", "test.part01.rar"]
		self.assertEqual(["test.part01.rar"], first_rars(t))
		t = ["test.part003.rar", "test.part020.rar", "test.part001.rar"]
		self.assertEqual(["test.part001.rar"], first_rars(t))
		t = ["test3.rar", "test20.rar", "test.part0001.rar"]
		self.assertEqual(t, first_rars(t))
		# 000 or 001 should be the first RAR
		t = ["name.000", "name.001", "name.002"]
		self.assertEqual(["name.000"], first_rars(t))
		t = ["name.001", "name.002", "name.003", "other.000", "other.001"]
		self.assertEqual(["name.001", "other.000"], first_rars(t))

	def test_diff_lists(self):
		a = """een
		twee
		
		drie"""
		b = """een
		twee
		drie
		"""
		a, b = (a,), (b,)
		
		#print diff_lists(a, b)
		
#	def test_nfo_diff(self):
#		txtdir = os.path.join(os.pardir, "test_files", "txt")
#		# _read all nfo files that start with ansi/unicode in memory
#		contents = {}
#		for file in os.listdir(txtdir):
#			if file[:4] in ("ansi",): # "unic"):
#				path = os.path.join(txtdir, file)
#				with open(path, "rt") as f:
#					contents[file] = f._read()
#
#		# all files must be equal
#		old = None
#		for k, v in contents.items():
#			if old == None:
#				old = (k, v)
#			else:
#				r = diff_lists(old[1].splitlines(), v.splitlines())
#				self.assertTrue(r)
#				print r, old[0], k
#				old = (k, v)
#				
#		self.assertFalse(diff_lists(("one",), ("one", "two")))
#				
#		
#		for i in range(len(contents)):
#			if i == len(contents) - 1:
#				break
#			r = diff_lists(contents.[i].splitlines(), 
#						   contents[i+1].splitlines())
#			print r, contents[i]