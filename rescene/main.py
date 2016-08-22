#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011-2016 pyReScene
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

"""Facade"""

from __future__ import (with_statement, unicode_literals, print_function,
	absolute_import, division)

from tempfile import mkstemp, mkdtemp
from glob import glob

import fnmatch
import io
import os
import sys
import zlib
import re

import hashlib
import nntplib
import collections

import time
import shutil
import subprocess
import multiprocessing

import rescene
from rescene.rar import (BlockType, RarReader,
	SrrStoredFileBlock, SrrRarFileBlock, SrrHeaderBlock, COMPR_STORING, 
	RarPackedFileBlock, SrrOsoHashBlock, SrrZipFileBlock)
from rescene.rarstream import RarStream, FakeFile
from rescene.utility import (SfvEntry, is_rar, _DEBUG,
                             first_rars, next_archive, empty_folder)
from rescene.utility import parse_sfv_file, parse_sfv_data
from rescene.utility import filter_sfv_duplicates
from rescene.utility import basestring, fsunicode
from rescene.utility import decodetext, encodeerrors
from rescene.utility import capitalized_fn
from rescene.utility import calculate_crc32
from rescene.osohash import osohash_from
from rescene.zip import ZipReader, ZIP_EXT, ZipFileBlock

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behavior
	range = xrange #@ReservedAssignment

try:  # Python 3
	from functools import partial
	int_to_bytes_big = partial(int.to_bytes, byteorder="big")
	int_from_bytes_big = partial(int.from_bytes, byteorder="big")
except AttributeError:  # Python < 3
	from binascii import unhexlify, hexlify
	def int_to_bytes_big(value, length):
		return unhexlify(format(value, "0{0}X".format(length * 2)))
	def int_from_bytes_big(bytes):
		return int(hexlify(bytes), 16)

callbacks = []

try:
	odict = collections.OrderedDict #@UndefinedVariable
except AttributeError:
	# Python 2.6 OrderedDict
	from rescene import ordereddict
	odict = ordereddict.OrderedDict

class Event(object):
	"""Attributes 'message' and 'code'."""
	pass

def subscribe(callback):
	callbacks.append(callback)
	
def _fire(code, **kwargs):
	"""Notify subscribers of a new event."""
	e = Event()
	e.code = code
	for k, v in kwargs.items():
		setattr(e, k, v)
	for fn in callbacks:
		fn(e) # this is calling the __call__ method

class Observer(object):
	"""Stores all events send to the observing object. Useful for
	communicating intermediate results or events when calling API function.
	Observer class used in the unit tests."""
	def __init__(self):
		self.events = []
	
	def __call__(self, event):
		self.events.append(event)
		
	def last_event(self):
		return (self.events[len(self.events) - 1]
				if len(self.events) > 0 else None)
	
	def print_events(self):
		for event in self.events:
			print(event.__dict__) # dictionary with added attributes

class MsgCode(object):
	MSG, OS_ERROR, NO_OVERWRITE, NO_EXTRACTION, DUPE, STORING, FILE_NOT_FOUND,\
	NO_FILES, DEL_STORED_FILE, RENAME_FILE, CMT, AV, AUTHENTCITY, \
	NO_RAR, BLOCK, FBLOCK, RBLOCK, COMPRESSION, UNSUPPORTED_FLAG, CRC,  \
	USER_ABORTED, AUTO_LOCATE, UNKNOWN = list(range(23))

class DupeFileName(Exception):
	"""A file already exists with the given name."""

class NotSrrFile(Exception):
	"""The SRR file is not in the expected format."""

class InvalidFileSize(Exception):
	"""The file size of the file to pack is not correct."""
	
class FileNotFound(Exception):
	"""The file does not exist."""

class EmptySfv(ValueError):
	"""The SFV does not have any valid contents."""

def can_overwrite(file_path):
	"""Method must be wrapped in the application to ask what to do. 
		Returns False when file exists.
		Returns True when file does not exist."""
	if _DEBUG:
		print("check overwrite: %s (%s)" %
	          (file_path, not os.path.isfile(file_path)))
	return not os.path.isfile(file_path)

def change_rescene_name_version(new_name):
	if not isinstance(new_name, basestring):
		raise AttributeError("ReScene name must be a string.")
	if len(new_name) > 0xFFF6:
		raise AttributeError("Application name too long.")
	rescene.APPNAME = new_name

def extract_files(srr_file, out_folder, extract_paths=True,
                  packed_name="", matcher=None):
	"""
	If packed_name is given, 
		it tries to extract all files with that name only.
		(It is possible for an SRR file to have a file with the same name
		if they have different paths.)
		If it is a relative path, it only extracts a single file.
	If extract_paths is True, 
		it tries to re-create the file with its stored path.
	If matcher is provided and not packed_name,
		it uses this function with one input parameter to find out
		if a file has to be extracted instead of using packed_name.
	Returns tuple: (extracted location, bool: extracted or overwritten)
	"""
	extracted_files = []
	def process(block):
		"""Process SrrStoredFileBlocks by deciding whether to extract the
		packed file or not: write each file if no name is specified or only
		those whose path/name matches. (only name if no path is specified)"""
		out_file = _opath(block, extract_paths, out_folder)
		if ((not packed_name and not matcher) or 
			(not packed_name and matcher and matcher(block.file_name)) or 
			packed_name ==
		    os.path.basename(packed_name) == os.path.basename(out_file) or
		    os.path.normpath(packed_name) == block.os_file_name()):
			success = _extract(block, out_file)
			extracted_files.append((out_file, success))
			return success

	# select all SrrStoredFileBlocks from SRR
	file_blocks = filter(lambda b: b.rawtype == BlockType.SrrStoredFile,
						 RarReader(srr_file).read_all())
	if not sum(x == True for x in map(process, file_blocks)) and packed_name:
		if _DEBUG: print("File to be extracted not found.")
		_fire(MsgCode.NO_EXTRACTION, message="Requested file not found")
	return extracted_files

def _opath(block, extract_paths, out_folder):
	"""Constructs path for the file to be extracted from the SRR. 
	block: SrrStoredFileBlock
	extract_paths: True or False
	out_folder: all paths start here"""
	file_name = block.os_file_name()
	if not extract_paths:
		file_name = os.path.basename(file_name)
	return os.path.join(os.path.normpath(out_folder), file_name)

def _extract(block, out_file):
	"""Extracts contents of SrrStoredFileBlock to out_file
	after checking it can overwrite it if necessary.
	The block must match the srr_file."""
	if can_overwrite(out_file):
		msg = "Re-creating stored file: %s" % block.file_name
		if _DEBUG: print(msg)
		_fire(MsgCode.MSG, message=msg)
		# IOError: [Errno 2] No such file or directory: 
		# '..\\test_files\\store_little\\' +
		# 'store_little/store_little.srr' -> create path
		try:
			os.makedirs(os.path.dirname(out_file))
		except BaseException as ex: # WindowsError: [Error 183]
			# cannot create dir because folder(s) already exist
			if _DEBUG: print(ex)
			_fire(MsgCode.OS_ERROR, message=ex)
		# what error when we cannot create path? XXX: Subs vs subs
		# that already exists -> LINUX
		with open(out_file, "wb") as out_stream:
			out_stream.write(block.srr_data())
		return True
	else: # User cancelled the file extraction
		_fire(MsgCode.NO_OVERWRITE, message="Operation aborted. "
		      "Stored file %s already exists." % out_file)
		return False

def add_stored_files(srr_file, store_files, in_folder="", save_paths=False,
	                 usenet=False):
	"""Add one or more files to a SRR reconstruction file.
	srr_file:     the srr file to add files to
	store_files:  a list of files to store in the srr
	              first file will be at the top
	              Wildcards are accepted for paths and file names.
	in_folder:    root folder for relative paths to store
	              necessary when save_paths is True 
	              #or paths are relative to in_folder in store_files
	save_paths:   if the path relative to in_folder 
	              must be stored with the file name
	usenet:       Don't try to add dupes and keep working quietly
	
	Will skip files that cannot be read when usenet=True.
	TODO: try to process the list like for usenet
	      instead of failing completely?
				   
	Raises ArchiveNotFoundError, DupeFileName, NotSrrFile, AttributeError
	"""
	
	if not isinstance(store_files, (list, tuple)): # we need a list
		store_files = [store_files]
	
	# Make it more likely to find duplicates
	store_files = list(map(os.path.normpath, store_files))
	
	rr = RarReader(srr_file) # ArchiveNotFoundError
	if rr.file_type() != RarReader.SRR:
		raise NotSrrFile("Not an SRR file.")
	
	if _DEBUG: print("Checking for dupes before adding files.")
	for block in rr.read_all():
		if block.rawtype == BlockType.SrrStoredFile:
			existing = block.os_file_name()
			if existing in store_files:
				msg = "There already is a file with the same name stored."
				_fire(MsgCode.DUPE, message=msg)
				if usenet:
					# don't try to add dupes and keep working quietly
					store_files.remove(existing)
				else:
					raise DupeFileName(msg)

	# create a temporarily file
	tmpfd, tmpname = mkstemp(prefix="srr_", suffix=".tmp", 
							 dir=os.path.dirname(srr_file))
	tmpfile = os.fdopen(tmpfd, "wb")

	in_folder = in_folder if in_folder else os.path.dirname(srr_file)
	location = False # whether we've added the files or not
	if _DEBUG: print("Reading blocks for adding files.")
	try:
		for block in rr.read_all():
			# add the files before the srr rar blocks
			if block.rawtype == BlockType.SrrRarFile and not location:
				location = True
				if not usenet:
					amount_added = 0
					for f in _search(store_files, in_folder):
						_store(f, tmpfile, save_paths, in_folder)
						amount_added += 1
					if not amount_added:
						_fire(MsgCode.NO_FILES,
						      message="No files found to add.")
				else: #TODO: make it nicer
					for f in store_files:
						_store_fh(f, tmpfile)
				
			tmpfile.write(block.block_bytes())
			
			# we need to copy the contents from blocks too
			if block.rawtype == BlockType.SrrStoredFile:
				tmpfile.write(block.srr_data())
			# XXX: will this always work correct? 
			
		if not location: # music video SRR file: add to end
			if not usenet:
				amount_added = 0
				for f in _search(store_files, in_folder):
					_store(f, tmpfile, save_paths, in_folder)
					amount_added += 1
				if not amount_added:
					_fire(MsgCode.NO_FILES,
					      message="No files found to add.")
			else: #TODO: make it nicer
				for f in store_files:
					_store_fh(f, tmpfile)	
	except:
		tmpfile.close()
		os.unlink(tmpname)
		raise
	else:
		tmpfile.close()
#		if not location:
#			# Bad SRR file or RAR file given.
#			os.remove(tmpname)
#			raise NotSrrFile("No SrrRarFile blocks detected. -> Not SRR. "
#							 "Zero files added.")
		# original srr file is replaced by the temp file
		os.remove(srr_file)
		os.rename(tmpname, srr_file)

def remove_stored_files(srr_file, store_files):
	"""Remove files stored inside a SRR file.
	srr_file:    the SRR file to remove stored files from
	store_files: list of files to be removed
	             must contain the relative path when necessary
	
	raises ArchiveNotFoundError, NotSrrFile, TypeError"""
	rr = RarReader(srr_file) # ArchiveNotFoundError
	if rr.file_type() != RarReader.SRR:
		raise NotSrrFile("Not an SRR file.")
	
	# create a temporarily file
	tmpfd, tmpname = mkstemp(prefix="remove_", suffix=".srr", 
							 dir=os.path.dirname(srr_file))
	tmpfile = os.fdopen(tmpfd, "wb")
	
	try:
		for block in rr.read_all():
			if block.rawtype == BlockType.SrrStoredFile:
				if block.file_name in store_files:
					_fire(MsgCode.DEL_STORED_FILE,
						  message="'%s' deleted." % block.file_name)
				else: # write header and stored file
					tmpfile.write(block.block_bytes())
					tmpfile.write(block.srr_data())		
			else: # TODO: write better tests here!!
				tmpfile.write(block.block_bytes())
		tmpfile.close()
		os.remove(srr_file)
		os.rename(tmpname, srr_file)
	except BaseException as ex:
		print(ex)
		os.unlink(tmpname)
		raise

def rename_stored_file(srr_file, stored_name, new_name):
	"""Changes the stored file name and the path. 
	srr_file:    the SRR file that contains the file to rename
	stored_name: the old file
	new_name:    the new name for the file
		
	raises ArchiveNotFoundError, 
	NotSrrFile, 
	AttributeError (invalid chars),
	FileNotFound
	"""
	rr = RarReader(srr_file) # ArchiveNotFoundError
	if rr.file_type() != RarReader.SRR:
		raise NotSrrFile("Not an SRR file.")
	
	for block in rr.read_all():
		if block.rawtype == BlockType.SrrStoredFile  \
				and block.file_name == stored_name:
			_fire(MsgCode.RENAME_FILE,
				  message="Renaming '%s'" % block.file_name)
			block.renameto(new_name)
			break
	else:
		_fire(MsgCode.FILE_NOT_FOUND, 
			  message="'%s' not found" % stored_name)
		raise FileNotFound("No stored file with such name.")

def validate_srr(srr_file):
	"""Checks if the SRR file has the right format and verifies
	the CRC values when applicable.
	"""
	raise NotImplementedError()

# TODO: test joining SRRs, although it works (exceptions)
def merge_srrs(srr_files, output_file, application_name=None):
	"""Merge the given iterable of srr_files together.
	srr_files:        iterable of SRR files to merge (including the path)
	output_file:	  the merged SRR file; the result
	application_name: if an other name is wanted for the merged file
	                  otherwise the first non empty name is used
	
	Order data of the result: application name, stored files, RAR meta-data
	
	TODO: rarfixes that need to be merged somewhere in the middle
	      2 sfvs that both have all the RAR files, but not individually
	"""
	stored_files = []
	other_blocks = []

	# read in all data
	for srr_file in srr_files:
		for block in RarReader(srr_file).read_all():
			if block.rawtype == BlockType.SrrHeader:
				if not application_name or application_name == "":
					application_name = block.appname
			elif block.rawtype == BlockType.SrrStoredFile:
				stored_files.append(block)
			else:
				other_blocks.append(block)
			
	# write the gathered data in the correct order
	with open(output_file, "wb") as new:
		new.write(SrrHeaderBlock(appname=application_name).block_bytes())
		
		# all stored files in the beginning after the header
		for sblock in stored_files:
			new.write(sblock.block_bytes())
			new.write(sblock.srr_data())
		
		# everything else in the same order as the original file
		for block in other_blocks:
			new.write(block.block_bytes())
			#TODO: this is skipping data in some less common cases?

def create_srr(srr_name, infiles, in_folder="",
               store_files=None, save_paths=False, compressed=False,
               oso_hash=True, tmp_srr_name=None):
	"""
	srr_name:    path and name of the SRR file to create
	             (for checking existence)
	tmp_srr_name the actual file created! To be used with utility helpers.
	             This will be the same as srr_name when not provided.
	infiles:     RAR, SFV or ZIP file(s) to create SRR from
	in_folder:   root folder for relative paths to store
	             necessary when save_paths is True or
	             paths are relative to in_folder in store_file
	store_files: a list of files to store in the SRR
	             SFVs from infiles do not need to be in this list.
	save_paths:  if the path relative to in_folder 
	             must be stored with the file name e.g. Sample/ or Proof/
	compressed:  Do we create an SRR or not when encountered compressed files?
	oso_hash:    Store OSO/ISDb hashes or not.
	
	Returns True: success
	Returns False: existing .srr file not overwritten
	Raises ValueError if rars in infiles are not the first of the archives.
	"""
	try:
		if not tmp_srr_name:
			tmp_srr_name = srr_name
		if store_files is None:      # no default initialization with []
			store_files = []
		if not isinstance(infiles, (list, tuple)):  # we need a list
			infiles = [infiles]      # otherwise iterating over characters
			
		if not can_overwrite(srr_name):
			return False
	except KeyboardInterrupt:
		if tmp_srr_name == srr_name:
			# so an existing SRR file won't be removed upon Ctrl+C
			raise KeyboardInterrupt("DONT_DELETE")
		else:
			raise
	
	srr = open(tmp_srr_name, "wb")
	srr.write(SrrHeaderBlock(appname=rescene.APPNAME).block_bytes())
	
	try:
		# STORE FILES
		# We store copies of any files included in the store_files list 
		# in the .srr using a "store block".
		# Any SFV files used are also included.
		store_files.extend([f for f in infiles if f[-4:].lower() == ".sfv"])
		
		if not len([_store(f, srr, save_paths, in_folder)
					for f in _search(store_files, in_folder)]):
			_fire(MsgCode.NO_FILES, message="No files found to store.")
		
		# COLLECT ARCHIVES
		rarfiles = []
		zipfiles = []
		for infile in infiles:
			if str(infile).lower().endswith(".sfv"):
				# SFV can sill have non-RAR files: empty list here
				files_sfv = _handle_sfv(infile)
				rarfiles.extend(files_sfv)
				# EmptySfv Exception: no useful lines found in the SFV file
			elif infile[-4:].lower() in ZIP_EXT:
				zipfiles.append(infile)
			else:
				rarfiles.extend(_handle_rar(infile))
	
		oso_dict = odict()
		# STORE RAR ARCHIVE BLOCKS
		for rarfile in rarfiles:
			# take into account case sensitivity on Unix systems
			(rfexact, rfcapitals) = capitalized_fn(rarfile)
			if not os.path.isfile(rfexact):
				# all lower in sfv and casings in RAR file names
				msg = "Referenced file not found: %s" % rfexact
				_fire(code=MsgCode.FILE_NOT_FOUND, message=msg)
				srr.close()	  
				os.unlink(tmp_srr_name)
				raise FileNotFound(msg)
	
			fname = os.path.relpath(rfcapitals, in_folder) if save_paths  \
				else os.path.basename(rfcapitals)
			_fire(MsgCode.MSG, message="Processing file: %s" % fname)
			
			rarblock = SrrRarFileBlock(file_name=fname)
	#		if save_paths:
	#			rarblock.flags |= SrrRarFileBlock.PATHS_SAVED
			srr.write(rarblock.block_bytes())
			
			rr = RarReader(rfexact)
			for block in rr.read_all():
				if block.rawtype == BlockType.RarPackedFile:
					_fire(MsgCode.FBLOCK, message="RAR Packed File Block",
						  compression_method=block.compression_method,
						  packed_size=block.packed_size,
						  unpacked_size=block.unpacked_size,
						  file_name=block.file_name)
					if block.compression_method != COMPR_STORING:
						_fire(MsgCode.COMPRESSION, 
						      message="Don't delete 'em yet!")
						if not compressed:
							srr.close()
							os.unlink(tmp_srr_name)
							raise ValueError("Archive uses unsupported "
							           "compression method: %s" % rarfile)
					else:
						# store first RAR where we encounter the stored file
						oso_dict.setdefault(block.os_file_name(), rarfile)
				elif _is_recovery(block):
					_fire(MsgCode.RBLOCK, message="RAR Recovery Block",
						  packed_size=block.packed_size,
						  recovery_sectors=block.recovery_sectors,
						  data_sectors=block.data_sectors)
				else:
					_fire(MsgCode.BLOCK, message="RAR Block",
						  type=block.rawtype, size=block.header_size)
				# store the raw data for any blocks found
				srr.write(block.block_bytes())
				
		# STORE ZIP META DATA
		for zipfile in zipfiles:
			if not os.path.isfile(zipfile):
				_fire(code=MsgCode.FILE_NOT_FOUND,
					  message="Referenced file not found: %s" % rarfile)
				srr.close()	  
				os.unlink(srr_name)
				raise FileNotFound("Referenced file not found: %s" % rarfile)
			
			fname = os.path.relpath(zipfile, in_folder) if save_paths  \
				else os.path.basename(zipfile)
			_fire(MsgCode.MSG, message="Processing file: %s." % fname)
		
			meta_data_bytes = b""
			for zipblock in ZipReader(zipfile):
				print(zipblock)
				if (isinstance(zipblock, ZipFileBlock)
					and zipblock.has_compression()):
					_fire(MsgCode.COMPRESSION, message="Don't delete 'em yet!")
					if not compressed:
						srr.close()
						os.unlink(srr_name)
						raise ValueError("Archive uses unsupported "
						           "compression method: %s" % zipfile)
				meta_data_bytes += zipblock.hbytes
				# TODO: no other blocks with non header data???
				
			zip_crc = calculate_crc32(zipfile)
			srrzblock = SrrZipFileBlock(
			    file_name=fname, zip_crc=zip_crc, metadata=meta_data_bytes)
			srr.write(srrzblock.block_bytes())

		# STORE OSO/ISDb HASHES
		if oso_hash:
			for (fname, rarname) in oso_dict.items():
				try:
					oso_hash, file_size = osohash_from(rarname, fname, True)
					block = SrrOsoHashBlock(file_size=file_size, 
						file_name=os.path.basename(fname), oso_hash=oso_hash)
					srr.write(block.block_bytes())	
				except (ValueError, AttributeError):
					pass # file is too small or compressed RARs
		return True
	finally:
		# when an IOError is raised, we close the file for further cleanup
		srr.close()
		
def create_srr_single_volume(srr_name, infile, tmp_srr_name=None):
	"""
	srr_name:    path and name of the SRR file to create
	             (for checking existence)
	tmp_srr_name the actual file created! To be used with utility helpers.
	             This will be the same as srr_name when not provided.
	infile:      RAR (or .vob) to create SRR from
	
	Returns True: success
	Returns False: existing .srr file not overwritten
	"""
	try:
		if not tmp_srr_name:
			tmp_srr_name = srr_name
		if not can_overwrite(srr_name):
			return False
	except KeyboardInterrupt:
		if tmp_srr_name == srr_name:
			# so an existing SRR file won't be removed upon Ctrl+C
			raise KeyboardInterrupt("DONT_DELETE")
		else:
			raise
	
	srr = open(tmp_srr_name, "wb")
	srr.write(SrrHeaderBlock(appname=rescene.APPNAME).block_bytes())
	
	try:
		# STORE ARCHIVE BLOCKS
		if not os.path.isfile(infile):
			# TODO: case sensitivity on Unix systems
			# all lower in sfv and casings in RAR file names
			msg = "Referenced file not found: %s" % infile
			_fire(code=MsgCode.FILE_NOT_FOUND, message=msg)
			srr.close()
			os.unlink(tmp_srr_name)
			raise FileNotFound(msg)
		base = os.path.basename(infile)

		_fire(MsgCode.MSG, message="Processing file: %s" % base)
		
		rarblock = SrrRarFileBlock(file_name=base)
		srr.write(rarblock.block_bytes())
		
		rr = RarReader(infile)
		for block in rr.read_all():
			# store the raw data for any blocks found
			srr.write(block.block_bytes())
				
		return True
	finally:
		# when an IOError is raised, we close the file for further cleanup
		srr.close()

def _rarreader_usenet(rarfile, read_retries=7):
	"""Tries redownloading data read_retries times if it fails.
	Regular RarReader, but handles Usenet exceptions and retries."""
	rr = RarReader(rarfile)
	try:
		return rr.read_all()
	except (EnvironmentError, IndexError, nntplib.NNTPTemporaryError) as error:
		# IndexError: Offset after end of file.
		# EnvironmentError: Invalid RAR block length (9728) at offset 0xe4e1b3
		# EnvironmentError: Invalid RAR block length (0) at offset 0xe4e1b1
		#	(banana_joe.cd2.part46.rar) Banana.Joe.XViD-HRG-CD1
		print(error)
		print("Parsing RAR file failed. Trying again a couple of times.")
		
		if _DEBUG:
			import traceback
			traceback.print_exc()
		
		# reading from usenet fails somewhere
		# keep redownloading
		stop = 0
		rarfile.init_data(server_nb=stop)
		while True:
			try:
				rr = RarReader(rarfile)
				return rr.read_all()
			except (EnvironmentError, IndexError,
			        nntplib.NNTPTemporaryError) as error:
				print(error)
				if stop <= read_retries:
					stop += 1
					print(stop)
					# pick an other server
					rarfile.init_data(server_nb=stop)
				else:
					raise
				
def create_srr_fh(srr_name, infiles, allfiles=None,
			   store_files=None, save_paths=False,
			   stat=True, read_retries=7): #TODO: use stat in caller
	"""Same as the function above, but uses open file handles for 
	all parameters. Can be used for creating SRRs directly from a
	virtual source. e.g. Usenet
	
	infiles:     RAR or SFV file(s) to create SRR from
	store_files: a list of files to store in the SRR
	in_folder:   root folder for relative paths to store
	             necessary when save_paths is True or
	             paths are relative to in_folder in store_file
	srr_name:    path and name of the SRR file to create
	save_paths:  if the path relative to in_folder 
	             must be stored with the file name
				 
	allfiles:    open file handles that must be used instead of hd files
	
	Returns False if infiles or the SFVs are empty
	Raises ValueError if RARs in infiles are not the first of the archives.
	"""
	if store_files is None:		 # no default initialization with []
		store_files = []
	if not isinstance(infiles, (list, tuple)): # we need a list
		infiles = [infiles] # otherwise iterating over characters
	
	if not len(infiles):
		raise ValueError("No SFV or RAR file supplied.")
	
	if allfiles is None or not len(allfiles):
		harddisk = True
	else:
		harddisk = False
		
	# sanity check for srr_name
	spath = os.path.dirname(srr_name)
	if not os.path.exists(spath): # TODO: test it!
		os.makedirs(spath)
	
	srr = open(srr_name, "wb")
	srr.write(SrrHeaderBlock(appname=rescene.APPNAME).block_bytes())
	
	class StatFailure(Exception):
		"""The file isn't posted completely."""

	try:
		# COLLECT ARCHIVES ----------------------------------------------------
		rarfiles = []
		for infile in infiles:
			rarfile = infile # declaration for 'except:' if it goes wrong here
			if str(infile).lower().endswith(".sfv"):
				# SFV can sill have non-RAR files: empty list here
				files_sfv = _handle_sfv(infile)
				rarfiles.extend(files_sfv)
				# EmptySfv Exception: no useful lines found in the SFV file
			else: # .rar, .001, .exe, ...?
				rarfiles.extend(_handle_rar(allfiles[infile], 
				                            filelist=allfiles, 
				                            read_retries=read_retries))
				
		if not len(rarfiles):
			raise ValueError("The SFV had no contents, files not found, ...")
		
		# check to see if all RAR files are even there, based on the SFVs
		# saves bandwidth on failure
		if not harddisk:
			for rarfile in rarfiles:
				if rarfile not in allfiles:
					# the rars could have capitals while it
					# is all lower in the sfv
					# the opposite can be true too
					found = False
					for (k, v) in allfiles.items():
						if k == rarfile.lower(): # capitals in SFV
							allfiles[rarfile] = v
							found = True
							break
						elif k.lower() == rarfile: # capitals in files
							# make the lookup for the next part succeed
							allfiles[k.lower()] = v
							found = True
							break
						# TODO: both having different capitals
						# possible, but then renaming occured 
					if not found:
						raise FileNotFound("ERROR: '%s' not found." % rarfile)
		else:
			pass
			# different for hard disk
			# check file existence and raise FileNotFound?
			# or do just nothing? it will fail later anyway
		
		# STORE FILES ---------------------------------------------------------
		# We store copies of any files included in the store_files list 
		# in the .srr using a "store block".
		# Any SFV files used are also included.
		store_files.extend([f for f in infiles if f[-4:].lower() == ".sfv"])
		
		# it skips corrupt files
		if not len([_store_fh(f, srr) for f in store_files]):
			_fire(MsgCode.NO_FILES, message="No files found to store.")

		# STORE ARCHIVE BLOCKS ------------------------------------------------
		end_segments_tested = False
		has_end_segment = False
		oso_dict = {}
		
		def test_end_segments():
			if stat:
				print("Checking the end segments. (STAT)")
			
			for rarfile in rarfiles: # preserves bandwidth if it fails
				rarfile = allfiles[rarfile]
				if not rarfile.stat_last_segment():
					raise RuntimeError("No end segment for %s." % rarfile.name)
				# possible: last segment was a success, 
				# but it wasn't the actual last file...
				
				# the fast disconnects don't work well on all servers
#				rarfile.stat_first_segment()

		for rarfile in rarfiles:
			rarfile = allfiles[rarfile]
			_fire(MsgCode.MSG, message="Processing file: %s" % rarfile.name)
			
			rarblock = SrrRarFileBlock(file_name=rarfile.name)
			srr.write(rarblock.block_bytes())
			
			rl = _rarreader_usenet(rarfile, read_retries=read_retries)
			
			for block in rl:
				if block.rawtype == BlockType.RarPackedFile:
					_fire(MsgCode.FBLOCK, message="RAR Packed File Block",
						  compression_method=block.compression_method,
						  packed_size=block.packed_size,
						  unpacked_size=block.unpacked_size,
						  file_name=block.file_name)
					if block.compression_method != COMPR_STORING:
						_fire(MsgCode.COMPRESSION, 
						      message="Don't delete 'em yet!")
	#					srr.close()
	#					os.unlink(srr_name)
	#					raise ValueError("Archive uses unsupported compression "
	#									 "method: %s", rarfile)
					else:
						# store first RAR where we encounter the stored file
						oso_dict.setdefault(block.os_file_name(), rarfile)
				elif _is_recovery(block):
					_fire(MsgCode.RBLOCK, message="RAR Recovery Block",
						  packed_size=block.packed_size,
						  recovery_sectors=block.recovery_sectors,
						  data_sectors=block.data_sectors)
				else:
					_fire(MsgCode.BLOCK, message="RAR Block",
						  type=block.rawtype, size=block.header_size)
					
					# if the first block has a RAR archive end block:
					# STAT all files for existence last segment
					if block.rawtype == BlockType.RarMax:
						has_end_segment = True
				if not end_segments_tested and has_end_segment and not harddisk:
					# check end segments of all following RARs
					# assumption: very high chance this is consistent
					# (all or non having RAR end block)
					test_end_segments()
					end_segments_tested = True
					
				# store the raw data for any blocks found
				srr.write(block.block_bytes())
				
				#TODO: when starting from RARs, detect when incomplete!!!!
	
		# STORE OSO/ISDb HASHES
		# Not for Usenet as we can't be 100% sure the hash will be valid
		srr.close()
	except KeyboardInterrupt:
		srr.close()	
		os.unlink(srr_name) # remove SRR as it is broken
		raise
	except (FileNotFound, KeyError):
		# KeyError should not occur
		"""
		  File "rescene.py", line 476, in create_srr_fh
		    rarfile = allfiles[rarfile]
		KeyError: u'shaolin.2011.720p.bluray.x264-soundwave.rar'"""
		srr.close()	
		os.unlink(srr_name) # remove SRR as it is broken
		_fire(code=MsgCode.FILE_NOT_FOUND,
			  message="Referenced file not found: %s" % rarfile)
		raise
	except:
		srr.close()	
		os.unlink(srr_name) # remove SRR as it is broken
#		traceback.print_exc()
#		raise FileNotFound("Broken file: %s" % rarfile)
		raise

def _handle_sfv(sfile):
	"""Helper function for create_srr and create_srr_fh that yields
	all RAR archives enumerated in a .sfv file.
	Duplicate SFV data lines will be filtered out.
	Throws EmptySfv when not a single line could be parsed."""
	(entries, _comments, _errors) = parse_sfv_file(sfile)
	if not len(entries):
		# Not even a non-RAR file found
		raise EmptySfv("Empty SFV file found.");

	wmsg = "Warning: Non-RAR file found in SFV: '%s'."
	sorted_entries = filter_sfv_duplicates(entries)
	srr_usenet_tool = "NNTPFile" in repr(type(sfile))
	if not srr_usenet_tool:
		for sfv_entry in sorted_entries:
			if is_rar(sfv_entry.file_name):
				yield os.path.join(os.path.dirname(sfile), sfv_entry.file_name)
			else:
				_fire(MsgCode.NO_RAR, message=wmsg % sfv_entry.file_name)
	else:
		for sfv_entry in sorted_entries:
			if is_rar(sfv_entry.file_name):
				yield sfv_entry.file_name
			else:
				_fire(MsgCode.NO_RAR, message=wmsg % sfv_entry.file_name)

def _handle_rar(rfile, filelist=None, read_retries=7):
	"""Helper function for create_srr that yields all existing RAR archives
	based on the first RAR. Archive naming is standardised: 
	no need to read each file yet. Checking for existence is enough, except
	for the first volume. The naming can be ambiguous there, so the volume
	naming style is checked.
	
	rfile: should be the first RAR volume. A ValueError is thrown otherwise.
	filelist: list check if specified instead of HD check (Usenet)
	read_retries: times to retry (Usenet)"""
	def exists(rarfile):
		if filelist:
			return os.path.basename(rarfile) in filelist
		else:
			return os.path.isfile(rarfile)
		
	def filename(robject):
		try: # we need a string, not a NNTPFile,...
			return robject.name
		except:
			return robject
		
	is_old_style_naming = False
	
	# RarReader(rfile) closes the file -> was problem with NNTPFiles
	for block in _rarreader_usenet(rfile, read_retries):
		if (block.rawtype == BlockType.RarVolumeHeader and 
			block.flags & block.VOLUME): # also set for RAR 2.0 archives
			# RAR file is part of multiple volumes. Figure out whether this is
			# the first volume based on file name because some RARs aren't
			# packed with (Win)RAR and always set the MHD_FIRSTVOLUME flag.
			# This flag is set only by RAR 3.0 and later on the first volume.
			#  -> ASAP and IMMERSE always set the first volume flag!
			#      e.g.  Game.of.Thrones.S01E07.HDTV.XviD-ASAP
			#            House.S06E12.720p.HDTV.x264-IMMERSE			
			#  -> RARFileSource version 0.9.2, released 2011-02-22
			#     is not able to start playing from .r00
			#  -> VLC 1.1 complains about broken files: ASAP, FQM
			#if (not block.flags & block.FIRST_VOLUME and first_rars([rfile])):
			#	raise ValueError("You must start with the first volume "
			#	                 "from a RAR set.")
			is_old_style_naming = not bool(block.flags & block.NEW_NUMBERING) 
			
	if first_rars([filename(rfile)]) != [filename(rfile)]:
		raise ValueError("You must start with the first volume from a RAR set.")
			
	next_file = filename(rfile)
	while exists(next_file):
		# TODO: fails on mixed capitals on Linux?
		yield next_file
		next_file = filename(next_archive(next_file, is_old_style_naming))
		
def info(srr_file):
	"""Returns a dictionary with the following keys:
	- appname:        the application name stored in the srr file
	- stored_files:   a list of the files that are added to the srr file
	- rar_files:	  a list of all the rar files
	- archived_files: a list of files packed inside the rar files
	- recovery:       information about the recovery records
	- sfv_entries:    files that are not in rar_files
	- sfv_comments:   the comments that are available in the sfv files
	- compression:    there are files inside the archive that use compression
	Apart from appname, everything is represented by a FileInfo object.
	"""
	stored_files = odict()   # files stored in the srr
	rar_files = odict()      # rar, r00, ...
	sfv_entries = []         # non repairable files from the SFV
	sfv_comments = []
	archived_files = odict() # files inside rar archive(s)
	appname = ""
	recovery = None         # FileInfo object: size recovery record
	current_rar = None      # for calculating file size
	compression = False     # RAR compression on some files
	oso_hashes = []

	for block in RarReader(srr_file).read_all():
		count_size = True
		if block.rawtype == BlockType.SrrHeader:
			appname = block.appname
			current_rar = None # end the file size counting
		elif block.rawtype == BlockType.SrrStoredFile:
			f = FileInfo()
			f.file_name = block.file_name
			f.file_size = block.file_size
			stored_files[block.file_name] = f
			
			# get the CRC32 hashes from the sfv file
			# not stored anywhere -> retrieve from sfv or we do not have it
			if block.file_name[-4:].lower() == ".sfv":
				with open(srr_file, "rb") as sfv:
					sfv.seek(block.block_position + block.header_size)
					sfvdata = sfv.read(block.file_size)
				(entries, comments, errors) = parse_sfv_data(sfvdata)
				sfv_entries.extend(entries)
				sfv_comments.extend(comments)
				# TODO: let user know that there is a bad SFV
				sfv_comments.extend(errors)
			
			current_rar = None # end the file size counting
		elif block.rawtype == BlockType.SrrRarFile:
			count_size = False
			current_rar = None # end the file size counting
				
			key = os.path.basename(block.file_name.lower())
			current_rar = FileInfo()
			current_rar.file_name = block.file_name
			current_rar.file_size = 0
			current_rar.key = key
			current_rar.offset_start_rar = (block.block_position + 
			                                block.header_size)
			rar_files[key] = current_rar
		elif block.rawtype == BlockType.RarPackedFile:
			f = archived_files.get(block.unicode_filename)
			if f is None:
				f = FileInfo()
				f.file_name = block.file_name
				if (block.unpacked_size != 0xffffffffffffffff and  # 1
				    block.unpacked_size != 0xffffffff):  # 2
					f.file_size = block.unpacked_size  # normal case
				else:
					# 1) custom RAR packers used: last RAR contains the size
					# Street.Fighter.V-RELOADED, Magic.Flute-HI2U
					# Groups: RELOADED, HI2U, 0x0007 and 0x0815
					# 2) crap group that doesn't store the correct size at all:
					# The.Powerpuff.Girls.2016.S01E08.HDTV.x264-QCF
					f.file_size = 0
				f.unicode_filename = block.unicode_filename
				f.orig_filename = block.orig_filename
				f.compression = block.is_compressed()
				if f.compression:
					compression = True
			if block.unpacked_size == 0xffffffff and not f.compression:
				# 2) above int was correct? it must match at the end
				f.file_size += block.packed_size
			if block.unpacked_size != 0xffffffffffffffff and f.file_size == 0:
				# 1) expected the last RAR (first with the proper value)
				f.file_size = block.unpacked_size
			# crc of the file is the crc stored in
			# the last archive that has the file
			f.crc32 = "%08X" % block.file_crc
			archived_files[block.file_name] = f
			
		# new-style Recovery Records
		elif block.rawtype == BlockType.RarNewSub:
			if block.file_name == "RR":
				if not recovery: 
					recovery = FileInfo()
					recovery.file_name = "Protect+"
					recovery.file_size = 0
				recovery.file_size += (512 * block.recovery_sectors +
				                      2 * block.data_sectors)
				assert block.add_size ==  \
					(512 * block.recovery_sectors + 2 * block.data_sectors)
			elif block.file_name == "CMT":
				# The comments themselves are stored after being 
				# compressed with the RAR algorithm. We cannot easily read
				# them compared to old style comment blocks.
				msg = "New style comment block found."
				if _DEBUG: print(msg)
				_fire(MsgCode.CMT, message=msg)

			elif block.file_name == "AV":
				msg = "Authenticity Verification block found."
				if _DEBUG: print(msg)
				_fire(MsgCode.AV, message=msg)
				
			else:
				msg = "Unexpected new-style RAR block. New RAR version?"
				if _DEBUG: print(msg)
				_fire(MsgCode.UNKNOWN, message=msg)
		
		elif block.rawtype == BlockType.RarOldRecovery:
			if not recovery:
				recovery = FileInfo()
				recovery.file_name = "Protect!"
				recovery.file_size = 0
			recovery.file_size += block.add_size
			
			# TODO: fails on 1.Day.2009.Extras.DVDRip.XviD-aAF
#			assert (block.add_size == 
#					512 * block.recovery_sectors + 2 * block.data_sectors)

		elif block.rawtype == BlockType.RarOldAuthenticity76 or  \
			 block.rawtype == BlockType.RarOldAuthenticity79:
			msg = "Old Authenticity block found. (%s)" % hex(block.rawtype)
			if _DEBUG: print(msg)
			_fire(MsgCode.AUTHENTCITY, message=msg)
			
		elif block.rawtype == BlockType.SrrOsoHash:
			if _DEBUG: print("ISDb hash block found.")
			oso_hashes.append(
				(block.file_name, block.oso_hash, block.file_size))
			current_rar = None # end the file size counting
			
		# calculate size of RAR file
		if current_rar:
			if count_size:
				current_rar.file_size += block.header_size + block.add_size
				# not the whole size for the padding block (7 + 4 add size)
				if block.rawtype == BlockType.SrrRarPadding:
					current_rar.file_size -= block.header_size  # - 11
			current_rar.offset_end_rar = (block.block_position + 
			                              block.header_size)
			rar_files[current_rar.key] = current_rar	
	
	def add_info_to_rar(sfv_entry):
		"""Add SFV crc32 hashes to the right RAR info block"""
		key = os.path.basename(sfv_entry.file_name).lower()		  
		rar = rar_files.get(key)
		if rar is not None:
			rar.crc32 = sfv_entry.crc32.upper()
			return True
		return False
	sfv_entries[:] = [e for e in sfv_entries if not add_info_to_rar(e)]
	
	return {"appname": appname, 
	        "stored_files": stored_files,
	        "rar_files": rar_files,
	        "archived_files": archived_files,
	        "recovery": recovery,
	        "sfv_entries": sfv_entries,
	        "sfv_comments": sfv_comments,
	        "compression": compression,
	        "oso_hashes": oso_hashes}

def content_hash(srr_file, algorithm='sha1'):
	"""Returns a Sha1 hash for comparing SRR files.
	
	Has the same behavior as rescene.php: 
	hash is based on the sorted RAR metadata.
	Exact behavior?
	 -> sort on lower case RAR names (no paths)
	Can be used to detect doubles."""
	rar_files = info(srr_file)["rar_files"]
	m = hashlib.new(algorithm)
	with open(srr_file, 'rb') as sfile:
		# sort based on file name without path
		# the difference in capitals is ignored
		for key in sorted(rar_files.keys()):
			start = rar_files[key].offset_start_rar
			try:
				end = rar_files[key].offset_end_rar
				amount = end - start
			except AttributeError:
				amount = -1 # read until EOF
			sfile.seek(start)
			data = sfile.read(amount)
			m.update(data)
	return m.hexdigest()
	
def print_details(file_path):
	"""Prints complete analysis and info to byte level."""
	rr = RarReader(file_path)
	# dict to emulate switch
	ftype = {RarReader.RAR: ("", "RAR"),
	         RarReader.SRR: ("n", "SRR"),
	         RarReader.SFX: ("n", "SFX"), }[rr.file_type()]
	print("The file is a%s %s file." % ftype)
	
	for block in rr.read_all():
		print(block.explain())
		
	srr_hash = content_hash(file_path)
	print("SRR sha1 content hash: %s" % srr_hash)
			
def reconstruct(srr_file, in_folder, out_folder, extract_paths=True, hints={},
				skip_rar_crc=False, auto_locate_renamed=False, empty=False,
				rar_executable_dir=None, tmp_dir=None, extract_files=True,
				srr_part=""):
	"""
	srr_file: SRR file of the archives that need to be rebuild
	in_folder: root folder in which we start looking for the files
	out_folder: location to place the constructed archives
	extract_paths: if paths are stored in the SRR, they will be re-created
	               starting from out_folder
	hints: a dictionary used for handling renamed files
	key: name in original RAR, value: renamed file name on disk
	skip_rar_crc: Disables checking the crc32 values of files and rars while
	              reconstructing. It speeds up the process.
	auto_locate_renamed: if set, start looking in sub folders and guess based
	                     on file size and extension of the file to pack
	empty: will write zero bytes when no file is found
	rar_executable_dir: folder with rar.exe files from -z parameter
	tmp_dir: working directory for compressed RAR reconstruction
	extract_files: if set, extract additional files stored in the srr
	srr_part: string with volume(s) to reconstruct
	"""
	rar_name = ""
	ofile = ""
	source_name = None
	rarfs = None # RAR Volume that is being reconstructed
	srcfs = None # File handle for the stored files
	rebuild_recovery = False
	running_crc = 0  # of bytes used in packaging a single file accross volumes
	compressed_block_encountered = False  # mixed blocks e.g. .PNG file
	
	skip_volume = False # helps to reconstruct a single volume
	skip_offset = 0
	partial_reconstruction = srr_part != "" and srr_part is not None
	partial_set = False
	
	global temp_dir
	temp_dir = tmp_dir
	
	if rar_executable_dir:
		initialize_rar_repository(rar_executable_dir)
		if not repository.count():
			_fire(MsgCode.MSG, message="No RAR executables found.")
			return False
	
	blocks = RarReader(srr_file).read_all()
	for block in blocks:
		_fire(MsgCode.BLOCK, message="RAR Block",
			  type=block.rawtype, size=block.header_size)
		if block.rawtype == BlockType.SrrHeader:
			_flag_check_srr(block)
			# SRR file header block. The only thing here so far is the name 
			# of the application that created the SRR file.
			_fire(MsgCode.MSG, message="SRR file created with %s." % 
				  block.appname)
		elif block.rawtype == BlockType.SrrStoredFile:
			_flag_check_srr(block)
			if extract_files:
				# There is a file stored within the SRR file. Extract it.
				_extract(block, _opath(block, extract_paths, out_folder))
		elif block.rawtype == BlockType.SrrRarFile:
			_flag_check_srr(block)
			
			skip_volume = False # always reset for new volume
			# check whether to re-create the volume
			if partial_reconstruction:
				if not block.file_name.endswith(srr_part):
					skip_volume = True
				
				# extension wildcard is used to reconstruct subset
				if (srr_part.endswith("*") and
				    block.file_name.startswith(srr_part[:-1])):
					skip_volume = False
					partial_set = True

			# We need to create a RAR file for each SRR block.
			# Get the stored name and create it.
			if rar_name != block.file_name and not skip_volume:
				# We use flag 0x1 to mark the files that have their recovery
				# records removed.  All other flags are currently undefined.
				rebuild_recovery = (block.flags &
							SrrRarFileBlock.RECOVERY_BLOCKS_REMOVED) != 0
				rar_name = block.file_name
				try:
					rarfs.close()
				except: pass
				ofile = _opath(block, extract_paths, out_folder)
				if can_overwrite(ofile):
					_fire(MsgCode.MSG, message="Re-creating RAR file: %s" % 
						os.path.basename(ofile))
					if not os.path.isdir(os.path.dirname(ofile)):
						os.makedirs(os.path.dirname(ofile))
					rarfs = open(ofile, "w+b")
				else:
					_fire(MsgCode.USER_ABORTED,
						message="Operation aborted. Archive already exists.")
					return -1
		elif _is_recovery(block) and not skip_volume:
			if block.recovery_sectors > 0 and rebuild_recovery:
				_write_recovery_record(block, rarfs)
			else:
				# The block is from a previous ReScene version (full RR stored)
				# or is not a recovery record. Just copy it.
				rarfs.write(block.block_bytes())
				# TODO: !!! not fully copied?
		elif block.rawtype == BlockType.RarPackedFile:
			if skip_volume:
				# keep track of offsets in the packed file
				if source_name != block.file_name:
					skip_offset = block.packed_size
				else:
					skip_offset += block.packed_size
				
				source_name = block.file_name
				running_crc = 0
				continue

			# This is the main RAR block and treat it differently.
			# We removed the data when storing it, so we need to get 
			# the data back from the extracted file.
			_fire(MsgCode.BLOCK, message="RAR Packed File Block",
				  file_name=block.file_name,
				  packed_size=block.packed_size)
			# write the block contents from the SRR file
			rarfs.write(block.block_bytes())
			
#			if block.packed_size > 0:
			# Make sure we have the correct extracted file open. 
			# If not, attempt to locate and open it.
			if (source_name != block.file_name
				or (partial_reconstruction and not partial_set)
				or (partial_set and source_name != block.file_name)):
				try: srcfs.close()
				except: pass
				source_name = block.file_name
				running_crc = 0
				try:
					# block is a directory: make it not crash
					if block.flags & block.DIRECTORY == block.DIRECTORY:
						srcfs = FakeFile(block.unpacked_size)
					else:
						src = _locate_file(block, in_folder,
										   hints, auto_locate_renamed)
						if block.compression_method != COMPR_STORING:
							_fire(MsgCode.MSG,
								message="Trying to rebuild compressed file %s."
								% block.file_name)
							srcfs = get_rar_data_object(block, blocks, src,
										in_folder, hints, auto_locate_renamed)
							compressed_block_encountered = srcfs
						else:  # uncompressed file
							srcfs = open(src, "rb")
							if compressed_block_encountered:
								global archived_files
								archived_files.setdefault(block.file_name,
									UncompressedRarFile(block, src,
									    compressed_block_encountered))
				except FileNotFound:
					if empty:
						_fire(MsgCode.MSG,
							message="File not found, using fake file.")
						srcfs = FakeFile(block.unpacked_size)
					else:
						raise
			assert srcfs
			
			# make sure the offset is correct
			if partial_reconstruction and not partial_set:
				srcfs.seek(skip_offset)
			
			# then grab the correct amount of data from the extracted file
			running_crc = _repack(block, rarfs, in_folder, srcfs, running_crc, 
			                      skip_rar_crc)
		elif (BlockType.RarMin <= block.rawtype <= BlockType.RarMax or 
			(block.rawtype == 0x00 and block.header_size == 20)): #TODO: test
			if not skip_volume:
				# copy any other RAR blocks to the destination unmodified
				rarfs.write(block.block_bytes())
				# -> P0W4 cleared RAR archive end block: 
				# almost all zeros except for the header size field
			else:
				continue
		elif block.rawtype == BlockType.SrrOsoHash:
			# so no warning message 'unknown block' is shown
			pass
		elif block.rawtype == BlockType.SrrRarPadding:
			if not skip_volume:
				# unknown superfluous bytes in the original volume
				rarfs.write(block.block_bytes()[block.header_size:])
			else:
				continue
		elif block.rawtype == BlockType.SrrZipFile:
			reconstruct_zip(block.zip_data(), in_folder, out_folder, 
				extract_paths, hints, skip_rar_crc, auto_locate_renamed,
				empty, tmp_dir)
		else:
			_fire(MsgCode.UNKNOWN, message="Warning: Unknown block type "
				  "%#x encountered in SRR file, consisting of %d bytes. "
				  "This block will be skipped." % 
				  (block.rawtype, block.header_size))
	if rarfs:
		rarfs.close()
	if srcfs:
		srcfs.close()
		
	temp_folder_cleanup()
	
def reconstruct_zip(zip_metadata, in_folder, out_folder, 
		extract_paths=True, hints={},
		skip_rar_crc=False, auto_locate_renamed=False, empty=False,
		tmp_dir=None):
	stream = io.BytesIO(zip_metadata)
	for zipblock in ZipReader(stream, is_srr=True):
		print(zipblock)


def _write_recovery_record(block, rarfs):
	"""block: original rar recovery block from SRR
	rarfs: partially reconstructed RAR file used for constructing and adding RR
	       an open file handle that will be added to
	
	Either the recovery block or the newsub block is used for recovery
	record data. It consists of two parts: crc's and recovery sectors.
	All file data preceding the recovery record block is protected by 
	the recovery record. That data is broken into sectors of 512 bytes.
	 *  The crc portion of the recovery block is the 2 low-order bytes of 
		the crc32 value for each sector (2 bytes * protected sector count)
	 *  The recovery sectors are created by breaking the data into slices 
		based on the recovery sector count. (512 bytes * recovery sector count)
	Each slice will get one parity sector created by xor-ing the 
	corresponding bytes from all other sectors in the slice."""
	recovery_sectors = block.recovery_sectors
	protected_sectors = block.data_sectors
	_fire(MsgCode.RBLOCK, message="RAR Recovery Block",
		  recovery_sectors=block.recovery_sectors,
		  protected_sectors=block.data_sectors)

	rs_slice = 0
	current_sector = 0	
	crc = [0] * (protected_sectors * 2)
	rs = [0] * recovery_sectors # [0, 0, ..., 0]

	rarfs.seek(0, os.SEEK_END) # move relative to end of file
	rar_length = rarfs.tell()
	assert rar_length != 0 # you can't calculate stuff on nothing
	rarfs.seek(0)
	
	count = 0
	while count < rar_length:
		count += 512
		
		# Read data one sector at a time.  Pad the last sector with 0's.
		sector = rarfs.read(512)
		if len(sector) != 512:
			# Before Python 3, crc32() does not accept a
			# bytearray(), and bytes(int) does not make a string
			# of zeros
			sector += bytes(bytearray(512 - len(sector)))
		# assert len(sector) == 512

		# calculate the crc32 for the sector and store the 2 low-order bytes
		sector_crc = ~zlib.crc32(sector) & 0xffff # Bitwise Inversion
		crc[current_sector*2] = sector_crc & 0xff
		crc[current_sector*2+1] = sector_crc >> 8
		current_sector += 1

		# update the recovery sector parity data for this slice
		rs[rs_slice] ^= int_from_bytes_big(sector)
		rs_slice = rs_slice + 1 if (rs_slice + 1) % recovery_sectors else 0
	# https://lists.ubuntu.com/archives/bazaar/2007q1/023524.html
	rarfs.seek(0, 2) # prevent IOError: [Errno 0] Error on Windows
	
	rarfs.write(block.block_bytes())  # write the backed-up block header,
	rarfs.write(bytearray(crc))	      # CRC data and
	for sector in rs:                 # recovery sectors
		rarfs.write(int_to_bytes_big(sector, 512))

def _locate_file(block, in_folder, hints, auto_locate_renamed):
	"""
	block:	 RarPackedFile that contains info of the file to look for
	in_folder: root folder in which we start looking for the file
	hints:	 dictionary, key -> name of the file in the RAR
	                     value -> name of the file on the hard disk
			   used for handling renamed files
	auto_locate_renamed: if set, start looking in sub folders and guess based
			   on file size and extension
	"""
	# if file has been renamed, use renamed file name
	src = hints.get(block.file_name)
	if src is None:
		src = block.os_file_name()
	src = os.path.abspath(os.path.join(in_folder, src))
	
	if not os.path.isfile(src):
		if auto_locate_renamed:
			src = _auto_locate_renamed(block.os_file_name(),
				block.unpacked_size, in_folder) or src
		if not os.path.isfile(src):
			raise FileNotFound("The file does not exist: %s." % src)
		
	file_size_candidate = os.path.getsize(src)
	if (file_size_candidate != block.unpacked_size and
		block.unpacked_size != 4294967295 and
		block.unpacked_size != 18446744073709551615):
		raise InvalidFileSize("Data file is not the correct size: %s.\n"
			"Found: %d bytes.\nExpected: %d bytes.\n" % 
			(src, os.path.getsize(src), block.unpacked_size))
	elif block.unpacked_size == 4294967295:
		# Edward.Scissorhands.1990.PROPER.1080p.BluRay.x264-PHOBOS
		# The.Apartment.1960.iNTERNAL.BDRip.x264-MARS
		# Pulling.Strings.2013.LIMITED.DVDRiP.X264-TASTE
		print("Probably bad RAR files used. (4294967295 byte archived file)")
		print("Ignoring expected unpacked size for reconstruction.")
		print("Using %s. (%d bytes)" % (os.path.basename(src),
		                                file_size_candidate))
	return src
	
def _auto_locate_renamed(name, size, in_folder):
	"""Tries to find the right file by searching in_folder based on the
	file extension and the file size. 
	Returns empty string when nothing found."""
	# message to user because this could potentially take a while
	_fire(MsgCode.AUTO_LOCATE, message="Auto locate '%s'" % name)
	
	for root, _dirnames, filenames in os.walk(in_folder):
		for fn in fnmatch.filter(filenames, "*" + os.path.splitext(name)[1]):
			f = os.path.join(root, fn)
			if os.path.getsize(f) == size:
				_fire(MsgCode.MSG, message="Trying 'renamed' file: %s" % f)
				return f
	return ""
		
def _repack(block, rarfs, in_folder, srcfs, running_crc, skip_rar_crc):
	"""
	Adds a file to the RAR archive.
	running_crc: CRC of the bytes used in packaging the file
	skip_rar_crc: whether to display CRC warnings
	"""
	bytes_copied_inc = 0
	file_crc = 0  # CRC of the file inside a single RAR volume

	while bytes_copied_inc < block.packed_size:
		# grab the correct amount of data from the extracted file
		bytes_to_copy = block.packed_size - bytes_copied_inc
		if bytes_to_copy > 0x10000: # 64 KiB
			bytes_to_copy = 0x10000
		copy_buffer = srcfs.read(bytes_to_copy)
		rarfs.write(copy_buffer)
		bytes_read = len(copy_buffer)
		
		if not skip_rar_crc: # because it slows the process down
			running_crc = zlib.crc32(copy_buffer, running_crc)
			file_crc = zlib.crc32(copy_buffer, file_crc)

		if bytes_read != bytes_to_copy:
			# If the file didn't have as many bytes as we needed, this file 
			# record was padded. Add null bytes to correct the length.
			# bytes are not used in CRC check - See ReScene .NET 1.2
			rarfs.write(bytearray(bytes_to_copy - bytes_read))
			print("Crappy release group. Adding %d zero bytes." % 
			      (bytes_to_copy - bytes_read))
			
		bytes_copied_inc += bytes_to_copy
	
	if not skip_rar_crc:
		def file_end():
			return block.flags & RarPackedFileBlock.SPLIT_AFTER == 0
		def running_crc_fail():
			return block.file_crc != running_crc & 0xffffffff

		# CRC check of file in the volume (last volume is across all of them)
		if not file_end() and block.file_crc != file_crc & 0xffffffff:
			msg = "CRC mismatch in RAR volume: %s" % rarfs.name
			_fire(MsgCode.CRC, message=msg)
			print("%08x %08x" % (block.file_crc, file_crc & 0xffffffff), 
				  rarfs.name)
		elif file_end() and running_crc_fail() and not block.is_compressed():
			# running_crc is on compressed data, so not applicable there
			msg = "CRC mismatch in file: %s" % block.file_name
			_fire(MsgCode.CRC, message=msg)
			print("%08x %08x" % (block.file_crc, running_crc & 0xffffffff), 
				  block.file_name, rarfs.name)
			
	return running_crc

def _flag_check_srr(block):
	"""Checks whether or not the given block has flags set that are not
	supported by this application."""
	if block.flags & ~block.SUPPORTED_FLAG_MASK: # Bitwise Inversion
		_fire(MsgCode.UNSUPPORTED_FLAG, message="Warning: Unsupported "
			  "flag value encountered in SRR file. This file may use features "
			  "not supported in this version of the application.")
		
def _store(sfile, stream, save_paths, in_folder):
	"""Adds 'file' to the file stream by creating a SrrStoredFileBlock."""
	file_name = os.path.basename(sfile)
	if save_paths:  # AttributeError: 'NoneType' object has no attr...
		try:
			file_name = os.path.relpath(sfile, in_folder)
		except ValueError:
			if os.name == "nt":
				# ValueError: Cannot mix UNC and non-UNC paths
				# the sfile must be a long file name here (.txt from auto)
				file_name = os.path.relpath(sfile, "\\\\?\\" + in_folder)
			else:
				raise  # if this ever throws another valid error here
			
		if file_name[:2] == b"..":
			# sfile and in_folder don't match
			# (long/short Windows path or totally different locations)
			# don't store a path for this file!
			file_name = os.path.basename(sfile)
			msg = "WARNING: No path stored for file: %s"
			_fire(MsgCode.MSG, message=msg % fsunicode(file_name))
	file_name = fsunicode(file_name)
	_fire(MsgCode.STORING, message="Storing file: %s" % file_name)
	
	block = SrrStoredFileBlock(file_name=file_name, 
							   file_size=os.path.getsize(sfile))
#	if save_paths:
#		block.flags |= SrrStoredFileBlock.PATHS_SAVED
	with open(sfile, "rb") as fdata:
		stream.write(block.block_bytes())
		stream.write(fdata.read())
		
def _store_fh(open_file, stream):
	"""Adds 'file' to the file stream by creating a SrrStoredFileBlock."""
	_fire(MsgCode.STORING, message="Storing file: %s" % open_file.name)
	try:
		open_file.seek(0) # has been read before for SFV parsing
		data = open_file.read()
		block = SrrStoredFileBlock(file_name=open_file.name, 
								   file_size=open_file.file_size())
		stream.write(block.block_bytes())
		stream.write(data)
	except Exception as ex:
		# reading data fails, so just skip the file
		print(ex)

def _search(files, folder=""):
	"""Enumerates all files to store. Yields a generator.
	Wildcards are accepted for paths and file names.
	
	files:   list of absolute or relative paths or 
	         paths relative to supplied folder and can contain wildcards
	folder:	 location to search for files when
	         paths are relative in files parameter
	"""
	folder = escape_glob(folder)

	for file_name in files:
		# use path relative to folder if the path isn't relative or absolute 
		if (os.path.isabs(file_name) or file_name.startswith(os.pardir)):
			search_name = file_name
		else:
			search_name = os.path.join(folder, file_name)
		found = False
		
		for found_file in glob(search_name):
			if os.path.isfile(found_file):
				found =  True
				yield found_file
		if not found:
			_fire(MsgCode.FILE_NOT_FOUND, message="File(s) not found: '%s'. "
				  "Continuing with searching for other files." % search_name)

def escape_glob(path):
	# http://bugs.python.org/issue8402
	transdict = {
            '[': '[[]',
            ']': '[]]',
            '*': '[*]',
            '?': '[?]',
            }
	rc = re.compile('|'.join(map(re.escape, transdict)))
	return rc.sub(lambda m: transdict[m.group(0)], path)

def _is_new_recovery(block):
	return block.rawtype == BlockType.RarNewSub and block.is_recovery

def _is_old_recovery(block):
	return block.rawtype == BlockType.RarOldRecovery

def _is_recovery(block):
	return _is_new_recovery(block) or _is_old_recovery(block)
	
class FileInfo(object):
	"""File information object used for returning detailed information. 
	Used in info method and the UI files."""
	def __init__(self):
		self.file_name = ""
		self.file_size = 0
		self.crc = ""
		# usable Unicode name (files in rar archive)
		self.unicode_filename = ""
		self.orig_filename = b""
		# use the same sorting used for the sfv entries
		self.__lt__ = SfvEntry.__lt__
	def __repr__(self): # if possible evaluable representation of an object
		return (repr(self.file_name) + " " + str(self.file_size)
				+ " " + self.crc)

### Compressed RAR stuff ######################################################

RETURNCODE = {
		0: "Successful operation",
		1: "Non fatal error(s) occurred",
		2: "A fatal error occurred",
		3: "A CRC error occurred when unpacking",
		4: "Attempt to modify an archive previously locked by the 'k' command",
		5: "Write to disk error",
		6: "Open file error",
		7: "Command line option error",
		8: "Not enough memory for operation",
		9: "Create file error",
		10: "No files to extract",
		255: "User stopped the process",
	   }

archived_files = {}
repository = None
temp_dir = None
working_temp_dir = None
regular_method_failed = False

class EmptyRepository(Exception):
	"""The RAR repository is empty."""

class RarNotFound(Exception):
	"""No good RAR executable can be found."""
	
def get_temp_directory():
	global temp_dir
	if temp_dir and os.path.isdir(temp_dir):
		return mkdtemp(prefix="SRR-", dir=temp_dir)
	return mkdtemp(prefix="SRR-")

def temp_folder_cleanup():
	"""Temp directory cleanup op the second compressed reconstruction
	method."""
	try:
		if os.path.isdir(working_temp_dir):
			shutil.rmtree(working_temp_dir)
	except TypeError:
		pass
	
def get_rar_data_object(block, blocks, src,
	                    in_folder, hints, auto_locate_renamed):
	rar_object = archived_files.setdefault(block.file_name,
		compressed_rar_file_factory(block, blocks, src, in_folder, hints,
		                            auto_locate_renamed))
	return rar_object

def initialize_rar_repository(location):
	global repository
	repository = RarRepository(location)
	
class RarRepository(object):
	"""Class that manages all Rar.exe files."""
	def __init__(self, bin_folder=None):
		self.rar_executables = []
		if bin_folder:
			self.load_rar_executables(bin_folder)
		else:
			#TODO: try a couple of default paths
			pass
		
	def load_rar_executables(self, bin_folder):
		for rarfile in os.listdir(bin_folder):
			try:
				rarexe = RarExecutable(bin_folder, rarfile)
				self.rar_executables.append(rarexe)
			except ValueError:
				pass
		self.rar_executables.sort()
	
	def get_most_recent_version(self):
		try:
			return self.rar_executables[-1]
		except:
			raise EmptyRepository("No RAR executables found.")
		
	def count(self):
		return len(self.rar_executables)
	
	def get_rar_executables(self, date):
		before = []
		after = []
		previous = []
		for rarexec in self.rar_executables:
			if rarexec.date < date:
				before.append(rarexec)
			else:
				after.append(rarexec)
		#if elements in archived_files, try those versions first!
		if len(archived_files):
			previous = next(iter(archived_files.values()))
			previous = [previous.good_rar]
		before.reverse()
		if len(after):
			# one from after first because of betas that can be in use
			return previous + [after[0]] + before + after[1:]
		else:
			return previous + before

class RarExecutable(object):
	def __init__(self, folder, rar_sfx_file):
		self.folder = folder
		self.file_name = rar_sfx_file
		self.threads = None
		self.args = None
		
		# parse file name
		match = re.match("(?P<date>\d{4}-\d{2}-\d{2})_rar"
		                 "(?P<major>\d)(?P<minor>\d\d)"
		                 "(?P<beta>b\d)?(\.exe)?", rar_sfx_file)
		if match:
			self.date, self.major, self.minor, self.beta = match.group(
				"date", "major", "minor", "beta")
		else:
			raise ValueError("Could not parse file name.")
		
	def path(self):
		return os.path.join(self.folder, self.file_name)
	
	def full(self):
		if self.args:
			return [self.path()] + self.args.arglist() 
		return [self.path()]
	
	def supports_setting_threads(self):
		if self.threads:
			return self.threads
		p = custom_popen([self.path()])
		(stdout, _stderr) = p.communicate()
		self.threads = b"mt<threads>" in stdout
		return self.threads
	
	def max_thread_count(self):
		"""
		Ignores whether or not this version can set threads!
		4.20: Now the allowed <threads> value for -mt<threads> switch is
		1 - 32, not 0 - 16 as before. (also in 4.20 beta 1)
		"""
		if (int(self.major) < 4 or
			int(self.major) == 4 and int(self.minor) < 20):
			return 16
		else:
			return 32
		
	def __lt__(self, other):
		"""
		The sort routines are guaranteed to use __lt__ when making 
		comparisons between two objects.
		"""
		return self.date < other.date
	
	def __str__(self, *args, **kwargs):
		return "%s %s.%s" % (self.date, self.major, self.minor)
		
class RarArguments(object):
	"""
	k             Lock archive
	m<0..5>       Set compression level (0-store...3-default...5-maximal)
	mc<par>       Set advanced compression parameters
	md<size>      Dictionary size in KB (64,128,256,512,1024,2048,4096 or A-G)
	mt<threads>   Set the number of threads
	n@            Read file names to include from stdin
	n@<list>      Include files listed in specified list file
	v<size>[k,b]  Create volumes with size=<size>*1000 [*1024, *1]
	vn            Use the old style volume naming scheme
	vp            Pause before each volume
	
	-sv     Create independent solid volumes
	-sv-    Create dependent solid volumes
	"""
	def __init__(self, block, rar_archive, store_files):
		self.compr_level = block.get_compression_parameter()
		self.dict_size = block.get_dictionary_size_parameter()
		
		self.rar_archive = rar_archive
		if type(store_files) != type([]):
			raise ValueError("Expects a list of files to store.")
		self.store_files = store_files
		self.extra_files_before = []
		self.extra_files_after = []
		self.store_all_files = []
		
		self.set_solid(block.flags & block.SOLID)
		self.set_solid_namesort(False)
		self.threads = ""
		self.split = ""
		self.old_naming_flag = "-vn"
		
	def increase_thread_count(self, rarbin):
		"""Call supports_setting_threads() before calling this method"""
		if self.threads == "":
			self.threads = "-mt1"
			return True
		else:
			current_count = int(self.threads[3:])
			# <threads> parameter can take values from 0 to 16.
			# 4.20: Now the allowed <threads> value for -mt<threads> switch is
			# 1 - 32, not 0 - 16 as before.
			max_threads = multiprocessing.cpu_count() * 2
			mtcount = rarbin.max_thread_count()	
			if max_threads > mtcount:
				max_threads = mtcount 
			if current_count < max_threads:
				self.threads = "-mt%d" % (current_count + 1)
				return True
		return False
	
	def thread_count(self):
		if self.threads == "":
			return 1 # so it won't crash here; see t-670586
		return int(self.threads[3:])
	
	def arglist(self):
		args = list(filter(lambda x: x != '', 
			["a", self.compr_level, self.dict_size, 
			self.solid, self.solid_namesort, self.threads,
			self.old_naming_flag, # old style volume naming scheme
			"-o+", # Overwrite all
			"-ep", # Exclude paths from names.
			"-idcd", # Disable messages: copyright string, "Done" string
			self.split,
			self.rar_archive]))
		if len(self.store_all_files):
#			global working_temp_dir
#			out = os.path.abspath(os.path.join(working_temp_dir, "all_files.txt"))
#			args += ["-n@%s" % out]
#			with open(out, 'w') as all_files:
#				for afile in self.store_all_files:
#					all_files.write(afile + os.linesep)
			for afile in self.store_all_files:
				args.append(afile)
		else:
			args += (self.extra_files_before
					+ self.store_files
					+ self.extra_files_after)
		return args
		
	def set_solid(self, is_set):
		"""
		s[<N>,v[-],e] Create solid archive
		s-            Disable solid archiving
		"""
		if is_set:
			self.solid = "-s"
		else:
			self.solid = "-s-"
	
	def set_split(self, size=None):
		if not size:
			self.split = ""
		else:
			self.split = "-v%db" % size
				
	def set_solid_namesort(self, is_set): #TODO: use while generating
		"""
		ds            Disable name sort for solid archive
		"""
		if is_set:
			self.solid_namesort = ""
		else:
			self.solid_namesort = "-ds"
	
	def reset_extra_files(self):
		self.extra_files_before = []
		self.extra_files_after = []
		
	def set_extra_files_before(self, file_list):
		self.extra_files_before = file_list
		
	def set_extra_files_after(self, file_list):
		self.extra_files_after = file_list

	def set_rar2_flags(self, rar2_detected):
		self.old_naming_flag = "" if rar2_detected else "-vn"
	
def compressed_rar_file_factory(block, blocks, src,
	                            in_folder, hints, auto_locate_renamed):
	global regular_method_failed
	if regular_method_failed:
		regular_method_failed.set_file(block)
		return regular_method_failed
	
	global working_temp_dir
	working_temp_dir = get_temp_directory()
	try:
		blocks_all = blocks
		blocks = get_archived_file_blocks(blocks, block)
		followup = followed_by_solid_block(block, blocks)
		# first block solid archive
		if followup and not block.flags & block.SOLID:
			#TODO: compress all at once and reuse first block
			
			# try to locate the file to archive too
			try:
				followup_src = _locate_file(followup, 
				               in_folder, hints, auto_locate_renamed)
			except FileNotFound:
				if followup.unpacked_size == 0: # a directory or empty file
					followup_src = ""
				else:
					raise
			return CompressedRarFile(block, blocks, src, 
			                         followup, followup_src, solid=True)
			
		if block.flags & block.SOLID:
			# get first file from archive
			if block != blocks[0]:
				if not followup:
					# reuse CompressedRarFile because of the solid archive
					rar = archived_files[blocks[0].file_name]
					rar.set_new(src, block)
					return rar
				else:
					followup_src = _locate_file(followup, 
					                   in_folder, hints, auto_locate_renamed)
					# reuse CompressedRarFile because of the solid archive
					rar = archived_files[blocks[0].file_name]
					rar.set_new(src, block, followup_src)
					return rar
		
		nblock = next_block(block, blocks)
		if nblock:
			try:
				followup_src = _locate_file(nblock, 
				                   in_folder, hints, auto_locate_renamed)
			except FileNotFound:
				followup_src = ""
		else:
			followup_src = "" 
	
		return CompressedRarFile(block, blocks, src,
		                         nblock, followup_src, solid=False)
	except (RarNotFound, ValueError) as ex:
		print(ex)
		# we have found good RAR versions before
		if len(archived_files) != 0:
			regular_method_failed = CompressedRarFileAll(
				blocks, block, blocks_all,
				(in_folder, hints, auto_locate_renamed))
			return regular_method_failed
		else:
			raise

def followed_by_solid_block(block, blocks):
	start = False
	for bl in blocks:
		if bl == block:
			start = True
			continue
		if start:
			if bl.flags & block.SOLID:
				return bl
			else:
				break
	return False

def next_block(block, blocks):
	start = False
	for bl in blocks:
		if bl == block:
			start = True
			continue
		if start:
			return bl
	return None

def previous_block(block, blocks):
	start = None
	for bl in blocks:
		if bl == block:
			if start is None:
				return block
			else:
				return start
		start = bl
	return block 
	
def get_archived_file_blocks(blocks, current_block):
	"""
	Out of all the blocks, only those RAR file blocks part of 
	the current archive are returned.
	"""
	result = []
	current_set = ""
	set_current_block = ""
	
	for block in blocks:
		if block == current_block:
			set_current_block = current_set
		if block.rawtype == BlockType.RarPackedFile:
			result.append(block)
			
		# get the sets from the SrrRarFile blocks
		if block.rawtype == BlockType.SrrRarFile:
			nset = get_set(block)
			if nset != current_set:
				if not set_current_block:
					current_set = nset
					result = []
				elif set_current_block:
					break
	return result

def get_set(srr_rar_block):	
	"""
	An SRR file can contain re-creation data of different RAR sets.
	This function tries to pick the basename of such a set.
	"""
	n = srr_rar_block.file_name[:-4]
	match = re.match("(.*)\.part\d*$", n, re.I)
	if match:
		return match.group(1)
	else:
		return n

def get_full_packed_size(block, blocks):
	result_size = 0
	for lego in blocks:
		if lego.file_name == block.file_name:
			result_size += lego.packed_size
		elif result_size:
			break
	return result_size

class CompressedRarFile(io.IOBase):
	"""Represents compressed RAR data."""
	def __init__(self, first_block, blocks, src, 
				next_block=None, next_src=None, solid=False):
		"""blocks are only RarPackedFile blocks from the current set
		solid: if it's a solid archive. (the first block isn't solid)"""
		self.current_block = first_block
		self.blocks = blocks
		self.source_files = [src]
		if solid:
			self.source_files.append(next_src)
		self.date = self.get_most_recent_date()
		self.COMPRESSED_NAME = "pyReScene_compressed.rar"
		self.solid = solid 
		
		global working_temp_dir
		self.temp_dir = working_temp_dir
		
		# make sure there is a RarRepository
		global repository
		if not repository:
			repository = RarRepository()
			
		# set a minimum thread count to start with based on previous runs
		# should make it a little bit faster too
		thread_count = ""
		for _key, value in archived_files.items():
			if value.good_rar.args.threads > thread_count:
				thread_count = value.good_rar.args.threads 
		
		# search the correct RAR executable
		self.good_rar = self.search_matching_rar_executable(
			first_block, blocks, thread_count)
		
		
		# try again with the next (previous) files added too
		if not self.good_rar and next_block and not solid:
			self.source_files.append(next_src)
			self.good_rar = self.search_matching_rar_executable(first_block, 
				blocks, thread_count, more_files=True)
			
		
		#TODO: to reconstruct succesfully, it probably needs to have the
		# next 'window size' of file data
		# link 'blocks' objects
		
		if not self.good_rar:
			# the directory can still have the .r00,... files
			try:
				#os.rmdir(self.temp_dir)
				shutil.rmtree(self.temp_dir)
			except:
				print("Failure to remove temp dir: %s" % self.temp_dir)
			raise RarNotFound("No good RAR version found.")
		_fire(MsgCode.MSG, message=
			"Good RAR version detected: %s" % self.good_rar)
		
		# determine volume size
		# volumes are needed when there is compression failure
		# e.g. Max.Payne.3-RELOADED
		# WinRAR prevents this if it's only one archive, but not with volumes
		packed_size = get_full_packed_size(first_block, blocks)
		if (first_block.unpacked_size < packed_size):
			x = int(packed_size // 2 * 1.1)
			if x > 4000000000: # FAT32 support
				x = 2000000000
			self.good_rar.args.set_split(x)
		# TODO: what about the detection code? works for example though
		
		self.good_rar.args.store_files = self.source_files
		self.good_rar.args.set_solid(self.solid)
		_fire(MsgCode.MSG, message=" ".join(self.good_rar.full()))
		_fire(MsgCode.MSG, message="Compressing %s..." % os.path.basename(src))
		time.sleep(0.5)
		compress = subprocess.Popen(self.good_rar.full())
		compress.communicate()
		
		if compress.returncode != 0:
			_fire(MsgCode.MSG, 
				message="Something went wrong executing Rar.exe:")
			_fire(MsgCode.MSG, message=RETURNCODE[compress.returncode])
			
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		try:
			self.rarstream = RarStream(out, compressed=True, 
				packed_file_name=os.path.basename(first_block.file_name))
		except AttributeError:
			# -r parameter is used to find the file to compress
			# that renamed file is inside the RAR
			# we "don't know" the packed file name; try the first file
			self.rarstream = RarStream(out, compressed=True)
			
		self.rarstream.seek(0, os.SEEK_END)
		size = self.rarstream.tell()
		self.rarstream.seek(0, os.SEEK_SET)
		
		if size != get_full_packed_size(first_block, blocks):
			print(size)
			print(get_full_packed_size(first_block, blocks))
			self.close()
			raise ValueError("Still not fine :(.")

	def search_matching_rar_executable(self, block, blocks, 
			thread_count, more_files=False):
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		if len(block.file_name) > 2:
			piece = os.path.join(self.temp_dir, "pyReScene_data_piece." + 
							block.file_name[-3:])
		else:
			piece = os.path.join(self.temp_dir, "pyReScene_data_piece.bin")
		
		# only compress enough data that is compressed 
		# larger than the amount we need
		# we need the size of the whole file compressed
		size_compr = get_full_packed_size(block, blocks)
		size_full = block.unpacked_size
#		assert size_full == os.path.getsize(self.source_files[-1])
		size_min = block.packed_size
		
		# RELOADED custom RAR packer: figure out correct file size
		if (block.unpacked_size == 0xffffffffffffffff):
			srr_file = block.fname
			archived = info(srr_file)["archived_files"]
			size_full = archived[block.file_name].file_size
		
		def get_previous_block():
			previous = None
			for lego in blocks:
				if lego == block:
					return previous
				previous = lego
			return None
		
		# Rar 2.0x version don't have a CRC stored, only at the end
		# do the complete file
		if block.file_crc == 0xFFFFFFFF:
			args = RarArguments(block, out, [self.source_files[0]])
			old = True
		else:
			old = False
			args = RarArguments(block, out, [piece])
		
			_fire(MsgCode.MSG, message=
				"Grabbing large enough data piece size for testing.")
			# we assume that newer versions always compress better
			rarexe = repository.get_most_recent_version()
			args.set_rar2_flags(re.search(r'_rar2', rarexe.path()) is not None)
			
			window_size = block.get_dict_size()
			amount = 0
			# start with 2% increase of the ratio
			for i in list(range(2, 100, 5)):
				increase = (size_full / size_compr) + (i / 100)
				amount = min(size_full, int(size_min * increase) + window_size)
				
				# copy bytes from source to destination
				copy_data(self.source_files[0], piece, amount)
				
				if amount == size_full:
					break
				
				proc = custom_popen([rarexe.path()] + args.arglist())
				(stdout, _) = proc.communicate()
				
				if proc.returncode != 0:
					stdout = decodetext(stdout, errors="replace")
					print(encodeerrors(stdout, sys.stdout))
					_fire(MsgCode.MSG, message=
						"Something went wrong executing Rar.exe:")
					_fire(MsgCode.MSG, message=RETURNCODE[proc.returncode])
			
				# check compressed size
				rarblocks = RarReader(out)
				for lego in rarblocks:
					if lego.rawtype == BlockType.RarPackedFile:
						size = lego.packed_size
						break
				rarblocks.close()
				os.unlink(out)
				
				if size >= size_min:
					break
			assert os.path.isfile(piece)
			assert not os.path.isfile(out)
		
		if more_files:
			#TODO: only use 4MiB here (maximum dictionary size RAR4)
			args.set_extra_files_after([self.source_files[1]])
		
		#TODO: use?
#		# based on previous runs
#		args.threads = thread_count
			
		def try_rar_executable(rar, args, old=False):
			compress = custom_popen([rar.path()] + args.arglist())
			stdout, _ = compress.communicate()
			
			if compress.returncode != 0:
				stdout = decodetext(stdout, errors="replace")
				print(encodeerrors(stdout, sys.stdout))
				_fire(MsgCode.MSG, message=
					"Something went wrong executing Rar.exe:")
				_fire(MsgCode.MSG, message=RETURNCODE[compress.returncode])

			# check if this is a good RAR version
			start = size_min
			ps = crc = 0
			with RarStream(out, compressed=True,
						packed_file_name=os.path.basename(piece)) as rs:
				if old:
					start = rs.length()
#				print("Compressed: %d" % rs.length())
#				print("Expected: %d" % start)
				if start > rs.length():
					# it compressed better than we need
					# crc check would fail
					crc = -1
				elif start == rs.length():
					# RAR already calculated crc for us
					# not sure if CRC is correct for small files because the
					# last stored CRC value is that from the extracted data
					rr = RarReader(out)
					if old:
						for bl in rr:
							if (bl.rawtype == BlockType.RarPackedFile
							and 0xFFFFFFFF != bl.file_crc):
								crc = bl.file_crc
								ps = bl.packed_size # works because one big RAR
								break
					else:
						for bl in rr:
							if bl.rawtype == BlockType.RarPackedFile:
								crc = bl.file_crc
								break
					rr.close()
				else:
					# we do the crc calculation ourselves
					assert rs.length() > start
	
					bufsize = 8*1024
					while start > 0:
						if start - bufsize > 0:
							readsize = bufsize
							start -= bufsize
						else:
							readsize = start
							start = 0
						crc = zlib.crc32(rs.read(readsize), crc)
			
			os.remove(out)
			try:
				os.remove(out[:-4] + ".r00")
			except:
				pass
			
			if crc & 0xFFFFFFFF == block.file_crc:
				return True
			if block.file_crc == 0xFFFFFFFF: # old RAR versions
				# CRC of file is stored in the last block
				for bl in blocks:
					if (bl.rawtype == BlockType.RarPackedFile
						and bl.file_name == block.file_name 
						and crc & 0xFFFFFFFF == bl.file_crc
						and size_compr == ps):
						return True
			return False
		
		# do not split when WinRAR didn't do it either
		if os.path.getsize(piece) != size_full:
			args.set_split(int(os.path.getsize(piece) * 0.6))
			
		for rar in repository.get_rar_executables(self.get_most_recent_date()):
			_fire(MsgCode.MSG, message="Trying %s." % rar)
			args.set_rar2_flags(re.search(r'_rar2', rar.path()) is not None)
			found = False
			if rar.supports_setting_threads():
				while args.increase_thread_count(rar):
					if try_rar_executable(rar, args, old):
						found = True
						break
			else:
				found = try_rar_executable(rar, args, old)
			if found:
				rar.args = args
				return rar
			args.threads = ""
			
			# we've done files before
			if len(archived_files) >= 1:
				print("Testing with previous file")
				# try compressing with the previous rar file before it
				prev = get_previous_block()
				if prev:
					prev_file = archived_files[prev.file_name]
					
					args.set_extra_files_before([prev_file.source_files[-1]])
					
					if rar.supports_setting_threads():
						while args.increase_thread_count(rar):
							if try_rar_executable(rar, args, old):
								found = True
								break
					else:
						found = try_rar_executable(rar, args, old)
					if found:
						rar.args = args
						return rar

			args.reset_extra_files()			
			args.threads = ""
		os.remove(piece)
	
	def set_new(self, source_file, block, followup_src=None):
		"""when solid, it can occur that the first file needs the second
		too (last bit can be different)"""
		# rar filters out same ones
		self.source_files.append(source_file)
		if followup_src:
			self.source_files.append(followup_src)
		self.current_block = block
		os.mkdir(self.temp_dir)
		
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		
		_fire(MsgCode.MSG, message=
			"Compressing %s..." % os.path.basename(self.source_files[-1]))
		self.good_rar.args.source_files = self.source_files
		self.good_rar.args.set_solid(block.flags & block.SOLID)
		
		def compress():
			time.sleep(0.5)
			compress = subprocess.Popen(self.good_rar.full())
			compress.communicate()
			
			if compress.returncode != 0:
				_fire(MsgCode.MSG, message=
					"Something went wrong executing Rar.exe:")
				_fire(MsgCode.MSG, message=
					RETURNCODE[compress.returncode])
	
			self.rarstream = RarStream(out, compressed=True,
				packed_file_name=os.path.basename(self.source_files[-1]))
		compress()
		
		# this happens with solid archives when the first file is small
		# an .idx file is detected as having -mt1, but the .sub file can
		# need 4 threads
		if self.rarstream.length() != block.packed_size:
			_fire(MsgCode.MSG, message="Solid archive recompression.")
			while(self.rarstream.length() != block.packed_size and
				self.good_rar.supports_setting_threads() and
				self.good_rar.args.increase_thread_count(self.good_rar)):
				compress()
			
		if self.rarstream.length() != block.packed_size:
			raise ValueError("Something isn't right yet.")
		
	def get_most_recent_date(self):
		most_recent_date = "1970-01-01"
		for block in self.blocks:
			if block.rawtype == BlockType.RarPackedFile:
				for date in (block.file_datetime, block.atime, block.mtime,
				             block.ctime, block.arctime):
					if date is not None:
						t = ("%d-%02d-%02d" % (date[0], date[1], date[2]))
						if t > most_recent_date:
							most_recent_date = t
		return most_recent_date	

	def length(self):
		"""Length of the packed file being accessed."""
		return self.rarstream.length()
	
	def tell(self):
		"""Return the current stream position."""
		return self.rarstream.tell()
	
	def readable(self):
		"""Return True if the stream can be read from. 
		If False, read() will raise IOError."""
		return not self.rarstream.closed()
	def seekable(self):
		"""Return True if the stream supports random access. 
		If False, seek(), tell() and truncate() will raise IOError."""
		return not self.rarstream.closed()
	
	def close(self):
		"""Flush and close this stream. Disable all I/O operations. 
		This method has no effect if the file is already closed. 
		Once the file is closed, any operation on the file 
		(e.g. reading or writing) will raise a ValueError.

		As a convenience, it is allowed to call this method more than once; 
		only the first call, however, will have an effect."""
		self.rarstream.close()
		shutil.rmtree(self.temp_dir)
		
	@property
	def closed(self):
		"""closed: bool.  True iff the file has been closed.

		For backwards compatibility, this is a property, not a predicate.
		"""
		return self.rarstream.closed()
	
	def seek(self, offset, origin=0):
		"""
		Change the stream position to the given byte offset. offset is 
		interpreted relative to the position indicated by origin. 
		Values for whence are:
	
			* SEEK_SET or 0 - start of the stream (the default); 
							  offset should be zero or positive
			* SEEK_CUR or 1 - current stream position; offset may be negative
			* SEEK_END or 2 - end of the stream; offset is usually negative
	
		Return the new absolute position.
		"""
		self.rarstream.seek(offset, origin)
	
	def read(self, size=-1):
		"""
		read([size]) 
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Return an empty string at EOF.
			
		size > self.length(): EOFError
		"""
		return self.rarstream.read(size)
	
	def readinto(self, byte_array):
		"""
		 |  readinto(...)
		 |	  readinto(bytearray) -> int.  Read up to len(b) bytes into b.
		 |	  
		 |	  Returns number of bytes read (0 for EOF), or None if the object
		 |	  is set not to block as has no data to read.
		 class io.RawIOBase
		 
		 readinto(b)
			Read up to len(b) bytes into bytearray b and return 
			the number of bytes read. If the object is in non-blocking mode 
			and no bytes are available, None is returned.
		"""
		return self.rarstream.readinto(byte_array)
	
def calculate_size_volume(blocks):
	"""Calculates the size of the first volume."""
	size = 0
	for block in blocks:
		if block.rawtype == BlockType.RarMin and size != 0:
			return size # when there is no archive end block
		elif block.rawtype == BlockType.RarMax:
			size += block.header_size
			return size
		elif block.rawtype in (BlockType.SrrHeader, BlockType.SrrStoredFile,
		                       BlockType.SrrRarFile, BlockType.SrrOsoHash):
			continue
		else:
			size += block.header_size
			size += block.add_size
	return size

class CompressedRarFileAll(io.IOBase):
	"""Represents compressed RAR data of all the files."""
	
	def __init__(self, blocks, block, all_blocks, search_options):
		"""blocks: all the file blocks for this RAR set
		block: the current file that has to be read
		all_blocks: all the blocks of the SRR"""
		self.blocks = blocks
		self.current_block = block
		self.COMPRESSED_NAME = "pyReScene_method2.rar"
		self.rarstream = None
		
		global working_temp_dir
		working_temp_dir = get_temp_directory()
		self.temp_dir = working_temp_dir
		
		# try grabbing the volume size from blocks
		volume = calculate_size_volume(all_blocks)
		
		assert len(archived_files) != 0
		
		# create archive with all the files based on last found good version
		good_version = previous_block(block, blocks)
		try:
			rar_settings = archived_files[good_version.file_name].good_rar
		except KeyError:
			for _key, value in archived_files.items():
				rar_settings = value.good_rar
				break
		# pick one of the files with the highest thread count
		for _key, value in archived_files.items():
			if (value.good_rar.args.thread_count() > 
				rar_settings.args.thread_count()):
				rar_settings = value.good_rar
		
		rar_settings.args.set_split(volume)
		rar_settings.args.rar_archive = os.path.join(self.temp_dir, 
		                                             self.COMPRESSED_NAME)
		for block in blocks:
			if block.packed_size != 0: # files and no directories
				rar_settings.args.store_all_files.append(
					_locate_file(block, *search_options))
		self.good_rar = rar_settings
		
		self.compress_files()
		
		self.set_file(self.current_block)
		
	def compress_files(self):
		_fire(MsgCode.MSG, message=" ".join(self.good_rar.full()))
		_fire(MsgCode.MSG, message="Compressing ALL files.")
		time.sleep(0.5)
		print("Command length: %d" % len(self.good_rar.full()))
		compress = subprocess.Popen(self.good_rar.full())
		compress.communicate()
		
		if compress.returncode != 0:
			_fire(MsgCode.MSG, 
				message="Something went wrong executing Rar.exe:")
			_fire(MsgCode.MSG, message=RETURNCODE[compress.returncode])
	
	def set_file(self, block):
		"""Sets the current file that must be served to the algorithm."""
		self.current_block = block
		try:
			self.rarstream.close()
		except:
			pass
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		# otherwise AttributeError: File not found in the archive.
		if not (block.flags & RarPackedFileBlock.DIRECTORY 
		    == RarPackedFileBlock.DIRECTORY):
			self.rarstream = RarStream(out, compressed=True, 
				packed_file_name=os.path.basename(block.file_name))
			self.rarstream.seek(0, os.SEEK_END)
			# test if file size match, otherwise try compressing again
			if get_full_packed_size(block, 
				self.blocks) != self.rarstream.tell():
				self.try_again(block)
			else:
				self.rarstream.seek(0, os.SEEK_SET)
		else:
			self.rarstream = FakeFile(block.packed_size)
		
	def try_again(self, block):
		# keep trying again with higher thread count
		if (self.good_rar.supports_setting_threads() and 
			self.good_rar.args.increase_thread_count(self.good_rar)):
			empty_folder(self.temp_dir)
			self.compress_files()
			self.set_file(block)
		else:
			shutil.rmtree(self.temp_dir)
			raise RarNotFound("Our options are exhausted.")

	def length(self):
		"""Length of the packed file being accessed."""
		return self.rarstream.length()
	
	def tell(self):
		"""Return the current stream position."""
		return self.rarstream.tell()
	
	def readable(self):
		"""Return True if the stream can be read from. 
		If False, read() will raise IOError."""
		return not self.rarstream.closed()
	def seekable(self):
		"""Return True if the stream supports random access. 
		If False, seek(), tell() and truncate() will raise IOError."""
		return not self.rarstream.closed()
	
	def close(self):
		"""Flush and close this stream. Disable all I/O operations. 
		This method has no effect if the file is already closed. 
		Once the file is closed, any operation on the file 
		(e.g. reading or writing) will raise a ValueError.

		As a convenience, it is allowed to call this method more than once; 
		only the first call, however, will have an effect."""
		self.rarstream.close()
		# cleanup of temp dir in separate function
		
	@property
	def closed(self):
		"""closed: bool.  True iff the file has been closed.

		For backwards compatibility, this is a property, not a predicate.
		"""
		return self.rarstream.closed()
	
	def seek(self, offset, origin=0):
		"""
		Change the stream position to the given byte offset. offset is 
		interpreted relative to the position indicated by origin. 
		Values for whence are:
	
			* SEEK_SET or 0 - start of the stream (the default); 
							  offset should be zero or positive
			* SEEK_CUR or 1 - current stream position; offset may be negative
			* SEEK_END or 2 - end of the stream; offset is usually negative
	
		Return the new absolute position.
		"""
		self.rarstream.seek(offset, origin)
	
	def read(self, size=-1):
		"""
		read([size]) 
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Return an empty string at EOF.
			
		size > self.length(): EOFError
		"""
		return self.rarstream.read(size)
	
	def readinto(self, byte_array):
		"""
		 |  readinto(...)
		 |	  readinto(bytearray) -> int.  Read up to len(b) bytes into b.
		 |	  
		 |	  Returns number of bytes read (0 for EOF), or None if the object
		 |	  is set not to block as has no data to read.
		 class io.RawIOBase
		 
		 readinto(b)
			Read up to len(b) bytes into bytearray b and return 
			the number of bytes read. If the object is in non-blocking mode 
			and no bytes are available, None is returned.
		"""
		return self.rarstream.readinto(byte_array)

class UncompressedRarFile(io.IOBase):
	"""Represents uncompressed RAR data in a compressed archive."""

	def __init__(self, block, source_files, prev_compressed):
		self.current_block = block
		self.source_files = [source_files]
		self.good_rar = prev_compressed.good_rar
	
def custom_popen(cmd):
	"""disconnect cmd from parent fds, read only from stdout"""
	
	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000 # CREATE_NO_WINDOW

	# run command
	if _DEBUG: print(" ".join(cmd))
	return subprocess.Popen(cmd, bufsize=0, stdout=subprocess.PIPE, 
	                        stdin=subprocess.PIPE, stderr=subprocess.STDOUT, 
	                        creationflags=creationflags)
	
def copy_data(source_file, destination_file, offset_amount):
	with open(source_file, 'rb') as source:
		with open(destination_file, 'wb') as destination:
			destination.write(source.read(offset_amount))

