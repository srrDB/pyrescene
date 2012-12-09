#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011-2012 pyReScene
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
	absolute_import)

from tempfile import mkstemp
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

import rescene
from rescene.rar import (BlockType, RarReader,
	SrrStoredFileBlock, SrrRarFileBlock, SrrHeaderBlock, COMPR_STORING, 
	RarPackedFileBlock, _DEBUG)
from rescene.rarstream import RarStream, FakeFile
from rescene.utility import (SfvEntry, is_rar, parse_sfv_file, 
                             first_rars, next_archive)

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behavior
	range = xrange #@ReservedAssignment
	# py2.6 has broken bytes()
	def bytes(foo, enc): #@ReservedAssignment
		return str(foo)

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

def can_overwrite(file_path):
	"""Method must be wrapped in the application to ask what to do. 
		Returns False when file exists.
		Returns True when file does not exist."""
	if _DEBUG:
		print("check overwrite: %s (%s)" %
	          (file_path, not os.path.isfile(file_path)))
	return not os.path.isfile(file_path)

def change_rescene_name_version(new_name):
	if not isinstance(new_name, str):
		raise AttributeError("ReScene name must be a string.")
	if len(new_name) > 0xFFF6:
		raise AttributeError("Application name too long.")
	rescene.APPNAME = new_name

def extract_files(srr_file, out_folder, extract_paths=True, packed_name=""):
	"""
	If packed_name is given, 
		we only try to extract all files with that name.
		(It is possible for an SRR file to have a file with the same name
		if they have different paths.)
		If it is a relative path, we only extract a single file.
	If extract_paths is True, 
		we try to recreate the file with its stored path.
	"""
	extracted_files = []
	def process(block):
		"""Process SrrStoredFileBlocks by deciding whether to extract the
		packed file or not: write each file if no name is specified or only
		those whose path/name matches. (only name if no path is specified)"""
		out_file = _opath(block, extract_paths, out_folder)
		if not packed_name or packed_name ==  \
			os.path.basename(packed_name) == os.path.basename(out_file) or  \
			os.path.normpath(packed_name) == os.path.normpath(block.file_name):
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
	file_name = os.path.normpath(block.file_name)  \
				if extract_paths else os.path.basename(block.file_name)
	return os.path.join(os.path.normpath(out_folder), file_name)

def _extract(block, out_file):
	"""Extracts contents of SrrStoredFileBlock to out_file
	after checking it can overwrite it if necessary.
	The block must match the srr_file."""
	if can_overwrite(out_file):
		msg = "Recreating stored file: %s" % block.file_name
		if _DEBUG: print(msg)
		_fire(MsgCode.MSG, message=msg)
		# IOError: [Errno 2] No such file or directory: 
		# '..\\test_files\\store_little\\' +
		# 'store_little/store_little.srr' -> create path
		try:
			os.makedirs(os.path.dirname(out_file))
		except BaseException: # WindowsError: [Error 183]
			# cannot create dir because folder(s) already exist
			ex = sys.exc_info()[1]
			if _DEBUG: print(ex)
			_fire(MsgCode.OS_ERROR, message=ex)
		# what error when we cannot create path? XXX: Subs vs subs
		# that already exists -> LINUX
		with open(out_file, "wb") as out_stream:
			out_stream.write(block.srr_data())
		return True
	else: # User cancelled the file extraction
		_fire(MsgCode.NO_OVERWRITE, 
		      message="Overwrite operation aborted for %s" % out_file)
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
	rr = RarReader(srr_file) # ArchiveNotFoundError
	if rr.file_type() != RarReader.SRR:
		raise NotSrrFile("Not an SRR file.")
	
	if _DEBUG: print("Checking for dupes before adding files.")
	for block in rr.read_all():
		if block.rawtype == BlockType.SrrStoredFile:
			if block.file_name in store_files:
				msg = "There already is a file with the same name stored."
				_fire(MsgCode.DUPE, message=msg)
				if usenet:
					# don't try to add dupes and keep working quietly
					store_files.remove(block.file_name)
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
	except:
		print(sys.exc_info()[1])
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
	"""Merge the given list of srr_files together.
	srr_files:        list of SRR files to merge (including the path)
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
			#TODO: this is skipping data in some less common casess?

def create_srr(srr_name, infiles, in_folder="",
               store_files=None, save_paths=False, compressed=False):
	"""
	infiles:     RAR or SFV file(s) to create SRR from
	store_files: a list of files to store in the SRR
	             SFVs from infiles do not need to be in this list.
	in_folder:   root folder for relative paths to store
	             necessary when save_paths is True or
	             paths are relative to in_folder in store_file
	srr_name:    path and name of the SRR file to create
	save_paths:  if the path relative to in_folder 
	             must be stored with the file name e.g. Sample/ or Proof/
				 
	Raises ValueError if rars in infiles are not the first of the archives.
	"""
	if store_files is None:      # no default initialisation with []
		store_files = []
	if not isinstance(infiles, (list, tuple)): # we need a list
		infiles = [infiles]      # otherwise iterating over characters
		
	if not can_overwrite(srr_name):
		raise EnvironmentError("Can't overwrite SRR file.")
	
	srr = open(srr_name, "wb")
	srr.write(SrrHeaderBlock(appname=rescene.APPNAME).block_bytes())
	
	try:
		# STORE FILES
		# We store copies of any files included in the store_files list 
		# in the .srr using a "store block".
		# Any SFV files used are also included.
		store_files.extend([f for f in infiles if f[-4:].lower() == ".sfv"])
		
		if not len([_store(f, srr, save_paths, in_folder)
					for f in _search(store_files, in_folder)]):
			_fire(MsgCode.NO_FILES, message="No files found to add.")
		
		# COLLECT ARCHIVES
		rarfiles = []
		for infile in infiles:
			if infile[-4:].lower() == ".sfv":
				rarfiles.extend(_handle_sfv(infile))
			else:
				rarfiles.extend(_handle_rar(infile))
	
		# STORE ARCHIVE BLOCKS
		for rarfile in rarfiles:
			if not os.path.isfile(rarfile):
				_fire(code=MsgCode.FILE_NOT_FOUND,
					  message="Referenced file not found: %s" % rarfile)
				srr.close()	  
				os.unlink(srr_name)
				raise FileNotFound("Referenced file not found: %s" % rarfile)
	
			fname = os.path.relpath(rarfile, in_folder) if save_paths  \
				else os.path.basename(rarfile)
			_fire(MsgCode.MSG, message="Processing file: %s." % fname)
			
			rarblock = SrrRarFileBlock(file_name=fname)
	#		if save_paths:
	#			rarblock.flags |= SrrRarFileBlock.PATHS_SAVED
			srr.write(rarblock.block_bytes())
			
			rr = RarReader(rarfile)
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
							os.unlink(srr_name)
							raise ValueError("Archive uses unsupported "
							           "compression method: %s" % rarfile)
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
	finally:
		# when an IOError is raised, we close the file for further cleanup
		srr.close()

def _rarreader_usenet(rarfile, read_retries=7):
	"""Tries redownloading data read_retries times if it fails.
	Regular RarReader, but handles Usenet exceptions and retries."""
	rr = RarReader(rarfile)
	try:
		return rr.read_all()
	except (EnvironmentError, IndexError, nntplib.NNTPTemporaryError):
		# IndexError: Offset after end of file.
		# EnvironmentError: Invalid RAR block length (9728) at offset 0xe4e1b3
		# EnvironmentError: Invalid RAR block length (0) at offset 0xe4e1b1
		#	(banana_joe.cd2.part46.rar) Banana.Joe.XViD-HRG-CD1
		print("Parsing RAR file failed. Trying again a couple of times.")
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
			except (EnvironmentError, IndexError, nntplib.NNTPTemporaryError):
				print(sys.exc_info())
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
	virtual source. e.g. Usenet"""
	"""
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
			if infile[-4:].lower() == ".sfv":
#				try:
				rarfiles.extend(_handle_sfv(infile))
					# pointer SFV has changed!
#				except:
#					# NNTPTemporaryError('430 No such article',)
#					print(sys.exc_info())
#					raise ValueError("SFV file can't be read.")
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
				try:
					allfiles[rarfile]
				except KeyError:
					# try again because the rars could have capitals while it
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
			_fire(MsgCode.NO_FILES, message="No files found to add.")

		# STORE ARCHIVE BLOCKS ------------------------------------------------
		end_segments_tested = False
		has_end_segment = False
		
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
			_fire(MsgCode.MSG, message="Processing file: %s." % rarfile.name)
			
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
				srr.write(block.block_bytes());
				
				#TODO: when starting from RARs, detect when incomplete!!!!
	
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
	"""Helper function for create_srr that yields all RAR archives enumerated
	in a .sfv file."""
	for sfv_entry in sorted(parse_sfv_file(sfile)[0]):
		if is_rar(sfv_entry.file_name):
			yield os.path.join(os.path.dirname(sfile), sfv_entry.file_name)
		else:
			_fire(MsgCode.NO_RAR, message="Warning: Non-RAR file found "
				  "as SFV: '%s'." % sfv_entry.file_name)


def _handle_rar(rfile, filelist=None, read_retries=7):
	"""Helper function for create_srr that yields all existing RAR archives
	based on the first RAR. Archive naming is standardised: 
	no need to read each file yet. Checking for existence is enough. 
	
	filelist: list check if specified instead of HD check (Usenet)"""
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
		
	# is this part necessary? just test on file name
#	#rr = RarReader(rfile) # closes the file -> was problem with NNTPFiles
#	for block in _rarreader_usenet(rfile, read_retries):
#		if block.rawtype == BlockType.RarVolumeHeader and \
#			(block.flags & rar.RarVolumeHeaderBlock.VOLUME):
#			# Rar file is part of multiple volumes. Figure out whether this is
#			# the first volume based on file name because some rars aren't
#			# packed with (Win)Rar and always set the MHD_FIRSTVOLUME flag.
#			# This flag is set only by RAR 3.0 and later on the first volume.
#			#  -> ASAP and IMMERSE always set the first volume flag!
#			#      e.g.  Game.of.Thrones.S01E07.HDTV.XviD-ASAP
#			#            House.S06E12.720p.HDTV.x264-IMMERSE			
#			#  -> RARFileSource version 0.9.2, released 2011-02-22
#			#     is not able to start playing from .r00
#			#  -> VLC 1.1 complains about broken files:
#			#     ASAP, FQM
#			if (not block.flags & rar.RarVolumeHeaderBlock.FIRST_VOLUME
#			    and utility.first_rars([rfile])):
#				raise ValueError("You must start with the first volume "
#								 "from a RAR set.")
#			# TODO: failed for RAR 2.0 archives
#			# write tests (rar files already created) -> done
#			# add rar version test too
			
	# TODO: SFX support?
	if first_rars([filename(rfile)]) != [filename(rfile)]:
		raise ValueError("You must start with the first volume from a RAR set.")
			
	next_file = filename(rfile)
	while exists(next_file):
		yield next_file
		next_file = filename(next_archive(next_file))
		
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

	for block in RarReader(srr_file).read_all():
		add_size = True
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
				sfvfile = io.BytesIO()
				with open(srr_file, "rb") as sfv:
					sfv.seek(block.block_position + block.header_size)
					sfvfile.write(sfv.read(block.file_size))
				(entries, comments, errors) = parse_sfv_file(sfvfile)
				sfv_entries.extend(entries)
				sfv_comments.extend(comments)
				# TODO: let user know that there is a bad SFV
				sfv_comments.extend(errors)
			
			current_rar = None # end the file size counting
		elif block.rawtype == BlockType.SrrRarFile:
			add_size = False
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
			if not block.unicode_filename in archived_files:
				f = FileInfo()
				f.file_name = block.file_name
				f.file_size = block.unpacked_size
				f.unicode_filename = block.unicode_filename
				f.orig_filename = block.orig_filename
				f.compression = block.is_compressed()
				if f.compression:
					compression = True
			else:
				f = archived_files[block.unicode_filename]
			# crc of the file is the crc stored in
			# the last archive that has the file
			f.crc32 = "%X" % block.file_crc
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
			msg = "Old Authenticity block found. (%s)"  \
				% str(hex(block.rawtype))
			if _DEBUG: print(msg)
			_fire(MsgCode.AUTHENTCITY, message=msg)
			
		# calculate size of RAR file
		if current_rar:
			if add_size:
				current_rar.file_size += block.header_size + block.add_size
			current_rar.offset_end_rar = (block.block_position + 
										  block.header_size)
			rar_files[current_rar.key] = current_rar	
	
	def add_info_to_rar(sfv_entry):
		"""Add SFV crc32 hashes to the right RAR info block"""
		key = os.path.basename(sfv_entry.file_name).lower()		  
		if key in rar_files:
			rar_files[key].crc32 = sfv_entry.crc32.upper()
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
			"compression": compression,}

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
	ftype = {RarReader.RAR: "RAR",
	         RarReader.SRR: "SRR",
	         RarReader.SFX: "SFX", }[rr.file_type()] # dict to emulate switch
	print("The file is a %s file." % ftype)
	
	for block in rr.read_all():
		print(block.explain())
			
def reconstruct(srr_file, in_folder, out_folder, extract_paths=True, hints={},
				skip_rar_crc=False, auto_locate_renamed=False, empty=False):
	"""
	srr_file: SRR file of the archives that need to be rebuild
	in_folder: root folder in which we start looking for the files
	out_folder: location to place the constructed archives
	extract_paths: if paths are stored in the SRR, they will be recreated
	               starting from out_folder
	hints: a dictionary used for handling renamed files
	key: name in original RAR, value: renamed file name on disk
	skip_rar_crc: Disables checking the crc32 values of files and rars while
	              reconstructing. It speeds up the process.
	auto_locate_renamed: if set, start looking in sub folders and guess based
	                     on file size and extension of the file to pack
	"""
	rar_name = ""
	ofile = ""
	source_name = ""
	rarfs = None # RAR Volume that is being reconstructed
	srcfs = None # File handle for the stored files
	rebuild_recovery = False
	running_crc = 0
	
	for block in RarReader(srr_file).read_all():
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
			# There is a file stored within the SRR file. Extract it.
			_extract(block, _opath(block, extract_paths, out_folder))
		elif block.rawtype == BlockType.SrrRarFile:
			_flag_check_srr(block)
			# We need to create a RAR file for each SRR block.
			# Get the stored name and create it.
			if rar_name != block.file_name:
				# We use flag 0x1 to mark the files that have their recovery
				# records removed.  All other flags are currently undefined.
				rebuild_recovery = (block.flags &  \
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
					_fire(MsgCode.USER_ABORTED, message="Operation aborted.")
					return -1
		elif _is_recovery(block):
			if block.recovery_sectors > 0 and rebuild_recovery:
				_write_recovery_record(block, rarfs)
			else:
				# The block is from a previous ReScene version (full RR stored)
				# or is not a recovery record. Just copy it.
				rarfs.write(block.block_bytes())
				# TODO: !!! not fully copied?
		elif block.rawtype == BlockType.RarPackedFile:
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
			if source_name != block.file_name:
				try: srcfs.close()
				except: pass
				source_name = block.file_name
				running_crc = 0
				try:
					if block.compression_method != COMPR_STORING:
						print("Trying to rebuild compressed file.")
						#TODO: bytes to pack need to come from an other rar
						
						"""
						rerar single file with the right compression method
						use that data
						
						multiple files -> more difficult because it can be solid
						
						"""
						
						
						first_rar = ""

						raise NotImplementedError
						
						srcfs = RarStream(first_rar, source_name)
					else: # uncompressed file
						src = _locate_file(block, in_folder,
										   hints, auto_locate_renamed)
						srcfs = open(src, "rb")
				except FileNotFound:
					if empty:
						srcfs = FakeFile(block.packed_size)
					else:
						raise
			assert srcfs
			
			# then grab the correct amount of data from the extracted file
			running_crc = _repack(block, rarfs, in_folder, srcfs, running_crc, 
								 skip_rar_crc)
		elif block.rawtype >= BlockType.RarMin and  \
				block.rawtype <= BlockType.RarMax or  \
				(block.rawtype == 0x00 and block.header_size == 20): #TODO:test
			# copy any other RAR blocks to the destination unmodified
			rarfs.write(block.block_bytes())
			# -> P0W4 cleared RAR archive end block: 
			# almost all zeros except for the header size field
		else:
			_fire(MsgCode.UNKNOWN, message="Warning: Unknown block type "
				  "%#x encountered in SRR file, consisting of %d bytes. "
				  "This block will be skipped." % 
				  (block.rawtype, block.header_size))
	if rarfs:
		rarfs.close()

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
	crc = bytearray(protected_sectors * 2)
	rs = [0] * recovery_sectors # [0, 0, ..., 0]
	for i in range(recovery_sectors):
		rs[i] = bytearray(512)

	rarfs.seek(0, os.SEEK_END) # move relative to end of file
	rar_length = rarfs.tell()
	assert rar_length != 0 # you can't calculate stuff on nothing
	rarfs.seek(0)
	
	while rarfs.tell() < rar_length:
		# Read data one sector at a time.  Pad the last sector with 0's.
		sector = rarfs.read(512)
		if len(sector) != 512:
			sector += str(bytearray(512 - len(sector)))
		assert len(sector) == 512

		# calculate the crc32 for the sector and store the 2 low-order bytes
		sector_crc = ~zlib.crc32(sector) # Bitwise Inversion
		crc[current_sector*2] = sector_crc & 0xff
		crc[current_sector*2+1] = (sector_crc >> 8) & 0xff
		current_sector += 1

		# update the recovery sector parity data for this slice
		for i in range(512):
			rs[rs_slice][i] ^= ord(sector[i])
		rs_slice = rs_slice + 1 if (rs_slice + 1) % recovery_sectors else 0
	# https://lists.ubuntu.com/archives/bazaar/2007q1/023524.html
	rarfs.seek(0, 2) # prevent IOError: [Errno 0] Error on Windows
	
	rarfs.write(block.block_bytes()) # write the backed-up block header,
	rarfs.write(crc)                  # CRC data and
	for sector in rs:                 # recovery sectors
		rarfs.write(sector)

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
	if block.file_name in hints.keys():
		src = hints.get(block.file_name)
	else:
		src = block.file_name
	src = os.path.join(in_folder, src)
	
	if not os.path.isfile(src):
#		_fire(MsgCode.FILE_NOT_FOUND, 
#			  message="Could not locate data file: %s" % src)
		if auto_locate_renamed:
			src = _auto_locate_renamed(block.file_name, 
									   block.unpacked_size, in_folder)
		if not os.path.isfile(src):
			raise FileNotFound("The file does not exist: %s." % src)
		
	if os.path.getsize(src) != block.unpacked_size:
		raise InvalidFileSize("Data file is not the correct size: %s."
			"Found: %d. Expected: %d." % 
			(src, os.path.getsize(src), block.unpacked_size));
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
	"""Adds a file to the RAR archive."""
	bytes_copied_inc = 0
	file_crc = 0

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
			print("Crappy release group.")
			
		bytes_copied_inc += bytes_to_copy
	
	def file_end():
		return block.flags & RarPackedFileBlock.SPLIT_AFTER == 0

	if not skip_rar_crc:
		if not file_end() and block.file_crc != file_crc & 0xffffffff:
			_fire(MsgCode.CRC, message="CRC mismatch in RAR file: %s" % 
				  rarfs.name)
			print("%08x %08x" % (block.file_crc, file_crc & 0xffffffff), 
				  rarfs.name)
		elif file_end() and block.file_crc != running_crc & 0xffffffff:
			_fire(MsgCode.CRC, message="CRC mismatch in file: %s" % 
				  block.file_name)
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
	if save_paths: # AttributeError: 'NoneType' object has no attr...
		file_name = os.path.relpath(sfile, in_folder)
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
	except Exception:
		# reading data fails, so just skip the file
		print(sys.exc_info())

def _search(files, folder=""):
	"""Enumerates all files to store. Yields a generator.
	Wildcards are accepted for paths and file names.
	
	files    absolute or relative path or 
	         path relative to supplied folder and can contain wildcards
	folder:	 location to search for files when
	         paths are relative in files parameter
	"""
	if not isinstance(files, (list, tuple)): # we need a list
		files = [files]		# otherwise iterating over characters
		
	folder = escape_glob(folder)

	for file_name in files:
		# use path relative to folder if the path isn't relative or absolute 
		if os.path.isabs(file_name) or file_name[:2] == os.pardir:
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
		self.orig_filename = ""
		# use the same sorting used for the sfv entries
		self.__lt__ = SfvEntry.__lt__
	def __str__(self):
		return (str(self.file_name) + " " + str(self.file_size)
				+ " " + str(self.crc))
	def __repr__(self): # if possible evaluable representation of an object
		return self.__str__()
