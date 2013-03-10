#!/usr/bin/env python
# -*- coding: latin-1 -*-

# Copyright (c) 2013 pyReScene
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import io
import os
import re
import sys
import zlib
import shutil
import subprocess
import multiprocessing
from tempfile import mkdtemp
from rescene.rar import RarReader, BlockType
from rescene.rarstream import RarStream
from rescene.utility import empty_folder

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

class EmptyRepository(Exception):
	"""The RAR repository is empty."""

class RarNotFound(Exception):
	"""No good RAR executable can be found."""
	
def get_temp_directory():
	global temp_dir
	if temp_dir and os.path.isdir(temp_dir):
		if not len(os.listdir(temp_dir)):
			return temp_dir
		else:
			print("Temporary directory not empty.")
	return mkdtemp("_pyReScene")
	
def get_rar_data_object(block, blocks, src):
	return archived_files.setdefault(block.file_name,
	                         compressed_rar_file_factory(block, blocks, src))
	
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
			previous = [archived_files.values()[-1].good_rar]
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
		p = custom_popen(self.path())
		(stdout, _stderr) = p.communicate()
		self.threads = "mt<threads>" in stdout
		return self.threads
	
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
		self.old_style = "-vn"
		
		self.rar_archive = rar_archive
		if type(store_files) != type([]):
			raise ValueError("Expects a list of files to store.")
		self.store_files = store_files
		
		self.set_solid(block.flags & block.SOLID)
		self.set_solid_namesort(False)
		self.threads = ""
	
	def arglist(self):
		args = filter(lambda x: x != '', 
			["a", self.compr_level, self.dict_size, 
			self.solid, self.solid_namesort, self.threads,
			self.old_style, "-o+",
			self.rar_archive]) + self.store_files
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
			
	def set_solid_namesort(self, is_set): #TODO: use while generating
		"""
		ds            Disable name sort for solid archive
		"""
		if is_set:
			self.solid_namesort = ""
		else:
			self.solid_namesort = "-sn"
	
def compressed_rar_file_factory(block, blocks, src):
	blocks = get_archived_file_blocks(blocks, block)
	if block.flags & block.SOLID:
		# get first file from archive
		if block != blocks[0]:
			# reuse CompressedRarFile because of the solid archive
			rar = archived_files[blocks[0].file_name]
			rar.set_new(src, block)
			return rar
	return CompressedRarFile(block, blocks, src)

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
	An SRR file can contain recreation data of different RAR sets.
	This function tries to pick the basename of such a set.
	"""
	n = srr_rar_block.file_name[:-4]
	match = re.match("(.*)\.part\d*$", n, re.I)
	if match:
		return match.group(1)
	else:
		return n

class CompressedRarFile(io.IOBase):
	"""Represents compressed RAR data."""
	def __init__(self, first_block, blocks, src):
		"""blocks are only RarPackedFile blocks from the current set"""
		self.current_block = first_block
		self.blocks = blocks
		self.source_files = [src]
		self.date = self.get_most_recent_date()
		self.COMPRESSED_NAME = "pyReScene_compressed.rar"
		
		self.solid = first_block.flags & first_block.SOLID
		
		self.temp_dir = get_temp_directory()
		
		# make sure there is a RarRepository
		global repository
		if not repository:
			repository = RarRepository()
		
		# search the correct RAR executable
		self.good_rar = self.search_matching_rar_executable(first_block, blocks)
		if not self.good_rar:
			assert len(os.listdir(self.temp_dir)) == 0
			try:
				# don't remove users' temp dir
				if self.temp_dir != temp_dir:
					os.rmdir(self.temp_dir)
			except:
				print("Failure to remove temp dir: %s" % self.temp_dir)
			raise RarNotFound("No good RAR version found.")
		print("Good RAR version detected: %s" % self.good_rar)
		
		print("Compressing %s..." % os.path.basename(src))
		self.good_rar.args.store_files = self.source_files
#		compress = custom_popen(self.good_rar.full())
		compress = subprocess.Popen(self.good_rar.full())
		stdout, stderr = compress.communicate()
		
		if compress.returncode != 0:
#			print(stdout)
#			print(stderr)
			print("Something went wrong executing Rar.exe:")
			print(RETURNCODE[compress.returncode])
			
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		self.rarstream = RarStream(out, compressed=True)

	def search_matching_rar_executable(self, block, blocks):
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		piece = os.path.join(self.temp_dir, "pyReScene_data_piece.bin")
		
		def get_full_packed_size():
			result_size = 0
			for lego in blocks:
				if lego.file_name == block.file_name:
					result_size += lego.packed_size
				elif result_size:
					break
			return result_size
		
		# only compress enough data that is compressed 
		# larger than the amount we need
		# we need the size of the whole file compressed
		size_compr = get_full_packed_size()
		size_full = block.unpacked_size
		assert size_full == os.path.getsize(self.source_files[-1])
		size_min = block.packed_size
		
		# Rar 2.0x version don't have a CRC stored, only at the end
		# do the complete file
		if block.file_crc == 0xFFFFFFFF:
			args = RarArguments(block, out, [self.source_files[0]])
			old = True
		else:
			old = False
			args = RarArguments(block, out, [piece])
		
			print("Grabbing large enough data piece size for testing.")
			# we assume that newer versions always compress better
			rarexe = repository.get_most_recent_version()
			
			window_size = block.get_dict_size()
			amount = 0
			# start with 2% increase of the ratio
			for i in list(range(2, 100, 5)):
				increase = (float(size_full) / size_compr) + (i / 100.0)
				amount = min(size_full, int(size_min * increase) + window_size)
				print("Size: %d" % amount)
				
				# copy bytes from source to destination
				copy_data(self.source_files[0], piece, amount)
				
				if amount == size_full:
					break
				
				proc = custom_popen([rarexe.path()] + args.arglist())
				proc.wait()
				
				if proc.returncode != 0:
					print(proc.stdout.read())
					print(proc.stderr.read())
					print("Something went wrong executing Rar.exe:")
					print(RETURNCODE[proc.returncode])
			
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
			
		def try_rar_executable(rar, args, old=False):
			compress = custom_popen([rar.path()] + args.arglist())
			stdout, stderr = compress.communicate()
			
			if compress.returncode != 0:
				print(stdout)
				print(stderr)
				print("Something went wrong executing Rar.exe:")
				print(RETURNCODE[compress.returncode])

			# check if this is a good RAR version
			start = size_min
			ps = crc = 0
			with RarStream(out, compressed=True) as rs:
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
		
		for rar in repository.get_rar_executables(self.get_most_recent_date()):
			print("Trying %s." % rar)
			found = False
			if rar.supports_setting_threads():
				for thread_param in range(1, multiprocessing.cpu_count() + 1):
					args.threads = "-mt%d" % thread_param
					if try_rar_executable(rar, args, old):
						found = True
						break
			else:
				found = try_rar_executable(rar, args, old)
			if found:
				rar.args = args
				print(" ".join(args.arglist()))
				return rar
			args.threads = ""
		os.remove(piece)
	
	def set_new(self, source_file, block):
		self.source_files.append(source_file)
		self.current_block = block
		os.mkdir(self.temp_dir)
		
		out = os.path.join(self.temp_dir, self.COMPRESSED_NAME)
		
		print("Compressing...")
		self.good_rar.args.source_files = self.source_files
		self.good_rar.args.set_solid(block.flags & block.SOLID)
		compress = custom_popen(self.good_rar.full())
		stdout, stderr = compress.communicate()
		
		if compress.returncode != 0:
			print(stdout)
			print(stderr)
			print("Something went wrong executing Rar.exe:")
			print(RETURNCODE[compress.returncode])

		self.rarstream = RarStream(out, compressed=True,
				packed_file_name=os.path.basename(self.source_files[-1]))
		
		if self.rarstream.length() != block.packed_size:
			raise ValueError("Something isn't good yet.")
#			self.good_rar = self.search_matching_rar_executable(block, self.blocks)
		
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
#		print "Length: %d" % self.rarstream.length()
		return self.rarstream.length()
	
	def tell(self):
		"""Return the current stream position."""
#		print "Tell: %d" % self.rarstream.tell()
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
		global temp_dir
		if self.temp_dir == temp_dir:
			# don't remove the user his folder
			empty_folder(self.temp_dir)
		else:
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
#		print "Seek: %d" % offset
		self.rarstream.seek(offset, origin)
	
	def read(self, size=-1):
		"""
		read([size]) 
			-> read at most size bytes, returned as a string.
			If the size argument is negative, read until EOF is reached.
			Return an empty string at EOF.
			
		size > self.length(): EOFError
		"""
#		print "Read amount: %d" % size
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
		return self.readinto(byte_array)
	
def custom_popen(cmd):
	"""disconnect cmd from parent fds, read only from stdout"""
	
	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000 # CREATE_NO_WINDOW

	# run command
	print(cmd)
	return subprocess.Popen(cmd, bufsize=0, stdout=subprocess.PIPE, 
							stdin=subprocess.PIPE, stderr=subprocess.STDOUT, 
							creationflags=creationflags)	
	
def copy_data(source_file, destination_file, offset_amount):
	with open(source_file, 'rb') as source:
		with open(destination_file, 'wb') as destination:
			destination.write(source.read(offset_amount))

	