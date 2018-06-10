#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2015 pyReScene
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
# used and Python 3.2 does not support the u"" syntax.
from __future__ import unicode_literals
from __future__ import print_function

import unittest
import os
import io
import sys
import locale
import platform

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behaviour
	str2 = str
	range = xrange  # @ReservedAssignment
	str = unicode  # @ReservedAssignment
else:
	str2 = str
	unicode = str  # @ReservedAssignment

from rescene.utility import SfvEntry, parse_sfv_file, parse_sfv_data
from rescene.utility import filter_sfv_duplicates, same_sfv
from rescene.utility import is_rar, next_archive, is_good_srr, first_rars, sep
from rescene.utility import capitalized_fn
from rescene.utility import DISK_FOLDERS, RELEASE_FOLDERS 

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestSfv(unittest.TestCase):
	"""For testing all objects and functions defined in this file."""
	unsorted_list = [SfvEntry("test.r02", "00000000"),
					 SfvEntry("test.rar", "00000000"),
					 SfvEntry("test.r00", "00000000"),
					 SfvEntry("test.r01", "00000000"),
					 SfvEntry("test.001", "00000000"),
					 SfvEntry("test.002", "00000000"),
					 SfvEntry("a.part02.rar", "00000000"),
					 SfvEntry("a.part01.rar", "00000000"), ]

	sorted_list = [SfvEntry("a.part01.rar", "00000000"),
				   SfvEntry("a.part02.rar", "00000000"),
				   SfvEntry("test.001", "00000000"),
				   SfvEntry("test.002", "00000000"),
				   SfvEntry("test.rar", "00000000"),
				   SfvEntry("test.r00", "00000000"),
				   SfvEntry("test.r01", "00000000"),
				   SfvEntry("test.r02", "00000000"), ]

	def test_sort(self):
		correct = [e.file_name for e in self.sorted_list]
		# sorted(): yields sorted list
		test = [e.file_name for e in sorted(self.unsorted_list)]
		self.assertEqual(correct, test, "Sorting does not work.")
		# sort(): in-place sort
		self.unsorted_list.sort()
		test = [e.file_name for e in self.unsorted_list]
		self.assertEqual(correct, test, "Sorting does not work.")

	def test_sort_bug(self):
		# multiple .rar files from different sets
		slist = [SfvEntry("group-begin.rar", "00000000"),
				SfvEntry("group-begin.r00", "00000000"),
				SfvEntry("group-other.rar", "00000000"),
				SfvEntry("group-other.r00", "00000000"), ]
		self.assertEqual(slist, sorted(slist), "Sorting does not work.")

	def test_sfv_entry(self):
		self.assertRaises(ValueError, SfvEntry, "file_name", "11aa33XX")
		self.assertRaises(ValueError, SfvEntry, "file_name", "11aa11aa  ")

	def test_parse_sfv(self):
		output = io.BytesIO()
		output.write(b"  ; sfv raped by teh skilled thugs\n"
		b"test.r00 aabb0099  \n"
		b"test.r01	  AABBCCDD\n"
		b"test.rar	AABBCCDD\n"  # \t only
		b"test.rar\tAABBDD\n"
		b"test name with spaces.rar AABBCCDD\n"
		b"test name with more spaces.rar	   AABBCCDD\n"
		b"test name with ;.rar AABBCCDD\n"
		b"  \n"
		b"----------------------------------\n")
		output.write(b"illegal.rar AABBCCDD ; comment\n")

		(entries, comments, errors) = parse_sfv_file(output)
		self.assertTrue(len(entries) == 7)
		self.assertTrue(len(comments) == 1)
		self.assertTrue(len(errors) == 2)

		self.assertEqual(str(entries[0]), 'test.r00 aabb0099')

		# just supply the data
		output.seek(0)
		(entries, comments, errors) = parse_sfv_data(output.read())
		self.assertTrue(len(entries) == 7)
		self.assertTrue(len(comments) == 1)
		self.assertTrue(len(errors) == 2)

	def test_extra_spaces_and_tab(self):
		output = io.BytesIO()
		output.write(b"atest.rar	  AABBCCDD\n")

		(entries, comments, errors) = parse_sfv_file(output)
		self.assertTrue(len(entries) == 1)
		self.assertTrue(len(comments) == 0)
		self.assertTrue(len(errors) == 0)

		line = entries[0]
		self.assertEqual("atest.rar", line.file_name)
		self.assertEqual("AABBCCDD", line.crc32)

	def test_parse_sfv_file(self):
		sfv = os.path.join(os.pardir, os.pardir, "test_files",
			"store_split_folder_old_srrsfv_windows", "store_split_folder.sfv")
		(entries, comments, _errors) = parse_sfv_file(sfv)
		self.assertTrue(len(entries) == 3)
		self.assertTrue(len(comments) == 9)

	def test_sfv_diff(self):
		txtdir = os.path.join(os.pardir, os.pardir, "test_files", "txt")
		one = os.path.join(txtdir, "checksum.sfv")  # Unicode content
		two = os.path.join(txtdir, "checksum_copy.sfv")

		self.assertTrue(same_sfv(one, two), "SFV files not the same.")
		one, _, _ = parse_sfv_file(os.path.join(txtdir, "checksum.sfv"))
		two, _, _ = parse_sfv_file(os.path.join(txtdir, "checksum_copy.sfv"))
		one.append(SfvEntry("name"))
		self.assertFalse(one == two)

	def test_sfv_quotes(self):
		output = io.BytesIO()  # De.Gelukkige.Huisvrouw.2010.DVDRip.XviD-FloW
		output.write(b"; sfv created by SFV Checker\n"
		b";\n"
		b""""gh-flow.subs.rar" 83a20923\n"""
		b";\n"
		b"; Total 1 File(s)	Combined CRC32 Checksum: 83a20923\n"
		)
		(entries, comments, errors) = parse_sfv_file(output)
# 		print([str(e) for e in entries])
# 		print(comments)
# 		print(errors)
		self.assertTrue(len(entries) == 1)
		self.assertTrue(len(comments) == 4)
		self.assertTrue(len(errors) == 0)
		self.assertEqual("gh-flow.subs.rar", entries[0].file_name)

	def test_encoding_error(self):
		"""Should not crash parsing garbage or non-ASCII SFV file"""
		sfv = io.BytesIO(
			b"; \x80 garbage comment\n"
			b"\xFF garbage name 12345678\n"
			b"garbage CRC \xA02345678\n"
			b"--- \x9F garbage error line ---\n"
		)
		parse_sfv_file(sfv)

	def test_umlaut(self):
		output = io.BytesIO(
			b"; irgendwann_kommt_alles_zur\xfcck\n"
			b"kommt_alles_zur\xfcck-tpmf.mp3 4EE8195C\n"
			b"kommt_alles_zur\xfcck-tpmf.mp34EE8195C"
		)
		(entries, comments, errors) = parse_sfv_file(output)

		self.assertTrue(len(entries) == 1)
		self.assertEqual("kommt_alles_zurück-tpmf.mp3", entries[0].file_name)
		self.assertEqual("4EE8195C", entries[0].crc32)

		self.assertTrue(len(comments) == 1)
		self.assertEqual("; irgendwann_kommt_alles_zurück", comments[0])

		self.assertTrue(len(errors) == 1)
		self.assertEqual("kommt_alles_zurück-tpmf.mp34EE8195C", errors[0])

	def test_filter_sfv_duplicates(self):
		"""The capitals in the CRC32 may not make a difference."""
		sorted_list = [SfvEntry("a.part01.rar", "ab000000"),
		               SfvEntry("a.part01.rar", "AB000000")]
		filtered = filter_sfv_duplicates(sorted_list)

		sorted_list.remove(SfvEntry("a.part01.rar", "AB000000"))
		self.assertEqual(filtered, sorted_list, "Dupe not filtered out")

class TestUtility(unittest.TestCase):
	def test_is_rar_file(self):
		self.assertTrue(is_rar(".rar"))
		self.assertTrue(is_rar("test.r00"))
		self.assertTrue(is_rar("test.s00"))
		self.assertTrue(is_rar("test.000"))
		self.assertTrue(is_rar("test.999"))
		self.assertTrue(is_rar("test.v99"))
		self.assertTrue(is_rar("test.part1.rar"))
		# self.assertFalse(is_rar("test.w66"))  # made by rar.exe when needed
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
		self.assertEqual(next_archive("th.frag.rar.cd1.r00"),
		                 "th.frag.rar.cd1.r01")

	def test_next_rar_bug_ambiguous_name(self):
		"""Doctor.Who.The.Enemy.Of.The.World.S05E17.DVDRip.x264-PFa and
		Doctor.Who.The.Enemy.Of.The.World.S05E18.DVDRip.x264-PFa"""
		self.assertEqual(next_archive("pfa-dw.s05e18.teotw.part02.rar", True),
		                 "pfa-dw.s05e18.teotw.part02.r00")
		self.assertEqual(next_archive("pfa-dw.s05e17.teotw.part01.rar", True),
		                 "pfa-dw.s05e17.teotw.part01.r00")
		self.assertEqual(next_archive("pfa-dw.s05e17.teotw.part01.rar", False),
		                 "pfa-dw.s05e17.teotw.part02.rar")
		self.assertEqual(next_archive("pfa-dw.s05e17.teotw.part01.rar"),
		                 "pfa-dw.s05e17.teotw.part02.rar")
		self.assertEqual(next_archive("pfa-dw.s05e17.teotw.part01.r10"),
		                 "pfa-dw.s05e17.teotw.part01.r11")

	def test_is_good(self):
		self.assertTrue(is_good_srr("good- #@&$§£~(){}[]!çéè"))
		for char in """\:*?"<>|""":
			self.assertFalse(is_good_srr("not" + char + "good"))

	def test_first_rars(self):
		t = ["name.r00", "name.r01", "name.rar"]
		self.assertEqual(["name.rar"], first_rars(x for x in t))
		t = ["test.part03.rar", "test.part20.rar", "test.part01.rar"]
		self.assertEqual(["test.part01.rar"], first_rars(t))
		t = ["test.part003.rar", "test.part020.rar", "test.part001.rar"]
		self.assertEqual(["test.part001.rar"], first_rars(t))
		t = ["test3.rar", "test20.rar", "test.part0001.rar", "9.rar"]
		self.assertEqual(t, first_rars(x for x in t))
		# 000 or 001 should be the first RAR
		t = ["name.000", "name.001", "name.002"]
		self.assertEqual(["name.000"], first_rars(x for x in t))
		t = ["name.001", "name.002", "name.003", "other.000", "other.001"]
		self.assertEqual(["name.001", "other.000"], first_rars(t))
		t = ["name.003", "name.004", "name.007"]
		self.assertEqual([], first_rars(t))
		t = ["part1.rar", "part2.rar"]
		self.assertEqual([], first_rars(t))  # TODO: this is ok?

	def test_first_rars_bug(self):
		t = ["name.part2.r00", "name.part2.r01", "name.part2.rar"]
		self.assertEqual(["name.part2.rar"], first_rars(x for x in t))
		t = ["name.part2.r00", "name.part2.r01", "name.part2.r02"]
		self.assertEqual([], first_rars(t))
		self.assertEqual(["name.part4.rar"], first_rars(["name.part4.rar"]))
		t = ["name.part01.r00", "name.part01.r01", "name.part01.r02"]
		self.assertEqual([], first_rars(t))
		t = ["name.part01.rar", "name.part01.r00", "name.part01.r01"]
		self.assertEqual(["name.part01.rar"], first_rars(t))
		t = ["name.part001.rar"]
		self.assertEqual(["name.part001.rar"], first_rars(x for x in t))
		t = ["name.part2.rar", "name.part22.rar", "name.part7.rar"]
		self.assertEqual([], first_rars(t))

	def test_diff_lists(self):
		a = """een
		twee
		
		drie"""
		b = """een
		twee
		drie
		"""
		a, b = (a,), (b,)

		# print(diff_lists(a, b))

# 	def test_nfo_diff(self):
# 		txtdir = os.path.join(os.pardir, "test_files", "txt")
# 		# _read all nfo files that start with ansi/unicode in memory
# 		contents = {}
# 		for file in os.listdir(txtdir):
# 			if file.startswith(("ansi",)): # "unic")):
# 				path = os.path.join(txtdir, file)
# 				with open(path, "rt") as f:
# 					contents[file] = f._read()
#
# 		# all files must be equal
# 		old = None
# 		for k, v in contents.items():
# 			if old == None:
# 				old = (k, v)
# 			else:
# 				r = diff_lists(old[1].splitlines(), v.splitlines())
# 				self.assertTrue(r)
# 				print(r, old[0], k)
# 				old = (k, v)
#
# 		self.assertFalse(diff_lists(("one",), ("one", "two")))
#
#
# 		for i in range(len(contents)):
# 			if i == len(contents) - 1:
# 				break
# 			r = diff_lists(contents.[i].splitlines(),
# 						   contents[i+1].splitlines())
# 			print(r, contents[i])

	def test_sep(self):
		try:
			# 3: Locale must be None, a string, or an iterable of two strings
			en = str2("English")  # 2: bytes, 3: unicode string
			nl = str2("Dutch_Belgium.1252")
			self.assertEqual(sep(1000000, en), "1,000,000")
			if int(platform.win32_ver()[0]) >= 8:
				# \xa0 on Windows 8 (non-breaking space)
				self.assertEqual(sep(1000000, nl), "1\xa0000\xa0000")
			else:
				# Windows 7 and lower
				self.assertEqual(sep(1000000, nl), "1.000.000")
		except locale.Error as err:
			fmt = '"Dutch_Belgium.1252" and "English" locales: {0}'
			# Python 2.6 does not have the skipTest() method
			self.skipTest(fmt.format(err))  # 2.6 crash expected

	def test_grab_file_names_capitals_on_disk(self):
		tdir = os.path.join(os.pardir, os.pardir, "test_files", "hash_capitals")
		ofile = "Parlamentet.S06E02.SWEDiSH-SQC_alllower.srr"
		orig = os.path.join(tdir, ofile)
		upper = os.path.join(tdir, ofile.upper())
		lower = os.path.join(tdir, ofile.lower())

		(a, b) = capitalized_fn(orig)
		c = os.path.basename(a)
		d = os.path.basename(b)
		(e, f) = capitalized_fn(upper)
		g = os.path.basename(e)
		h = os.path.basename(f)
		(i, j) = capitalized_fn(lower)
		k = os.path.basename(i)
		l = os.path.basename(j)

		# first element must match with what is on disk
		self.assertEqual(c, ofile, "not exact")
		self.assertEqual(g, ofile, "not exact")
		self.assertEqual(k, ofile, "not exact")

		# second element tries to use the input with capitals
		self.assertEqual(d, ofile, "not with capitals")
		self.assertEqual(h, ofile.upper(), "when in doubt, use input")
		self.assertEqual(l, ofile, "use capitals from input when lc file name")

		# same without path prepended
		cwd = os.getcwd()
		try:
			os.chdir(tdir)
			ofile = "Parlamentet.S06E02.SWEDiSH-SQC_alllower.srr"
			orig = ofile
			upper = ofile.upper()
			lower = ofile.lower()

			(a, b) = capitalized_fn(orig)
			c = os.path.basename(a)
			d = os.path.basename(b)
			(e, f) = capitalized_fn(upper)
			g = os.path.basename(e)
			h = os.path.basename(f)
			(i, j) = capitalized_fn(lower)
			k = os.path.basename(i)
			l = os.path.basename(j)

			# first element must match with what is on disk
			self.assertEqual(c, ofile, "not exact")
			self.assertEqual(g, ofile, "not exact")
			self.assertEqual(k, ofile, "not exact")

			# second element tries to use the input with capitals
			self.assertEqual(d, ofile, "not with capitals")
			self.assertEqual(h, ofile.upper(), "when in doubt, use input")
			self.assertEqual(l, ofile, "use capitals from input when lc file name")
		finally:
			os.chdir(cwd)

	def test_grab_file_names_all_lower_on_disk(self):
		tdir = os.path.join(os.pardir, os.pardir, "test_files", "txt")
		ofile = "empty_file.txt"
		orig = os.path.join(tdir, ofile)
		upper = os.path.join(tdir, ofile.upper())

		(a, b) = capitalized_fn(orig)
		c = os.path.basename(a)
		d = os.path.basename(b)
		(e, f) = capitalized_fn(upper)
		g = os.path.basename(e)
		h = os.path.basename(f)

		self.assertEqual(c, ofile, "not exact")
		self.assertEqual(g, ofile, "not exact")

		self.assertEqual(d, ofile, "not with capitals")
		self.assertEqual(h, ofile.upper(), "not with capitals")

		# same without path prepended
		cwd = os.getcwd()
		try:
			os.chdir(tdir)
			ofile = "empty_file.txt"
			orig = ofile
			upper = ofile.upper()

			(a, b) = capitalized_fn(orig)
			c = os.path.basename(a)
			d = os.path.basename(b)
			(e, f) = capitalized_fn(upper)
			g = os.path.basename(e)
			h = os.path.basename(f)

			self.assertEqual(c, ofile, "not exact")
			self.assertEqual(g, ofile, "not exact")

			self.assertEqual(d, ofile, "not with capitals")
			self.assertEqual(h, ofile.upper(), "not with capitals")
		finally:
			os.chdir(cwd)

class TestReleaseRegex(unittest.TestCase):
	def test_disk_folders(self):
		self.assertTrue(DISK_FOLDERS.match("cd1"))
		self.assertTrue(DISK_FOLDERS.match("cd.1"))
		self.assertTrue(DISK_FOLDERS.match("cd_1"))
		self.assertTrue(DISK_FOLDERS.match("Disk1"))
		self.assertTrue(DISK_FOLDERS.match("Disc1"))
		self.assertTrue(DISK_FOLDERS.match("DVD.11"))
		self.assertTrue(DISK_FOLDERS.match("PART1"))
		self.assertTrue(DISK_FOLDERS.match("Disc1_A.Long.disk_title"))
		self.assertTrue(DISK_FOLDERS.match("Disc1.Leon"))
		self.assertTrue(DISK_FOLDERS.match("Disc1_Leon"))
		self.assertTrue(DISK_FOLDERS.match("Disc1-Leon"))
		self.assertTrue(DISK_FOLDERS.match("CD1-Dont_Cross_Me"))

		# the - could give problems with actual releases
		self.assertFalse(DISK_FOLDERS.match("Disc1_A.Long-disk_title"))
		self.assertFalse(DISK_FOLDERS.match("DVD2oneX2.v2.1.2.MacOSX.UB-Lz0"))
		
	def test_release_folders(self):
		self.assertTrue(RELEASE_FOLDERS.match("Disc_1"))
		self.assertTrue(RELEASE_FOLDERS.match("Sample"))
		self.assertTrue(RELEASE_FOLDERS.match("Samples"))
		self.assertTrue(RELEASE_FOLDERS.match("VobSample"))
		self.assertTrue(RELEASE_FOLDERS.match("VobSamples"))
		self.assertTrue(RELEASE_FOLDERS.match("Cover"))
		self.assertTrue(RELEASE_FOLDERS.match("Covers"))
		self.assertTrue(RELEASE_FOLDERS.match("PROOF"))
		self.assertTrue(RELEASE_FOLDERS.match("Proofs"))
		self.assertTrue(RELEASE_FOLDERS.match("Subs"))
		self.assertTrue(RELEASE_FOLDERS.match("Subpack"))
		self.assertTrue(RELEASE_FOLDERS.match("vobsubs"))
		self.assertTrue(RELEASE_FOLDERS.match("vobsub"))
		self.assertFalse(RELEASE_FOLDERS.match("Bluray1"))
		self.assertFalse(RELEASE_FOLDERS.match("PROOOF"))