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

from __future__ import (with_statement, unicode_literals, print_function,
	absolute_import)

import unittest
import shutil 
import pprint
from filecmp import cmp
from os.path import join
from tempfile import mkdtemp
import sys
import struct

import rescene
from rescene.main import *
from rescene.main import _handle_rar, _flag_check_srr, _auto_locate_renamed
from rescene.rar import ArchiveNotFoundError
from rescene import rar

try:  # Python < 3
	from StringIO import StringIO  # Supports writing non-Unicode strings
except ImportError:  # Python 3
	from io import StringIO

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestInit(unittest.TestCase):
	def setUp(self):
		self.o = Observer()
		subscribe(self.o)
		
		# directory to place temporarily files: users home dir
		self.test_dir = os.path.expanduser('~')
		
		# some supplied files to work with
		self.files_dir = os.path.join(os.pardir, os.pardir, "test_files")
		
		self.little = os.path.join(self.files_dir, "store_little")
		self.newrr = os.path.join(self.files_dir, 
		                          "store_rr_solid_auth_unicode_new") 
		self.oldfolder = os.path.join(self.files_dir, 
		                              "store_split_folder_old_srrsfv_windows") 
		self.utfunix = os.path.join(self.files_dir, "store_utf8_comment")
		self.compression = os.path.join(self.files_dir, "best_little")
		self.txt = os.path.join(self.files_dir, "txt")
		
	def _print_events(self):
		for event in self.o.events:
			print(event.code),
			print(event.message)
	
	def _clear_events(self):
		self.o.events = []

class TmpDirSetup(TestInit):
	cleanup = True # do self.cleanup = False to prevent cleanup
		
	def setUp(self):
		super(TmpDirSetup, self).setUp()
		# temp dir to create files for tests
		self.tdir = mkdtemp("-pyReScene", "tmp.", self.test_dir)
		assert self.o.events == []
		
	def tearDown(self):
		"""Delete the temporarily directory and its files."""
		super(TmpDirSetup, self).tearDown()
		if self.cleanup:
			shutil.rmtree(self.tdir)
		
class TestExtract(TmpDirSetup):
	"""Test the extraction of additional files added to a srr file."""
	def test_extract_srr_path(self):
		path = os.path.join(os.pardir, os.pardir, "test_files", "store_little")
		srr_file = os.path.join(path, "store_little_srrfile_with_path.srr")
		efile = os.path.join(self.tdir, "store_little", "store_little.srr")
		
		extract_files(srr_file, self.tdir)
		self.assertEqual(self.o.last_event().message[:10], "Recreating")
		self.assertEqual(self.o.last_event().code, MsgCode.MSG)
		extract_files(srr_file, self.tdir)
		self.assertEqual(self.o.last_event().code, MsgCode.NO_OVERWRITE)
		self.assertEqual(self.o.last_event().message[:15], 
		                 "Overwrite operation aborted"[:15])
		
		# clean up but keep created directory -> os error expected
		try:
			os.remove(efile)
		except: pass
		extract_files(srr_file, self.tdir)
		self.assertEqual(self.o.last_event().code, MsgCode.OS_ERROR)
		self.assertTrue(os.path.isfile(efile))

	def test_extract_srr_path_backslash(self):
		"""Stored paths never use a \ for a file stored in a srr file, but
		it doesn't cause problems with ReScene .NET"""
		path = os.path.join(os.pardir, os.pardir, "test_files", "store_little")
		efile = os.path.join(self.tdir, "store_little", "store_little.srr")
		srr_file = os.path.join(path, 
		                        "store_little_srrfile_with_path_backslash.srr")
		
		extract_files(srr_file, self.tdir)
		self.assertTrue(os.path.isfile(efile),
			"{0!r} should be a file".format(efile))
		self.assertEqual(self.o.last_event().code, MsgCode.MSG)
		self.assertEqual(self.o.last_event().message[:10], "Recreating")
		
		extract_files(srr_file, self.tdir)
		self.assertEqual(self.o.last_event().code, MsgCode.NO_OVERWRITE)
		self.assertEqual(self.o.last_event().message[:15], 
		                 "Overwrite operation aborted"[:15])
	
	def test_extract_srr_utf8(self):
		utf8 = "Κείμενο στην ελληνική γλώσσα.txt"
		temputf = os.path.join(self.tdir, utf8)
		origutf = os.path.join(self.txt, utf8)
		srr_file = os.path.join(self.utfunix, "utf8_filename_added.srr")

		extract_files(srr_file, self.tdir)
		#self.assertEqual(self.o.last_event().message[:10], "Recreating")
		self.assertTrue(os.path.isfile(temputf))
		self.assertTrue(cmp(temputf, origutf), "Extracted file is bad.")
		os.remove(temputf)
		
		extract_files(srr_file, self.tdir, packed_name=utf8)
		self.assertTrue(cmp(temputf, origutf), "Extracted file is bad.")
		self.assertTrue(os.path.isfile(temputf))

	def test_not_existing_name(self):
		"""Do not extract anything when the provided file name is not
		included in the srr file."""
		path = os.path.join(os.pardir, os.pardir, "test_files", "store_little")
		srr_file = os.path.join(path, "store_little_srrfile_with_path.srr")
		extract_files(srr_file, "", packed_name="fake_file")
		self.assertEqual(self.o.last_event().code, MsgCode.NO_EXTRACTION)

class TestAddRemoveRenameError(TestInit):
	"""Tests the errors of adding and removing stored files."""	
	def test_error_unknown_srr_file(self):
		self.assertRaises(ArchiveNotFoundError, add_stored_files, None, ())
		self.assertRaises(ArchiveNotFoundError,
		                  remove_stored_files, None, None)
		self.assertRaises(ArchiveNotFoundError,
		                  rename_stored_file, None, "dummy", "dummy")
	
	def test_error_rar_for_srr(self):
		rar = os.path.join(self.little, "store_little.rar")
		self.assertRaises(NotSrrFile, add_stored_files, rar, ())
		self.assertRaises(NotSrrFile, remove_stored_files, rar, None)
		self.assertRaises(NotSrrFile, rename_stored_file, rar, "dummy", "dummy")

	def test_error_dupe(self):
		srrp = os.path.join(self.little, "store_little_srrfile_with_path.srr")
		self.assertRaises(DupeFileName, add_stored_files,
		                  srrp, ["store_little/store_little.srr"])
		
	def test_file_not_found(self):
		srr = os.path.join(self.little, "store_little.srr")
		self.assertRaises(FileNotFound, rename_stored_file, srr,
		                  "old name", "new name")

class TestAddRemoveFiles(TmpDirSetup):		
	def test_add_remove(self):
		# create srr file to add files too
		srrorig = os.path.join(self.little, "store_little.srr")
		srr = os.path.join(self.tdir, os.path.basename(srrorig))
		_copy(srrorig, self.tdir)
		
		# NO PATHS
		# add all text files of the txt directory to the SRR file
		files = os.listdir(os.path.join(self.files_dir, "txt"))
		
		add_stored_files(srr, files)
		self.assertEqual(self.o.last_event().code, MsgCode.NO_FILES)
		
		add_stored_files(srr, files, os.path.join(self.files_dir, "txt"))
		
		files_srr = info(srr)["stored_files"]
		s = [v.file_name for _, v in files_srr.items()]
		files.sort() # don't create folders in the directory for this test
		s.sort()
		self.assertEqual(files, s, "File list not equal.")
		
		# Remove all added files again: equal with original file
		self.o.events = []
		remove_stored_files(srr, s) # TODO: better tests!
		self.assertTrue(cmp(srr, srrorig), "Files not equivalent.")
		self.assertEqual(len(s), len(self.o.events), "Deletion events not "
						 "equal to the number of files to be deleted.")
		self.assertEqual(MsgCode.DEL_STORED_FILE, self.o.last_event().code)
		
		# WITH PATHS
		root = os.path.join(self.files_dir, "txt")
		files = list(os.path.join(root, x) for x in os.listdir(root))
		self.o.events = []
		add_stored_files(srr, files, self.files_dir, True)
		
		files = sorted(os.path.relpath(x, 
					self.files_dir).replace(os.sep, "/") for x in files)  
		files_srr = info(srr)["stored_files"]
		s = [v.file_name for _, v in files_srr.items()]
		s.sort()
		# self.o.print_events()
		self.assertEqual(MsgCode.STORING, self.o.last_event().code)
		self.assertEqual(files, s, "File list not equal.")
		
		# paths must be POSIX for srr
		rr = RarReader(srr)
		for block in rr.read_all():
			if block.rawtype == BlockType.SrrStoredFile:
				self.assertRaises(ValueError, block.file_name.index, "\\")
		
		# Remove all added files again: equal with original file
		self.o.events = []
		remove_stored_files(srr, files)
		self.assertTrue(cmp(srr, srr), "Files not equivalent.")
		self.assertEqual(len(s), len(self.o.events), "Deletion events not "
						 "equal to the number of files to be deleted.")
		self.assertEqual(MsgCode.DEL_STORED_FILE, self.o.last_event().code)

class TestRename(TmpDirSetup):		
	def test_rename(self):
		# create srr file to test rename on
		orig = os.path.join(self.little, "store_little_srrfile_with_path.srr")
		srr = os.path.join(self.tdir, os.path.basename(orig))
		_copy(orig, self.tdir)
#		fname = RarReader(srr).list_files()[0]
#		print(fname)
		
		rename_stored_file(srr, "store_little/store_little.srr", 
		                   "store_little/store_little_renamed.srr")
		RarReader(srr).read_all()
		rename_stored_file(srr, "store_little/store_little_renamed.srr",
		                   "store_little/store_little.srr")
		RarReader(srr).read_all()
		self.assertTrue(cmp(srr, orig), "Files not equivalent.")
#		rename_stored_file(srr, "store_little.srr",
#						   "store_little_renamed.srr")
		
class TestHash(TestInit):
	def test_hash_capitals(self):
		"""To compare with the PHP hash implementation"""
		d = join(os.pardir, os.pardir, "test_files", "hash_capitals")
		lower = join(d, "Parlamentet.S06E02.SWEDiSH-SQC_alllower.srr")
		capitals = join(d, "Parlamentet.S06E02.SWEDiSH-SQC_capitals.srr")
		
		hl = content_hash(lower)
		hc = content_hash(capitals)
		print(hl) # 1baad396af00591a16cd9691f2ff11ccdde1dcb1
		self.assertEqual(hl, hc)
	
class TestDisplayInfo(TestInit):
	def test_mlkj(self):
		asap = os.path.join(os.pardir, os.pardir, "test_files", "other",
		                    "Game.of.Thrones.S01E07.HDTV.XviD-ASAP.srr")
		good = os.path.join(os.pardir, os.pardir, "test_files", "other",
		                    "Antz.1998.iNTERNAL.DVDRip.XviD-SLeTDiVX.srr")
		
		# Dexter.S05E02.iNTERNAL.720p.HDTV.x264-ORENJI
		# http://trac.videolan.org/vlc/ticket/4463
		# http://trac.videolan.org/vlc/search?q=.rar+
		#print_details(php)
#		pprint.pprint(info(php))
		
#		pprint.pprint(info(srr))

		for block in RarReader(good):
			pprint.pprint(block) 
			pprint.pprint(hex(block.flags))

# first.volume.HEAD_FLAG.set.for.rXX_UNP_VER.is.2.0.with.m0.not.2.9
		
	def test_srr(self):
		antz = os.path.join(os.pardir, "test_files",
				"Antz.1998.iNTERNAL.DVDRip.XviD-SLeTDiVX.srr")
#		(appname, stored_files, rar_files, archived_files, recovery,
#		 sfv_entities, sfv_comments) = info(antz)
#		
#		if False:
#			print(appname)
#			print(stored_files)
#			print(rar_files)
#			print(archived_files)
#			print(recovery)
#		
#		self.assertEqual(7320474, recovery.file_size)
		
		#reconstruct(antz, "", "C://Users//Me//Desktop", False, {}, 
		#			True, False, True)
		#self._print_events()
		
	def test_rr(self):
		solid = os.path.join(os.pardir, os.pardir, "test_files",
				"store_rr_solid_auth_unicode_new",
				"store_rr_solid_auth.part1.srr")
		r = info(solid)
		rar_files = r["rar_files"]
		archived_files = r["archived_files"]
		
		self.assertEqual(r["stored_files"], {})
		rarfiles = [ 'store_rr_solid_auth.part1.rar',
					 'store_rr_solid_auth.part2.rar',
					 'store_rr_solid_auth.part3.rar',]
		self.assertEqual(sorted(rar_files.keys()), rarfiles)
		self.assertEqual(rar_files['store_rr_solid_auth.part1.rar'].file_size,
						 33000)
		self.assertEqual(rar_files['store_rr_solid_auth.part2.rar'].file_size,
						 33000)
		self.assertEqual(rar_files['store_rr_solid_auth.part3.rar'].file_size,
						 17504)
		self.assertEqual(archived_files['users_manual4.00.txt'].file_size,
						 78667)

		self.assertEqual("663F4491",
			archived_files['Κείμενο στην ελληνική γλώσσα.txt'].crc32)

		self.assertEqual(3*(2*512)+2*(63*2)+32*2, r["recovery"].file_size)
		self.assertEqual("ReScene .NET 1.2", r["appname"])
		
	def test_comment(self):
		comment = os.path.join(os.pardir, os.pardir, "test_files",
				"store_utf8_comment", "store_utf8_comment.srr")
				#"win_comment.rar"
#		info(comment)
#		print_details(comment)
	
	def test_details(self):
		"""Exercise main.print_details()"""
		srr = os.path.join(os.pardir, os.pardir, "test_files",
			"other", "house.713.hdtv-lol.srr")
		orig_stdout = sys.stdout
		try:
			sys.stdout = StringIO()
			print_details(srr)
		finally:
			sys.stdout = orig_stdout

class TestCreate(TmpDirSetup):
	"""Tests the creation of SRR files."""
	def test_new_rr(self):
		"""Basic SRR creation. No files to store."""
		sfv = os.path.join(self.newrr, "store_rr_solid_auth.sfv")
		srr = os.path.join(self.newrr, "store_rr_solid_auth.part1.srr")
		rar = os.path.join(self.newrr, "store_rr_solid_auth.part1.rar")
		rescene.APPNAME = _get_appname(srr)
		
		# FROM SFV
		dest = os.path.join(self.tdir, "newrr_sfv.srr")
		create_srr(dest, sfv, oso_hash=False)
		self.assertEqual(MsgCode.STORING, self.o.events[0].code)
		# sfv also has .srr file included
		self.assertEqual(MsgCode.NO_RAR, self.o.events[1].code)

		# copy original and add .sfv to original before checking correctness
		origcopy = _copy(srr, self.tdir)
		add_stored_files(origcopy, sfv)
		self.assertTrue(cmp(origcopy, dest), "Files not equivalent.")
		
		# FROM RAR
		self._clear_events()
		assert len(self.o.events) == 0
		dest = os.path.join(self.tdir, "newrr_rar.srr")
		create_srr(dest, rar, oso_hash=False)
		self.assertEqual(MsgCode.NO_FILES, self.o.events[0].code)
		self.assertEqual(MsgCode.MSG, self.o.events[1].code)
		self.assertTrue(cmp(srr, dest), "Files not equivalent.")

	def test_old_folder(self):
		"""Folder support."""
		sfv = os.path.join(self.oldfolder, "store_split_folder.sfv")
		srr = os.path.join(self.oldfolder, "store_split_folder.srr")
		rar = os.path.join(self.oldfolder, "store_split_folder.rar")
		rescene.APPNAME = _get_appname(srr)
		
		origcopy = _copy(srr, self.tdir)
		
		# FROM SFV
		dest = os.path.join(self.tdir, "oldfolder_sfv.srr")
		create_srr(dest, sfv, oso_hash=False)
		self.assertEqual(MsgCode.STORING, self.o.events[0].code)
		self.assertTrue(cmp(origcopy, dest), "Files not equivalent.")
		
		# FROM RAR
		self._clear_events()
		dest = os.path.join(self.tdir, "oldfolder_rar.srr")
		create_srr(dest, rar, oso_hash=False)
		self.assertEqual(MsgCode.NO_FILES, self.o.events[0].code)
		self.assertEqual(MsgCode.MSG, self.o.events[1].code)
		remove_stored_files(origcopy, os.path.basename(sfv))
		self.assertTrue(cmp(origcopy, dest), "Files not equivalent.")
	
	def test_utf_unix(self):
		srr = os.path.join(self.utfunix, "store_utf8_comment.srr")
		rar = os.path.join(self.utfunix, "store_utf8_comment.rar")
		rescene.APPNAME = _get_appname(srr)
		
		origcopy = _copy(srr, self.tdir)
		dest = os.path.join(self.tdir, "utf_unix_rar.srr")
		
		create_srr(dest, rar)
		self.assertEqual(MsgCode.NO_FILES, self.o.events[0].code)
		self.assertEqual(MsgCode.MSG, self.o.events[1].code)
		self.assertTrue(cmp(origcopy, dest), "Files not equivalent.")

	def test_compressed(self):
		rar = os.path.join(self.compression, "best_little.rar")
		dest = os.path.join(self.tdir, "compression.srr")
#		self.assertRaises(ValueError, create_srr, dest, rar)
#		self.assertEqual(MsgCode.FBLOCK, self.o.last_event().code)
		self.assertTrue(create_srr(dest, rar, compressed=True))
		#self._print_events()
		self.assertEqual(MsgCode.BLOCK, self.o.last_event().code)
	
	def test_osohash_path(self):
		"""Test OSO hash calculation of file with path"""
		
		# Create a test Rar file storing an uncompressed data file.
		# The data file must be at least 64 KiB
		# for OSO hashing to work.
		rarpath = os.path.join(self.tdir, "test.rar")
		with open(rarpath, "wb") as file:
			file.write(rar.RAR_MARKER_BLOCK)
			
			block = rar.RarBlock.__new__(rar.RarBlock)
			block.crc = 0  # Dummy value; not verified
			
			block.rawtype = rar.BlockType.RarVolumeHeader
			block.flags = 0
			block._write_header(rar.HEADER_LENGTH)
			file.write(block.block_bytes())
			
			block.rawtype = rar.BlockType.RarPackedFile
			block.flags = 0
			datasize = 128 * 1024
			datapath = "dir\\datafile"
			pathbytes = datapath.encode("ascii")
			header = struct.pack(str("<IIBIIBBHI"),
				datasize, datasize,  # Packed, unpacked
				0, 0, 0,  # OS, CRC, timestamp
				0,  # Rar version
				rar.COMPR_STORING,
				len(pathbytes),
				0,  # File attributes
			)
			header += pathbytes
			block._write_header(rar.HEADER_LENGTH + len(header))
			file.write(block.block_bytes())
			file.write(header)
			file.write(bytearray(datasize))
		
		# Create an SRR file from the Rar file
		srr = os.path.join(self.tdir, "test.srr")
		self.assertTrue(create_srr(srr, rarpath, oso_hash=True))
		
		# Verify that the correct OSO hash is stored,
		# and that just the base name of the file is recorded
		expected = ("datafile", "0000000000020000", datasize)
		self.assertEqual([expected], info(srr)["oso_hashes"])

def _copy(cfile, destination_dir):
	"""Copies 'cfile' to 'destination_dir'. Returns path of new file.
	Removes read-only tag to enable cleanup afterwards."""
	shutil.copy(cfile, destination_dir)
	origcopy = os.path.join(destination_dir, os.path.basename(cfile))
	os.chmod(origcopy, 0o700) # remove read-only flag
	return origcopy
		
class TestRebuild(TmpDirSetup):
	def test_file_not_found(self):
		srr = os.path.join(self.newrr, "store_rr_solid_auth.part1.srr")
		# file is in /txt/ a directory deeper
		self.assertRaises(FileNotFound, reconstruct, srr, self.files_dir, 
						  self.tdir)

	def test_new_rr(self):
		"""Rar files with recovery record. 
		SRR has no files stored. No folders in the rars."""
		sfv = os.path.join(self.newrr, "store_rr_solid_auth.sfv")
		srr = os.path.join(self.newrr, "store_rr_solid_auth.part1.srr")
		rar1 = os.path.join(self.newrr, "store_rr_solid_auth.part1.rar")
		rar2 = os.path.join(self.newrr, "store_rr_solid_auth.part2.rar")
		rar3 = os.path.join(self.newrr, "store_rr_solid_auth.part3.rar")

		reconstruct(srr, self.files_dir, self.tdir, auto_locate_renamed=True)
		#self._print_events()
		_copy(srr, self.tdir) # is included in sfv
		_copy(sfv, self.tdir) # for checking by hand
		cmp1 = os.path.join(self.tdir, "store_rr_solid_auth.part1.rar")
		cmp2 = os.path.join(self.tdir, "store_rr_solid_auth.part2.rar")
		cmp3 = os.path.join(self.tdir, "store_rr_solid_auth.part3.rar")
		self.cleanup = False 
		self.assertEqual(os.path.getsize(cmp1), os.path.getsize(rar1))
		self.assertEqual(os.path.getsize(cmp2), os.path.getsize(rar2))
		self.assertEqual(os.path.getsize(cmp3), os.path.getsize(rar3))
		self.assertTrue(cmp(cmp1, rar1), "Files not equivalent.")
		self.assertTrue(cmp(cmp2, rar2), "Files not equivalent.")
		self.assertTrue(cmp(cmp3, rar3), "Files not equivalent.")
		self.cleanup = True

	def test_old_folder(self):
		"""Folder support. Contains SFV."""
		sfv = os.path.join(self.oldfolder, "store_split_folder.sfv")
		srr = os.path.join(self.oldfolder, "store_split_folder.srr")
		rar1 = os.path.join(self.oldfolder, "store_split_folder.rar")
		rar2 = os.path.join(self.oldfolder, "store_split_folder.r00")
		rar3 = os.path.join(self.oldfolder, "store_split_folder.r01")
		
		reconstruct(srr, self.files_dir, self.tdir)
		self.cleanup = False
		cmp1 = os.path.join(self.tdir, "store_split_folder.rar")
		cmp2 = os.path.join(self.tdir, "store_split_folder.r00")
		cmp3 = os.path.join(self.tdir, "store_split_folder.r01")
		sfvc = os.path.join(self.tdir, "store_split_folder.sfv")
		self.assertTrue(cmp(cmp1, rar1), "Files not equivalent.")
		self.assertTrue(cmp(cmp2, rar2), "Files not equivalent.")
		self.assertTrue(cmp(cmp3, rar3), "Files not equivalent.")
		self.assertTrue(cmp(sfvc, sfv), "Files not equivalent.")
		self.cleanup = True
	
	def test_utf_unix(self):
		srr = os.path.join(self.utfunix, "store_utf8_comment.srr")
		rar = os.path.join(self.utfunix, "store_utf8_comment.rar")
		new = os.path.join(self.tdir, "store_utf8_comment.rar")

		reconstruct(srr, self.txt, self.tdir, auto_locate_renamed=True)
		# it only works because of the auto locate
		# self._print_events()
		self.assertTrue(cmp(new, rar), "Files not equivalent.")
		
	def test_hints(self):
		pass
	
	def test_fake_file(self):
		pass
	
	def test_compressed(self):
		rar = os.path.join(self.compression, "best_little.rar")
		dest = os.path.join(self.tdir, "compression.srr")
		
		

class TestHelper(TestInit):
	"""Test helper functions."""
	def test_autolocate_renamed(self):
		result = _auto_locate_renamed("something.txt", 0, self.files_dir)
		self.assertEqual(os.path.join(self.files_dir, "txt", "empty_file.txt"),
						 result, "Empty file not found.")
		
	def test_flagcheck(self):
		block = SrrStoredFileBlock(file_name="file.name", file_size=1234)
		block.flags = SrrStoredFileBlock.SUPPORTED_FLAG_MASK
		_flag_check_srr(block)
		# these changes actually don't get written
		# block.flags = SrrStoredFileBlock.PATHS_SAVED
		# _flag_check_srr(block) # -> we don't use PATHS_SAVED
		block.flags = 0xffff
		_flag_check_srr(block)
		# self._print_events()
		self.assertEqual(len(self.o.events), 1)
		_flag_check_srr(SrrStoredFileBlock(file_name="file.name", file_size=0))
		self.assertEqual(self.o.last_event().code, MsgCode.UNSUPPORTED_FLAG)
		
	def test_handle_rar_failure(self):
		tfile = os.path.join(self.files_dir, 
		                     "store_split_folder_old_srrsfv_windows", 
		                     "store_split_folder.r00")
		self.assertRaises(ValueError, list, _handle_rar(tfile))
	
	def test_handle_rar(self):
		base = join(self.files_dir, "store_split_folder_old_srrsfv_windows")
		result = [f for f in _handle_rar(join(base, "store_split_folder.rar"))]
		expected = [join(base, "store_split_folder.rar"),
		            join(base, "store_split_folder.r00"),
		            join(base, "store_split_folder.r01")]
		self.assertEqual(result, expected)
		
	def test_handle_rar_old_winrar(self):
		base = join(self.files_dir, "store_split_folder_old_srrsfv_windows")
		tfile = join(base, "store_split_folder.r00")
		self.assertRaises(ValueError, list, _handle_rar(tfile))
			
		result = [f for f in _handle_rar(join(base, "winrar2.80.rar"))]
		expected = [join(base, "winrar2.80.rar")]
		for i in range(17):
			expected.append(join(base, "winrar2.80.r%02d" % i))
		self.assertEqual(result, expected)
			
	def test_locate_file(self):
		"""_locate_file("""
		
def _get_appname(srr):
	for block in RarReader(srr).read_all():
		if block.rawtype == BlockType.SrrHeader:
			return block.appname