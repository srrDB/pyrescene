#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011-2013 pyReScene
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

# Development started after ReScene .NET 1.2
#   RarBlocks.cs
# Port based on the above file: MIT license
#   http://rescene.com/ - http://rescene.info/
# ISC License (ISCL) for the stuff copied from rarfile.py (version 2.2)
#   (Unicode, MS-DOS timedate support)
#   http://pypi.python.org/pypi/rarfile

# TODO: 
# define external public interface
# __all__ = [] # dir(rar)

from __future__ import absolute_import
#from __future__ import unicode_literals # either textual or bytes data
import io
import struct
import os
import sys
import tempfile

from rescene import utility 

_DEBUG = bool(os.environ.get("RESCENE_DEBUG", "")) # leave empty for False

###############################################################################

# Copyright (c) 2005-2010  Marko Kreen <markokr@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

##
## Compatibility code to support both Python 2 and 3
##

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behavior
	range = xrange #@ReservedAssignment @UndefinedVariable
	# py2.6 has broken bytes()
	def bytes(foo, enc=None): #@ReservedAssignment
		return str(foo)

# internal byte constants
RAR_MARKER_BLOCK = bytes("Rar!\x1a\x07\x00", 'ascii')
ZERO = bytes("\0", 'ascii')

# default fallback charset
DEFAULT_CHARSET = "windows-1252"

def _parse_dos_time(stamp):
	sec = stamp & 0x1F; stamp = stamp >> 5
	mnt = stamp & 0x3F; stamp = stamp >> 6
	hr  = stamp & 0x1F; stamp = stamp >> 5
	day = stamp & 0x1F; stamp = stamp >> 5
	mon = stamp & 0x0F; stamp = stamp >> 4
	yr = (stamp & 0x7F) + 1980
	return (yr, mon, day, hr, mnt, sec * 2)

def _parse_ext_time(block, pos):
	data = block._rawdata

	# flags and rest of data can be missing
	flags = 0
	if pos + 2 <= len(data):
		flags = struct.Struct('<H').unpack_from(data, pos)[0] # short
		pos += 2

	block.mtime, pos = _parse_xtime(flags >> 3*4, data, pos, 
	                                block.file_datetime)
	block.ctime, pos = _parse_xtime(flags >> 2*4, data, pos)
	block.atime, pos = _parse_xtime(flags >> 1*4, data, pos)
	block.arctime, pos = _parse_xtime(flags >> 0*4, data, pos)
	return pos

def _parse_xtime(flag, data, pos, dostime = None):
	unit = 10000000.0 # 100 ns units
	if flag & 8:
		if not dostime:
			t = struct.Struct('<L').unpack_from(data, pos)[0] # long
			dostime = _parse_dos_time(t)
			pos += 4
		rem = 0
		cnt = flag & 3
		for _ in range(cnt):
			b = struct.Struct('<B').unpack_from(data, pos)[0] # byte
			rem = (b << 16) | (rem >> 8)
			pos += 1
		sec = dostime[5] + rem / unit
		if flag & 4:
			sec += 1
		dostime = dostime[:5] + (sec,)
	return dostime, pos

class UnicodeFilename(object):
	""" Handles the Unicode filename compression used in rar files.
	The bytes inside the rar file contain the original file name separated
	from the Unicode file name by a null byte.
	  name: the part before 0x00
	  encdata: the compressed Unicode data after the null byte
	Use the decode() function to get the Unicode string of the file name.
	
	WinRAR documentation:
	   0x200 - FILE_NAME contains both usual and encoded
		   Unicode name separated by zero. In this case
		   NAME_SIZE field is equal to the length
		   of usual name plus encoded Unicode name plus 1.

		   If this flag is present, but FILE_NAME does not
		   contain zero bytes, it means that file name
		   is encoded using UTF-8.
		LHD_UNICODE
	"""
	def __init__(self, name, encdata):
		self.std_name = bytearray(name)
		self.encdata = bytearray(encdata)
		self.pos = self.encpos = 0
		self.buf = bytearray()

	def enc_byte(self):
		c = self.encdata[self.encpos]
		self.encpos += 1
		return c

	def std_byte(self):
		return self.std_name[self.pos]

	def put(self, lo, hi):
		self.buf.append(lo)
		self.buf.append(hi)
		self.pos += 1

	def decode(self):
		""" See also encname.cpp """
		hi = self.enc_byte()
		flagbits = 0
		while self.encpos < len(self.encdata):
			if flagbits == 0:
				flags = self.enc_byte()
				flagbits = 8
			flagbits -= 2
			t = (flags >> flagbits) & 3
			if t == 0:
				self.put(self.enc_byte(), 0)
			elif t == 1:
				self.put(self.enc_byte(), hi)
			elif t == 2:
				self.put(self.enc_byte(), self.enc_byte())
			else:
				n = self.enc_byte()
				if n & 0x80:
					c = self.enc_byte()
					for _ in range((n & 0x7f) + 2):
						lo = (self.std_byte() + c) & 0xFF
						self.put(lo, hi)
				else:
					for _ in range(n + 2):
						self.put(self.std_byte(), 0)
		return self.buf.decode("utf-16le", "replace") # LE: little endian

###############################################################################

HEADER_LENGTH = 7 # The minimum size of a header block

COMPR_STORING = 0x30
COMPR_FASTEST = 0x31
COMPR_FAST    = 0x32
COMPR_NORMAL  = 0x33
COMPR_GOOD    = 0x34
COMPR_BEST    = 0x35

OS_MSDOS = 0
OS_OS2   = 1
OS_WIN32 = 2
OS_UNIX  = 3
OS_MACOS = 4
OS_BEOS  = 5

class BlockType: # saved as integer number internally
	""" Enumeration class to easily reference hex values. """
	# not all block types are consumed.
	RarOldComment = 0x75
	RarOldAuthenticity76 = 0x76 # AV_HEAD - Extra info block
	RarOldSubblock = 0x77 # OS/2 extended attributes subblock
	RarOldAuthenticity79 = 0x79 # SIGN_HEAD
	
	# these are the only RAR block types we do anything with
	RarVolumeHeader = 0x73  # Archive header                            s
	RarPackedFile = 0x74    # File header                               t
	RarOldRecovery = 0x78   # old-style recovery record                 x
	RarNewSub = 0x7A        # subblock (contains new-style RR, CMT, AV) z
	
	# block types 0x72 to 0x7B are defined by the RAR specification
	# These values let us identify them
	RarMin = 0x72           # Marker block (must be the first block)    r
	RarMax = 0x7B           # Archive end (optional: -en switch rar)    {
	
	# we use the range just below that (0x69 to 0x71) for SRR
	SrrHeader = 0x69        # i -> 0x73 (s) RarVolumeHeader
	SrrStoredFile = 0x6A    # j -> 0x74 (t) RarPackedFile
	SrrOsoHash = 0x6B       # k
	SrrRarPadding = 0x6C	# l
	SrrRarFile = 0x71       # q -> 0x7A (z) RarNewSub
	
class SrrFlags():
	LONG_BLOCK = 0x8000
	SRR_APP_NAME_PRESENT = 0x1
	
	RECOVERY_BLOCKS_REMOVED = 0x1
	
# SRR has no marker or archive end blocks
BLOCK_NAME = {
	0x69: "SRR Volume Header", # i
	0x6A: "SRR Stored File", # j
	0x6B: "SRR OSO Hash", # unused
	0x6C: "SRR", # unused
	0x6D: "SRR", # unused
	0x6E: "SRR", # unused
	0x6F: "SRR", # unused
	0x70: "SRR", # unused
	0x71: "SRR RAR subblock", # q
	0x72: "RAR Marker",
	0x73: "RAR Archive Header",
	0x74: "RAR File",
	0x75: "RAR Old style - Comment",
	0x76: "RAR Old style - Extra info (authenticity information)",
	0x77: "RAR Old style - Subblock",
	0x78: "RAR Old style - Recovery record",
	0x79: "RAR Old style - Archive authenticity",
	0x7A: "RAR New-format subblock",
	0x7B: "RAR Archive end",
}

COMPRESSION_NAME = {
	0x30: "Storing",
	0x31: "Fastest compression",
	0x32: "Fast compression",
	0x33: "Normal compression",
	0x34: "Good compression",
	0x35: "Best compression"
}

OS_NAME = {
	0: "MS DOS",
	1: "OS/2",
	2: "Windows",
	3: "Unix",
	4: "Mac OS",
	5: "BeOS",
}

DICTIONARY_NAME = {
	0: "Dictionary size 64 KiB",
	1: "Dictionary size 128 KiB",
	2: "Dictionary size 256 KiB",
	3: "Dictionary size 512 KiB",
	4: "Dictionary size 1024 KiB",
	5: "Dictionary size 2048 KiB",
	6: "Dictionary size 4096 KiB",
	7: "File is a directory",
}

RAR_VERSION = {
#	0: "Unknown compression!", # Farscape.S01E01.AC3.DivX.DVDRip.iNTERNAL-AMC
	15: "15: RAR 1.5 compression",
	20: "20: RAR 2.x compression",
	26: "26: files larger than 2GB",
	29: "29: RAR 3.x compression",
	36: "36: alternative hash",	   
}
		
class ArchiveNotFoundError(IOError):
	pass

class RarBlock(object):
	""" Represents basic header used in all SRR and RAR blocks.
	
	crc             HEAD_CRC: For header CRCs,  RAR calculates a CRC32 and 
	                throws out the high-order bytes.
	rawtype         HEAD_TYPE
	flags           HEAD_FLAGS
	_rawdata        All the data (byte string) of this block.
	block_position  Offset of the block in the original file/stream.
	header_size     The length of the header from this block.
	
	|CRC |TY|FLAG|SIZE[|ADD_SIZE]
	Each block begins with the following fields:
	
	HEAD_CRC       2 bytes     CRC of total block or block part
	HEAD_TYPE      1 byte      Block type
	HEAD_FLAGS     2 bytes     Block flags
	HEAD_SIZE      2 bytes     Block size
	ADD_SIZE       4 bytes     Optional field - added block size
	
	   Marker block ( MARK_HEAD )
	HEAD_CRC        Always 0x6152                    2 bytes
	HEAD_TYPE       Header type: 0x72                1 byte
	HEAD_FLAGS      Always 0x1a21                    2 bytes
	HEAD_SIZE       Block size = 0x0007              2 bytes
	   The marker block is actually considered as a fixed byte
	sequence: 0x52 0x61 0x72 0x21 0x1a 0x07 0x00
	"""
	# if set, ADD_SIZE field is present and the full block
	# size is HEAD_SIZE+ADD_SIZE
	LONG_BLOCK = 0x8000
	
	# if set, older RAR versions will ignore the block
	# and remove it when the archive is updated.
	# if clear, the block is copied to the new archive
	# file when the archive is updated;
	SKIP_IF_UNKNOWN = 0x4000
	
	SUPPORTED_FLAG_MASK = (LONG_BLOCK | SKIP_IF_UNKNOWN)
	
	def __init__(self, block_bytes, file_position, fname):
		"""Interprets the first 7 bytes of the header.
		block_bytes: the full header + sometimes the data
					(e.g. SrrRarFileBlock)
		file_position: index of the block in fname
		fname: file we need if we want to lookup the stored data bits
			   (only necessary with SrrStoredFileBlock)
			   TODO: make it work for RarPackedFile too
		"""
		# make incoming bytes accessible as a stream
		self._rawdata = block_bytes
		self.block_position = file_position
		self.fname = fname
		
		(self.crc, self.rawtype, self.flags, self.header_size) =  \
						struct.unpack(str("<HBHH"), self._rawdata[:7])
		self._p = HEADER_LENGTH # pointer to ease reading
		
		# Outcast BiA releases don't set this flag for BlockType.RarPackedFile 
		if self.flags & RarBlock.LONG_BLOCK:
			self.add_size = struct.unpack(str("<I"), self._rawdata[7:7+4])[0]
		else:
			self.add_size = 0
			
	def _write_header(self, header_size):
		"""Write 7 byte header."""
		self._rawdata = ""
		self._rawdata += str(struct.pack(str("<H"), self.crc)) # 2 bytes
		self._rawdata += str(struct.pack(str("<B"), self.rawtype)) # 1 byte: uchar
		self._rawdata += str(struct.pack(str("<H"), self.flags)) # unsigned short
		self._rawdata += str(struct.pack(str("<H"), header_size)) # 2 bytes
		self._p = HEADER_LENGTH

	def block_bytes(self):
		"""Returns all header data of the block.
		Unless it's a SRR stored file block, the body data is returned too.
		
		How about a RarPackedFileBlock or recovery block?
		"""
		#TODO: this isn't right... (comments or implementation)
		# make a function that does the whole block see add_stored_files
		return self._rawdata
	
	def __repr__(self):
		return "%s %x %d" % (BLOCK_NAME[self.rawtype], self.block_position, 
		                     self.header_size)
		
	def explain(self):
		bname = BLOCK_NAME.get(self.rawtype, "UNKNOWN BLOCK! NUKE IT!")
		out = "Block: %s; offset: %s\n" % (bname, 
			self.explain_size(self.block_position))
		out += "|Header bytes: %s\n" % self._rawdata.encode('hex')
		if self.rawtype == BlockType.RarMin:
			out += "|Rar marker block is always 'Rar!1A0700' (magic number)\n"
		out += "|HEAD_CRC:   0x%X\n" % self.crc
		out += "|HEAD_TYPE:  0x%X (%s)\n" % (self.rawtype, bname)
		out += self.explain_flags()
		out += "|HEAD_SIZE:  %s\n" % self.explain_size(self.header_size)
		return out
	
	def explain_flags(self):
		out = "|HEAD_FLAGS: 0x%04X\n" % self.flags
		flagresult = (self.SUPPORTED_FLAG_MASK & self.flags) ^ self.flags
		if flagresult != 0 and self.rawtype != BlockType.RarMin:
			out += "UNSUPPORTED FLAG DETECTED! %04X\n" % flagresult
		if self.flags & RarBlock.LONG_BLOCK:
			out += self.flag_format(RarBlock.LONG_BLOCK) +  \
				"LONG_BLOCK (ADD_SIZE field present)\n"
		if self.flags & RarBlock.SKIP_IF_UNKNOWN:
			out += self.flag_format(RarBlock.SKIP_IF_UNKNOWN) +  \
				"SKIP_IF_UNKNOWN (older RAR versions will ignore this block)\n"
		return out
	
	def flag_format(self, flag):
		return "|   0x%04X " % flag
	
	def explain_size(self, size):
		return "0x%X (%u bytes)" % (size, size)
		
class SrrHeaderBlock(RarBlock):
	""" Represents marker/srr volume header block.
	It contains the name of the ReScene application.
	
	|CRC |TY|FLAG|SIZE|[APNS|APPLICATION NAME...|]
	 6969 69 0100
	         0000
	CRC:    0x6969; (will never be the actual calculated CRC value)
	        magic number
	TY:     Type: 0x69
	FLAG:   0x1 if Application name is present
	SIZE:   Header length in bytes (See RAR HEAD_SIZE)
	        Name length and name are included in the header, but HL is limited
	        to 65535 (0xFFFF) bytes.
	
	APNS:   Application name size. Length of APPLICATION NAME.
	        2 bytes. Maximum value: FFF6. Can be 0000 if 0x1 flag is set.
	APPLICATION NAME:
	        Name of the application, if present. Max 65526 bytes long.
	
	If APNS and name are included in the header, so the maximum possible
	APNS value is 0xFFF6 because of SIZE.
	    Max application name size:
	        FFFF(65535 bytes) (SIZE: 2 bytes) minus:
	         - 7 bytes        (HEADER_LENGTH) 
	         - 2 bytes        (APNS) 
	        65535 - 9 = 65526 (FFF6).
	Minimal block used in the old beta 2 equivalent C implementation:
	69 69 69 00 00 07 00
	Minimal block that ReScene .NET produces when empty string is given.
	69 69 69 01 00 07 00 00 00
	"""
	SRR_APP_NAME_PRESENT = 0x1
	SUPPORTED_FLAG_MASK = SRR_APP_NAME_PRESENT
	
	def __init__(self, bbytes=None, filepos=None, fname=None, appname=None):
		if not appname and appname != "": # read block
			super(SrrHeaderBlock, self).__init__(bbytes, filepos, fname)
			
			# If the SRR_APP_NAME_PRESENT flag is set, the header contains
			# 2 bytes for application name length, followed by the name.
			if self.flags & self.SRR_APP_NAME_PRESENT:
				appname_length = struct.unpack(str("<H"), 
								self._rawdata[self._p:self._p+2])
				self.appname = self._rawdata[self._p+2:self._p+2+
											appname_length[0]] # tuple
				self._p += 2 + appname_length[0]
			else:
				self.appname = "" # "No application name present."
		else: # Create SRR header block
			# SRR blocks are based on RAR block format. 
			# Header block type is 0x69.
			# TODO: "We don't use CRC for blocks (as of now), 
			# so CRC value is set to 0x6969."
			# Flag 0x1 indicates the header contains appName. 
			# Length of the block is 7 bytes (header length) + 
			#						2 bytes for appName length +
			#						the length of the appName.
			self.crc = 0x6969
			self.rawtype = 0x69
			self.flags = 0
			self.appname = appname
			if len(self.appname):
				self.flags = self.SRR_APP_NAME_PRESENT
				self._write_header(HEADER_LENGTH + 2 + len(self.appname))
				self._rawdata += str(struct.pack(str("<H"), len(self.appname)))
				self._rawdata += str(self.appname)
			else:
				self._write_header(HEADER_LENGTH)
				
	def __str__(self):
		return self.appname
	
	def explain_flags(self):
		out = super(SrrHeaderBlock, self).explain_flags()
		if self.flags & self.SRR_APP_NAME_PRESENT:
			out += self.flag_format(self.SRR_APP_NAME_PRESENT) +  \
				"(an application name (length) field is present)\n"
		return out
	
	def explain(self):
		out = super(SrrHeaderBlock, self).explain()
		out += "+Application name length: " + self.explain_size(
		                                      len(self.appname)) + "\n"
		out += "+Application name: " + self.appname + "\n"
		return out

class SrrStoredFileBlock(RarBlock):
	"""
	SRR block used to store additional files inside the .srr file.
	e.g. .nfo and .sfv files.
	
	|CRC |TY|FLAG| HL | * |  SIZE  | NL |(path)File name|
	CRC:    0x6A6A
	TY:     Type 0x6A
	HL:     Header Length (2 bytes)
	FLAG:   0x8000 must always be set for this block to indicate file size
	SIZE:   File Size (4 bytes) -> existence indicated in FLAGs
	        The maximum file size is 4294967296 bytes (0xFFFFFFFF) or 4096 MiB.
	NL: Name Length + path (2 bytes)
	    The maximum length of the path + the name is 65522 (0xFFF2).
	    The path structure in RAR files is always Windows style: "\" BUT
	    ReScene .NET uses the "/" file name separator to store paths. 
	    
	    Because HL is also 2 bytes, NL can't use the full range.
	    0xFFFF - 7 - 4 - 2 = 65522 (0xFFF2)
	
	file_size       The size in bytes of the file stored.
	file_name       The name of the file stored after this block.
	header_size     The offset in the header where the actual file begins.
	"""
	#PATHS_SAVED = 0x2 # Never actually written with ReScene .NET 1.2
#	#TODO: new flag when it's a path only (for empty dirfix releases)
#	PATH_ONLY = 0x4 -> empty file and name ends on /?
	
	SUPPORTED_FLAG_MASK = RarBlock.LONG_BLOCK # | PATHS_SAVED

	def __init__(self, bbytes=None, filepos=None, fname=None,
	             file_name=None, file_size=None):
		try:
			file_size = int(file_size)
		except (ValueError, TypeError): # not a number
			file_size = None
		# when reading a srr file block
		if bbytes and filepos and fname:
			super(SrrStoredFileBlock, self).__init__(bbytes, filepos, fname)
			
			# 4 bytes for file length (unsigned int) (add_size field)
			# 2 bytes for name length, then the name (unsigned short)
			(self.file_size, length) = struct.unpack(str("<IH"), 
			                           self._rawdata[self._p:self._p+6])
			self.file_name = self._rawdata[self._p+6:self._p+6+length]
			self._p += 6 + length
			
		# creating a srr file block
#		elif file_name != None and isinstance(file_size, (int, long)):
		elif file_name != None and file_size != None:
			""" store block (type 0x6A) has the 0x8000 flag set to indicate
				there is additional data following the block.
				format is 7 byte header followed by 4 byte file size, 
				2 byte file name length, and file name
			"""
			self._write_rawdata(file_name, file_size)
		else:
			raise AttributeError("The two named parameters to construct a "
					"SrrStoredFileBlock are called file_name and file_size.")

	def _write_rawdata(self, file_name, file_size):
		# Paths always use forward slashes as the directory separator
		# File paths in RAR files use backward slashes.
		if os.sep != "/" and os.sep in file_name:
			file_name = file_name.replace(os.sep, "/")
			
		if not utility.is_good_srr(file_name): 
			raise AttributeError("Illegal Windows character used " +
			                     "somewhere in the filename/path.")
		elif file_size < 0:
			raise AttributeError("Negative file sizes do not exist.")
		elif not 0 < len(file_name) < 0xFFF3:
			raise AttributeError("Invalid file name length.")

		self.crc = 0x6A6A
		self.rawtype = 0x6A
		# indicate ADD_SIZE field and _always_ set this for this block
		self.flags = self.LONG_BLOCK
		# setting PATHS_SAVED (0x2) flag after construction doesn't do shit
		# This detection can be done afterwards and we do not set the flag.
		#if "/" in file_name:
		#	self.flags |= SrrStoredFileBlock.PATHS_SAVED
		
		self.file_name = file_name.encode("utf-8")
		self.file_size = file_size # uint (2 bytes)
		
		# full length header: basic header (7 bytes), add_size, name length
		# the size in bytes (not the number of Unicode characters).
		self._write_header(HEADER_LENGTH + 4 + 2 + len(self.file_name))
		# ADD_SIZE field: unsigned integer (4 bytes)
		self._rawdata += (struct.pack(str("<I"), file_size))
		self._rawdata += (struct.pack(str("<H"), len(self.file_name))) # ushort 
		self._rawdata += (self.file_name).encode('utf-8')

	def srr_data(self):
		""" Returns the stored file. """
		with open(self.fname, "rb") as f:
			f.seek(self.block_position + self.header_size)
			data = f.read(self.file_size)
		return data

	def renameto(self, new_name): #XXX: not a method on this level?
		""" Only works for real files. """
		if not utility.is_good_srr(new_name):
			raise AttributeError("Invalid characters used in the new name.")
		old_file_offset = self.block_position + self.header_size
		self._write_rawdata(new_name, self.file_size)
		
		# create a temporarily file
		tmpfd, tmpname = tempfile.mkstemp(prefix="file_rename-", suffix=".srr", 
		                                  dir=os.path.dirname(self.fname))
		tmpfile = os.fdopen(tmpfd, "wb")
		
		with open(self.fname, "rb") as f:
			tmpfile.write(f.read(self.block_position)) # previous block data
			tmpfile.write(self.block_bytes()) # new block header
			f.seek(old_file_offset) # go to beginning stored file
			tmpfile.write(f.read()) # read all data until EOF
			
		tmpfile.close() 
		os.remove(self.fname)
		os.rename(tmpname, self.fname)

	def explain(self):
		out = super(SrrStoredFileBlock, self).explain()
		if self.flags & RarBlock.LONG_BLOCK:
			out += "+ADD_SIZE: " + self.explain_size(self.file_size) +  \
				"(the size of the stored file)" + "\n"
		out += "+Stored file name length (2 bytes): " + self.explain_size(
		                                                len(self.file_name)) + "\n"
		out += "+Stored file name: " + self.file_name + "\n"
		return out
	
	def explain_flags(self):
		out = super(SrrStoredFileBlock, self).explain_flags()
#		if self.flags & self.PATHS_SAVED:
#			out += self.flag_format(self.PATHS_SAVED) +  \
#				"(a path is added before the file name)\n"
		return out

class SrrRarFileBlock(RarBlock):
	""" We create one SRR block (type 0x71) for each RAR file.
	It has a 7 byte header: 2 bytes for file name length, then file name.
	Flag 0x1 means recovery records have been removed if present. This
	flag is always set in newer versions of ReScene. 
	
	|CRC |TY|FLAG|SIZE| * | NL |RAR File name...|
	CRC: 0x7171
	TY: Type 0x71
	SIZE: Header Length
	NL: Name Length of RAR File name (2 bytes)
	
	The maximum length of the path + the name is 65526 (0xFFF6).
		0xFFFF - 7 - 2 = 65526 (0xFFF6)
	
	file_name: The name of the file inside a rar archive.
	"""
		
	RECOVERY_BLOCKS_REMOVED = 0x1
	PATHS_SAVED = 0x2
	SUPPORTED_FLAG_MASK = (RECOVERY_BLOCKS_REMOVED | PATHS_SAVED |
						   RarBlock.LONG_BLOCK)
	
	def __init__(self, bbytes=None, filepos=None, fname=None, file_name=None):
		if not file_name:
			super(SrrRarFileBlock, self).__init__(bbytes, filepos, fname)
			
			# 2 bytes for name length, then the name (unsigned short)
			name_length = struct.unpack(str("<H"), 
			                            self._rawdata[self._p:self._p+2])[0]
			self.file_name = self._rawdata[self._p+2:self._p+2+name_length]
			self._p += 2 + name_length
		else:
			self.crc = 0x7171
			self.rawtype = 0x71
			# earlier beta versions of ReScene .NET did not remove it
			# we always set this flag, even if there aren't RR
			self.flags = self.RECOVERY_BLOCKS_REMOVED
			self.file_name = file_name
			# Paths always use forward slashes as the directory separator
			# File paths in RAR files use backward slashes.
			if os.sep != "/" and os.sep in file_name:
				file_name = file_name.replace(os.sep, "/")
	
			# parameter: full length header
			self._write_header(HEADER_LENGTH + 2 + len(file_name))
			self._rawdata += struct.pack("<H", len(file_name)) # ushort
			self._rawdata += str(file_name)
			
	def explain_flags(self):
		out = super(SrrRarFileBlock, self).explain_flags()
		if self.flags & self.RECOVERY_BLOCKS_REMOVED:
			out += self.flag_format(self.RECOVERY_BLOCKS_REMOVED) +  \
				"(the stored recovery data is removed)\n"
		if self.flags & self.PATHS_SAVED:
			out += self.flag_format(self.PATHS_SAVED) +  \
				"(a path is added before the file name)\n"
		return out
		
	def explain(self):
		out = super(SrrRarFileBlock, self).explain()
		out += "+Rar name length (2 bytes): " + self.explain_size(
		                                        len(self.file_name)) + "\n"
		out += "+Rar name: " + self.file_name + "\n"
		return out
	
class SrrOsoHashBlock(RarBlock):
	"""SRR block that contains an OpenSubtitles.Org hash.
	http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
	
	|CRC |TY|FLAG| HL |  SIZE          |  OSO HASH      | NL |File name|
	CRC:    0x6B6B (2 bytes)
	TY:     Type 0x6B (1 byte)
	FLAG:   no flags (2 bytes)
	HL:     Header Length (2 bytes)
	
	SIZE:   File Size (8 bytes)
	        The maximum file size is 0xFFFFFFFFFFFFFFFF bytes
	OSO HASH: 64bit chksum of the first and last 64k
	NL: Name Length (2 bytes)
	    Because HL is also 2 bytes, NL can't use the full range.
	    0xFFFF - 7 - 8 - 8 - 2 = 65510 (0xFFE6)
	File name: must match a stored file name"""
	SUPPORTED_FLAG_MASK = 0
	
	def __init__(self, bbytes=None, filepos=None, fname=None,
				file_size=None, file_name=None, oso_hash=None):
		if bbytes != None:
			super(SrrOsoHashBlock, self).__init__(bbytes, filepos, fname)
			
			# 8 bytes for the file size
			self.file_size = struct.unpack("<Q", 
				self._rawdata[self._p:self._p+8])[0]
			
			# 8 bytes for the OSO hash
			self.oso_hash = "%016x" % struct.unpack("<Q", 
				self._rawdata[self._p+8:self._p+16])[0]
				
			# 2 bytes for name length, then the name (unsigned short)
			name_length = struct.unpack(str("<H"), 
				self._rawdata[self._p+16:self._p+16+2])[0]
			self.file_name = self._rawdata[self._p+18:self._p+18+name_length]
			self._p += 18 + name_length
		elif file_size != None and file_name != None and oso_hash != None:
			self.crc = 0x6B6B
			self.rawtype = 0x6B
			self.flags = 0
			
			self.file_size = file_size
			self.oso_hash = oso_hash 
			self.file_name = file_name
			
			assert len(oso_hash) == 16
		
			# parameter: full length header
			self._write_header(HEADER_LENGTH + 8 + 8 + 2 + len(file_name))
			self._rawdata += struct.pack("<Q", self.file_size) # ulonglong
			self._rawdata += struct.pack("<Q", int(self.oso_hash, 16))
			self._rawdata += struct.pack("<H", len(file_name)) # ushort
			self._rawdata += str(file_name)
		else:
			raise AttributeError("Invalid values for the constructor.")
			
	def explain(self):
		out = super(SrrOsoHashBlock, self).explain()
		out += "+File size (8 bytes): " + self.explain_size(
												self.file_size) + "\n"
		out += "+OSO hash (8 bytes): " + self.oso_hash + "\n"
		out += "+Name length (2 bytes): " + self.explain_size(
		                                        len(self.file_name)) + "\n"
		out += "+File name: " + self.file_name + "\n"
		return out

class SrrRarPaddingBlock(RarBlock):
	"""
	Some scene releases, e.g.
	    The.Numbers.Station.2013.720p.BluRay.x264-DAA
	    Stand.Up.Guys.2012.720p.BluRay.x264-DAA
	have padded bytes after the end of the RAR Archive End Block.
	This block will include those padded bytes into the SRR file.
		
	|CRC |TY|FLAG| HL |  SIZE  |
	CRC:    0x6C6C (2 bytes)
	TY:     Type 0x6C (1 byte)
	FLAG:   Long block (2 bytes)
	HL:     Header Length (2 bytes)
	        Always 7 + 4 = 11 bytes.
	"""
	def __init__(self, bbytes=None, filepos=None, fname=None,
				padding_bytes=None):
		if bbytes != None:
			super(SrrRarPaddingBlock, self).__init__(bbytes, filepos, fname)
			
			# 4 bytes for the padding size (ADD_SIZE)
			self.padding_size = struct.unpack("<I", 
				self._rawdata[self._p:self._p+4])[0]
			self._p += 4
		elif padding_bytes != None:
			self.crc = 0x6C6C
			self.rawtype = 0x6C
			self.flags = self.LONG_BLOCK
			self.padding_size = len(padding_bytes)
			self.header_size = HEADER_LENGTH + 4
			
			self._write_header(self.header_size)
			self._rawdata += struct.pack("<I", self.padding_size) # 4 bytes
			self._rawdata += padding_bytes
		else:
			raise AttributeError("Invalid values for the constructor.")
			
	def explain(self):
		out = super(SrrRarPaddingBlock, self).explain()
		out += "+Padding size (4 bytes): " + self.explain_size(
												self.padding_size) + "\n"
		return out
	
class RarVolumeHeaderBlock(RarBlock): # 0x73
	""" Archive header ( MAIN_HEAD )
	HEAD_CRC    CRC of fields HEAD_TYPE to RESERVED2                  2 bytes
	HEAD_TYPE   Header type: 0x73                                     1 byte
	HEAD_FLAGS  Bit flags:                                            2 bytes
	HEAD_SIZE   Archive header total size including archive comments  2 bytes
	RESERVED1   Reserved    2 bytes
	RESERVED2   Reserved    4 bytes
	"""
	VOLUME          = 0x0001
	COMMENT         = 0x0002
	# RAR 3.x uses the separate comment block and does not set this flag.
	# those comments use compression
	LOCK            = 0x0004
	SOLID           = 0x0008
	NEW_NUMBERING   = 0x0010
	AUTHENTICITY    = 0x0020 # RAR 3.x does not set this flag.
	PROTECTED       = 0x0040
	ENCRYPTED       = 0x0080
	FIRST_VOLUME    = 0x0100
	# other bits in HEAD_FLAGS are reserved for internal use
	ENCRYPTVER      = 0x0200
	
	SUPPORTED_FLAG_MASK = (RarBlock.SUPPORTED_FLAG_MASK | VOLUME | COMMENT |
	                       LOCK | SOLID | NEW_NUMBERING | AUTHENTICITY | 
	                       PROTECTED | ENCRYPTED | FIRST_VOLUME | ENCRYPTVER)
	def explain_flags(self):
		out = super(RarVolumeHeaderBlock, self).explain_flags()
		if self.flags & self.VOLUME:
			out += self.flag_format(self.VOLUME) + "MHD_VOLUME "  \
				"(Volume attribute (RAR is an archive volume))\n"
		if self.flags & self.COMMENT:
			out += self.flag_format(self.COMMENT) + "MHD_COMMENT "  \
				"(Archive comment present -> RAR 3.x has separate block)\n"
		if self.flags & self.LOCK:
			out += self.flag_format(self.LOCK) + "MHD_LOCK "  \
				"(Archive lock attribute)\n"
		if self.flags & self.SOLID:
			out += self.flag_format(self.SOLID) + "MHD_SOLID "  \
				"(Solid attribute (solid archive))\n"
		if self.flags & self.NEW_NUMBERING:
			out += self.flag_format(self.NEW_NUMBERING) + "MHD_NEWNUMBERING" + \
				", MHD_PACK_COMMENT " +  \
				"(New volume naming scheme ('volname.partN.rar'))\n"
		if self.flags & self.AUTHENTICITY:
			out += self.flag_format(self.AUTHENTICITY) + "MHD_AV "  \
				"(Authenticity information present)\n"
		if self.flags & self.PROTECTED:
			out += self.flag_format(self.PROTECTED) + "MHD_PROTECT "  \
				"(Recovery record present)\n"
		if self.flags & self.ENCRYPTED:
			out += self.flag_format(self.ENCRYPTED) + "MHD_PASSWORD "  \
				"(Block headers are encrypted)\n"
		if self.flags & self.FIRST_VOLUME:
			out += self.flag_format(self.FIRST_VOLUME) + "MHD_FIRSTVOLUME "  \
				"(First volume (set only by RAR 3.0 and later))\n"
		if self.flags & self.ENCRYPTVER:
			out += self.flag_format(self.ENCRYPTVER) + "MHD_ENCRYPTVER\n"
		return out
	
	def __init__(self, bbytes, filepos, fname):
		super(RarVolumeHeaderBlock, self).__init__(bbytes, filepos, fname)
		# 2 bytes + 4 bytes
		(self.reserved1, self.reserved2) = struct.unpack(str("<HL"), 
								self._rawdata[self._p:self._p+6]) 
		self._p += 6

		# TODO: look what is in the reserved places and figure it out
		if self.reserved1 != 0 or self.reserved2 != 0:
#			print self.reserved1, self.reserved2, self.fname
			pass
			
#		print self.reserved1, self.reserved2, self.fname
		# print self._rawdata[7:].encode('hex')
#		if not "000000000000" == self._rawdata[7:].encode('hex'):
##			print self._rawdata[7:].encode('hex'), self.fname
#			# only with solid archives?
#			pass

	def explain(self):
		out = super(RarVolumeHeaderBlock, self).explain()
		out += "+RESERVED1: 2 bytes: " + bytes(self.reserved1) + "\n"
		out += "+RESERVED2: 4 bytes: " + bytes(self.reserved2) + "\n"
		return out
		
class RarPackedFileBlock(RarBlock): # 0x74
	""" File header (File in archive)
	HEAD_CRC        CRC of fields from HEAD_TYPE to FILEATTR   2 bytes
	                and file name
	HEAD_TYPE       Header type: 0x74                          1 byte
	HEAD_FLAGS      Bit flags                                  2 bytes
	HEAD_SIZE       File header full size                      2 bytes
	                including file name and comments
	                
	PACK_SIZE       Compressed file size                       4 bytes
	UNP_SIZE        Uncompressed file size                     4 bytes
	HOST_OS         Operating system used for archiving        1 byte
	FILE_CRC        File CRC                                   4 bytes
	FTIME           Date and time in standard MS DOS format    4 bytes
	UNP_VER         RAR version needed to extract file         1 byte
	                Version number is encoded as
	                10 * Major version + minor version.
	METHOD          Packing method                             1 byte
	NAME_SIZE       File name size                             2 bytes (27-28)
	ATTR            File attributes                            4 bytes
	
	HIGH_PACK_SIZE  High 4 bytes of 64 bit value of compressed     4 bytes
	                file size. Optional value, presents only if
	                bit 0x100 in HEAD_FLAGS is set.
	HIGH_UNP_SIZE   High 4 bytes of 64 bit value of uncompressed   4 bytes
	                file size. Optional value, presents only
	                if bit 0x100 in HEAD_FLAGS is set.
	FILE_NAME       File name - string of NAME_SIZE bytes size
	SALT            present if (HEAD_FLAGS & 0x400) != 0       8 bytes
	EXT_TIME        present if (HEAD_FLAGS & 0x1000) != 0      variable size
	
	other new fields may appear here.
	"""
	SPLIT_BEFORE   = 0x0001 # file continued from previous volume
	SPLIT_AFTER	   = 0x0002 # file continued in next volume
	PASSWORD       = 0x0004 # file encrypted with password
	COMMENT        = 0x0008 # file comment present -> < RAR 3.0
	SOLID          = 0x0010 # information from previous files is used
	DICT64         = 0x0000
	DICT128	       = 0x0020
	DICT256	       = 0x0040
	DICT512        = 0x0060
	DICT1024       = 0x0080
	DICT2048       = 0x00a0
	DICT4096       = 0x00c0
	DIRECTORY      = 0x00e0 # file is directory
	LARGE_FILE     = 0x0100 # for very large files (> 2GiB)
	# Outcasts.S01E06.720p.HDTV.x264-BiA does have it (ARCHiVE SiZE: 1493MB)
	UTF8_FILE_NAME = 0x0200 # Unicode name available
	SALT           = 0x0400 # 8 byte salt is present
	VERSION        = 0x0800 # a version number is appended to the name
	EXT_TIME       = 0x1000 # extra time field present
	EXTFLAGS       = 0x2000 # never used
	
	SUPPORTED_FLAG_MASK = (SPLIT_BEFORE | SPLIT_AFTER | PASSWORD | COMMENT |
	                       SOLID | DICT64 | DICT128 | DICT256 | DICT512 |
	                       DICT1024 | DICT2048 | DICT4096 | DIRECTORY |
	                       LARGE_FILE | UTF8_FILE_NAME | SALT | VERSION |
	                       EXT_TIME | EXTFLAGS | RarBlock.SUPPORTED_FLAG_MASK)

	def __init__(self, blockbytes, filepos, fname):
		super(RarPackedFileBlock, 
			  self).__init__(blockbytes, filepos, fname)

		# 4 bytes for packed size, 4 for unpacked
		# 1 byte for OS, 4 bytes for crc
		# 4 bytes for file date/time, 1 for required RAR version
		# 1 byte for compression method, then 2 for filename length
		# 4 bytes for file attributes
		(self.packed_size, self.unpacked_size, self.os, self.file_crc,
		 self.file_datetime, self.rar_version, self.compression_method,
		 filename_length, self.file_attributes) =  \
		 struct.unpack(str("<IIBIIBBHI"), self._rawdata[self._p:self._p+25])
		self._p += 25
		# If large file flag is set, next are 4 bytes each
		# for high order bits of file sizes.
		if self.flags & self.LARGE_FILE == self.LARGE_FILE:
			self.high_pack_size = struct.unpack("<I", 
			                        self._rawdata[self._p:self._p+4])[0]
			self.high_unpack_size = struct.unpack("<I", 
			                          self._rawdata[self._p+4:self._p+4+4])[0]
			self.packed_size += self.high_pack_size * 0x100000000
			self.unpacked_size += self.high_unpack_size * 0x100000000
			self._p += 8
			# TODO: write tests when high pack size is used
		# BiA releases that don't set the ADD_SIZE flag
		# get the correct additional size
		self.add_size = self.packed_size

		# CMT: Comment
		# RR: Recovery Record
		# AV: Authenticity Verification
		
		# Copyright (c) 2005-2010  Marko Kreen <markokr@gmail.com>
		self.file_datetime = _parse_dos_time(self.file_datetime)
		self.file_name = self._rawdata[self._p:self._p+filename_length]
		self._p += filename_length
		if self.flags & RarPackedFileBlock.UTF8_FILE_NAME:
			null = self.file_name.find(ZERO) # index zero byte
			self.orig_filename = self.file_name[:null]
			u = UnicodeFilename(self.orig_filename, self.file_name[null + 1:])
			self.unicode_filename = u.decode()
		else:
			self.orig_filename = self.file_name
			self.unicode_filename = self.file_name.decode(DEFAULT_CHARSET, 
			                                              "replace")
		self.file_name = self.unicode_filename
		
		if self.flags & self.SALT:
			self.salt = self._rawdata[self._p:self._p + 8]
			self._p += 8
		else:
			self.salt = None

		# optional extended time stamps
		if self.flags & self.EXT_TIME:
			self._p = _parse_ext_time(self, self._p)
		else:
			self.mtime = self.atime = self.ctime = self.arctime = None
			
		# other new fields may appear here
		# e.g. recovery fields used in a RarNewSubBlock

	def explain(self):
		out = super(RarPackedFileBlock, self).explain()
		out += "+PACK_SIZE: %i bytes (ADD_SIZE + HIGH_PACK_SIZE field)\n" % \
		       self.packed_size 
		out += "+UNP_SIZE: %i bytes\n" % self.unpacked_size
		out += "+HOST_OS: " + self.get_os() + "\n"
		out += "+FILE_CRC: %X\n" % self.file_crc
		out += "+FTIME: %s\n" % self.ftime(self.file_datetime)
		out += "+UNP_VER: " + self.get_version() + "\n"
		out += "+METHOD: " + self.get_compression_name() + "\n"
		out += "+NAME_SIZE: always present\n"
		# TODO: http://phpbuilder.com/manual/en/function.rar-getattr.php
		out += "+ATTR: %X\n" % self.file_attributes
		if self.flags & self.LARGE_FILE:
			out += "+HIGH_PACK_SIZE: %i\n" % self.high_pack_size
			out += "+HIGH_UNP_SIZE: %i\n" % self.high_unpack_size
		out += "+FILE_NAME: %s\n" % self.file_name
		if self.flags & self.SALT:
			out += "+SALT: %X\n" % self.salt
		if self.flags & self.EXT_TIME:
			out += "+modification time: %s\n" % self.ftime(self.atime)
			out += "+access time: %s\n" % self.ftime(self.mtime)
			out += "+metadata change time: %s\n" % self.ftime(self.ctime)
			out += "+arc time: %s\n" % self.ftime(self.arctime)
		return out
	
	def ftime(self, timetuple):
		"""Formats the time tuple to a string."""
		if not timetuple:
			return "UNKNOWN"
		return "%04d-%02d-%02d %02d:%02d:%02d" % timetuple
	
	def get_compression_name(self):
		return COMPRESSION_NAME[self.compression_method]
	
	def is_compressed(self):
		return self.compression_method != 0x30 # Storing
	
	def get_compression_parameter(self):
		"""
		Returns Rar.exe compression parameter
		m<0..5>       Set compression level (0-store...3-default...5-maximal)
		"""
		compression_parameter = {
			0x30: "-m0",
			0x31: "-m1",
			0x32: "-m2",
			0x33: "-m3",
			0x34: "-m4",
			0x35: "-m5"
		}
		return compression_parameter[self.compression_method]
	
	def get_dictionary_size_parameter(self):
		"""
		Returns Rar.exe dictionary size parameter
		md<size>   Dictionary size in KB (64,128,256,512,1024,2048,4096 or A-G)
		"""
		if self.flags & self.DICT4096 == self.DICT4096:
			return "-mdG"
		elif self.flags & self.DICT2048 == self.DICT2048:
			return "-mdF"
		elif self.flags & self.DICT1024 == self.DICT1024:
			return "-mdE"
		elif self.flags & self.DICT512 == self.DICT512:
			return "-mdD"
		elif self.flags & self.DICT256 == self.DICT256:
			return "-mdC"
		elif self.flags & self.DICT128 == self.DICT128:
			return "-mdB"
		elif self.flags & self.DICT64 == self.DICT64:
			return "-mdA"
	
	def get_os(self):
		return "%s used to create this file block." % OS_NAME[self.os]
	
	def get_dictionary(self):
		return DICTIONARY_NAME[(self.flags & 0x00e0) >> 5]
	
	def get_dict_size(self):
		if self.flags & self.DICT4096 == self.DICT4096:
			return 4096*1024
		elif self.flags & self.DICT2048 == self.DICT2048:
			return 2048*1024
		elif self.flags & self.DICT1024 == self.DICT1024:
			return 1024*1024
		elif self.flags & self.DICT512 == self.DICT512:
			return 512*1024
		elif self.flags & self.DICT256 == self.DICT256:
			return 256*1024
		elif self.flags & self.DICT128 == self.DICT128:
			return 128*1024
		elif self.flags & self.DICT64 == self.DICT64:
			return 64*1024

	def get_version(self):
		return "Version %d.%d is needed to extract." %  \
			divmod(self.rar_version, 10)

	def explain_flags(self):
		out = super(RarPackedFileBlock, self).explain_flags()
		if self.flags & self.SPLIT_BEFORE:
			out += self.flag_format(self.SPLIT_BEFORE) + "LHD_SPLIT_BEFORE "  \
				"(file continued from previous volume)\n"
		if self.flags & self.SPLIT_AFTER:
			out += self.flag_format(self.SPLIT_AFTER) + "LHD_SPLIT_AFTER "  \
				"(file continued in next volume)\n"
		if self.flags & self.PASSWORD:
			out += self.flag_format(self.PASSWORD) + "LHD_PASSWORD "  \
				"(file encrypted with password)\n"
		if self.flags & self.COMMENT:
			out += self.flag_format(self.COMMENT) + "LHD_COMMENT "  \
				"(file comment present -> RAR 3.x has separate block)\n"
		if self.flags & self.SOLID:
			out += self.flag_format(self.SOLID) + "LHD_SOLID" + \
				"(information from previous files is used (solid flag) 2.0+)\n"
		if self.flags & self.LARGE_FILE:
			out += self.flag_format(self.LARGE_FILE) + "LHD_LARGE "  \
				"(only used for files larger then 2GiB)\n"
		if self.flags & self.UTF8_FILE_NAME:
			out += self.flag_format(self.UTF8_FILE_NAME) + "LHD_UNICODE "  \
				"(Unicode name separated by zero also available)\n"
		if self.flags & self.SALT:
			out += self.flag_format(self.SALT) + "LHD_SALT "  \
				"(the header contains additional 8 bytes" +  \
				" to increase encryption security)\n"
		if self.flags & self.VERSION:
			out += self.flag_format(self.VERSION) + "LHD_VERSION "  \
				"(an old file version, appended to file name as ';n')\n"
		if self.flags & self.EXT_TIME:
			out += self.flag_format(self.EXT_TIME) + "LHD_EXTTIME "  \
				"(Extended time field present)\n"
		if self.flags & self.EXTFLAGS:
			out += self.flag_format(self.EXTFLAGS) + "LHD_EXTFLAGS "  \
				"(never used)\;"
		out += self.flag_format(self.flags & self.DIRECTORY) +  \
				"LHD_WINDOW (" + self.get_dictionary() + ")\n"
		return out

class RarNewSubBlock(RarPackedFileBlock): # 0x7A
	""" RarNewSubBlock is used for AV, CMT, RR. 
	http://stackoverflow.com/questions/8126645/
	on-which-data-is-the-filecrc-in-newsub-head-of-a-rar-recovery-record-based/
	crc = crc32(data, ~0x0fffffff)
	"""
	#(FILE and NEWSUB share the same structure)
	def __init__(self, blockbytes, filepos, fname):
		super(RarNewSubBlock, self).__init__(blockbytes, filepos, fname)
		
		if self.file_name == "RR":
			# skip 8 bytes for 'Protect+' (also part of the header)
			# 4 bytes for recovery sector count, 8 bytes for data sector count
			(self.recovery_sectors, self.data_sectors) =  \
				struct.unpack("<IQ", self._rawdata[self._p+8:self._p+8+12])
			self.is_recovery = True
			self._p += 8 + 4 + 8
		else:
			self.is_recovery = False
			
	def explain(self):
		out = super(RarNewSubBlock, self).explain()
		if self.file_name == "RR":
			out += "+RR: Recovery Record\n"
			out += "+Recovery sectors: %i\n" % self.recovery_sectors
			out += "+Data sectors: %i\n" % self.data_sectors
			out += "+Protect+\n"
		elif self.file_name == "AV":
			out += "+AV: Authentication Verification\n"
		elif self.file_name == "CMT":
			out += "+CMT: Comment\n"
		else:
			out += "+UKNOWN RarNewSubBlock FOUND!\n"
		return out
			
class RarOldRecoveryBlock(RarBlock): # 0x78
	def __init__(self, blockbytes, filepos, fname):
		super(RarOldRecoveryBlock, self).__init__(blockbytes, filepos, fname)
		# 2 bytes for packed size
		# 1 byte for RAR version
		# 2 bytes for recovery sector count
		# 4 bytes for data sector count
		(self.packed_size, self.rar_version, self.recovery_sectors,
		 self.data_sectors) = struct.unpack("<IBHI", 
		                                    self._rawdata[self._p:self._p+11])
		# next 8 bytes for 'Protect!'
		self._p += 11 + 8
		# Protect! is part of the header (last field before the recovery data)
		
		# for when the ADD_SIZE flag isn't set
		self.add_size = self.packed_size
	
	def explain(self):
		out = super(RarOldRecoveryBlock, self).explain()
		out += "+ADD_SIZE: " + self.explain_size(self.packed_size) +  \
			"(the size of the packed recovery data)\n"
		try:
			version = RAR_VERSION[self.rar_version]
		except KeyError:
			version = self.rar_version
		out += "+Rar version (1 byte): %s\n" % version
		out += "+Recovery sectors: %i\n" % self.recovery_sectors
		out += "+Data sectors: %i\n" % self.data_sectors
		out += "+Protect!\n"
		return out
	
class RarEndArchiveBlock(RarBlock):
	""" Last block of a RAR file. This block is optional. From rar.exe:
	  en    Do not put 'end of archive' block
	  
	Block with length 26 bytes found! gvd-herorpk1.r40
	Hero.Directors.Cut.German.2002.WS.DVDRIP.REPACK.AC3.XviD-GVD
	e069 7b 0f40 1a00  ec30ef94  2900  00000000000000  _000000000000_
	+FTIME: 2005-07-23 13:22:12
	+UNP_VER: Version 2.9 is needed to extract.
	+FILE_NAME: AV -> last zeros something to do with this?
	"""
	NEXT_VOLUME = 0x0001 # // not last volume
	DATACRC	    = 0x0002 # 4 bytes
	REVSPACE    = 0x0004 # 7 bytes
	VOLNUMBER   = 0x0008 # 2 bytes
	
	SUPPORTED_FLAG_MASK = (RarBlock.SUPPORTED_FLAG_MASK | NEXT_VOLUME |
	                       DATACRC | REVSPACE | VOLNUMBER)

	def __init__(self, blockbytes, filepos, fname):
		super(RarEndArchiveBlock, self).__init__(blockbytes, filepos, fname)
		# see if there are fields we can read
		if self.flags & RarEndArchiveBlock.DATACRC:
			# // store CRC32 of RAR archive (now used only in volumes)
			self.rarcrc = struct.unpack(str("<I"), 
			                         self._rawdata[self._p:self._p+4])
			self._p += 4
		if self.flags & RarEndArchiveBlock.VOLNUMBER:
			# // store a number of current volume
			self.volume_number = struct.unpack(str("<H"), 
			                         self._rawdata[self._p:self._p+2])
			self._p += 2
#		if self.flags & RarEndArchiveBlock.REVSPACE:
#			# // reserve space for end of REV file 7 byte record
#			# WinRAR Recovery Volume File
#			assert self._p + 7 == self.header_size
	
	def explain_flags(self):
		out = super(RarEndArchiveBlock, self).explain_flags()
		if self.flags & self.NEXT_VOLUME:
			out += self.flag_format(self.NEXT_VOLUME) +  \
				"(not the last volume)\n"
		if self.flags & self.DATACRC:
			out += self.flag_format(self.DATACRC) +  \
				"(store CRC32 of RAR archive (now used only in volumes))\n"
		if self.flags & self.REVSPACE:
			out += self.flag_format(self.REVSPACE) +  \
				"(reserve space for end of REV file 7 byte record)\n"
		if self.flags & self.VOLNUMBER:
			out += self.flag_format(self.VOLNUMBER) +  \
				"(store a number of current volume)\n"
		return out
		
	def explain(self):
		out = super(RarEndArchiveBlock, self).explain()
		if self.flags & RarEndArchiveBlock.DATACRC:
			out += "+RAR CRC (4 bytes): %X\n" % self.rarcrc
		if self.flags & RarEndArchiveBlock.VOLNUMBER:
			out += "+Volume number (2 bytes): %d\n" % self.volume_number
		return out

# to get the right class based on a hexadecimal number
BTYPES_CLASSES = {
	BlockType.SrrHeader: SrrHeaderBlock,
	BlockType.SrrStoredFile: SrrStoredFileBlock,
	BlockType.SrrRarFile: SrrRarFileBlock,
	BlockType.SrrOsoHash: SrrOsoHashBlock,
	BlockType.SrrRarPadding: SrrRarPaddingBlock,
	BlockType.RarVolumeHeader: RarVolumeHeaderBlock,
	BlockType.RarPackedFile: RarPackedFileBlock,
	BlockType.RarOldRecovery: RarOldRecoveryBlock,
	BlockType.RarNewSub: RarNewSubBlock,
	BlockType.RarMin: RarBlock,
	BlockType.RarMax: RarEndArchiveBlock,
	BlockType.RarOldComment: RarBlock,
	BlockType.RarOldSubblock: RarBlock,
	BlockType.RarOldAuthenticity76: RarBlock,
	BlockType.RarOldAuthenticity79: RarBlock,
}
		
###############################################################################
	
class RarReader(object):
	""" A simple Reader class that reads through 
		RAR or SRR files one block at a time. """
	RAR, SRR, SFX = list(range(3))
	
	def __init__(self, rfile, file_length=0, enable_sfx=False):
		""" If the file is a part of a stream, (e.g. RAR in SRR)
			the file_length must be given. """
		if isinstance(rfile, io.IOBase): 
			# the file is supplied as a stream
			self._rarstream = rfile
		else: # file on hard drive
			try:
				self._rarstream = open(rfile, mode="rb")
			except (IOError, TypeError):
				raise ArchiveNotFoundError(sys.exc_info()[1])
		
		# get the length of the stream
		self._initial_offset = self._rarstream.tell()
		if not file_length:
			self._rarstream.seek(0, 2) # 2: move relative to end of file
			self._file_length = self._rarstream.tell() - self._initial_offset
		else:
			self._file_length = file_length

		# http://en.wikipedia.org/wiki/RAR says:
		# "The minimum size of a RAR file is 20 bytes."
		#  - 7 bytes marker block
		#  - 13 bytes archive header block
		# WinRAR 7 bytes rar file: (does not even open and gives pop-up)
		#	"The archive is either in unknown format or damaged."
		# Minimum 20 bytes minus last \x00:
		#	"The archive header is corrupt"
		#	"Unexpected end of archive"
		#	"The archive is either in unknown format or damaged"
		if (self._file_length - self._initial_offset) < 20:
			raise ValueError("The file is too small. "
							 "The minimum RAR size is 20 bytes.")
		else: # determine the read mode based on the raw flag type
#			self._rarstream.seek(self._initial_offset + 2) # third byte
#			block_type = ord(self._rarstream.read(1))
			# read 7 bytes so Usenet error correction can kick in
			self._rarstream.seek(self._initial_offset)
			bheader = self._rarstream.read(7)
			block_type = ord(bheader[2:3]) # third byte
			if block_type == BlockType.RarMin: # 0x72
				self._readmode = self.RAR
			elif block_type == BlockType.SrrHeader: # 0x69
				self._readmode = self.SRR
				self.recovery_records_removed = True # init to be sure
			elif enable_sfx: # SFX ?
				# TODO: make it resceneable
				# search for RAR marker block offset
				# 79280 for wrar400.exe
				# 123904 for wrar-x64-400.exe
				self._rarstream.seek(self._initial_offset)
				data = self._rarstream.read(0x100000) # unrar max SFX size
				offset = data.find(RAR_MARKER_BLOCK)
				self._initial_offset += offset
				if offset < 0 or self._initial_offset > self._file_length:
					raise ValueError("The file is not a valid .rar archive"
					                 " or .srr file.")
				self._readmode = self.SFX
				# What kind of errors if SRR is detected as SFX?
				#	 srr_detected_as_sfx.exe EnvironmentError: 
				#	 Invalid RAR block length (46325) at offset 0x124
			else:
				raise ValueError("SFX support not on or not a RAR archive.")
		self._rarstream.seek(self._initial_offset)
		self._current_index = 0
		self._rar_end_block_encountered = False # for detecting padding

	def __del__(self):
		try: # close the file/stream
			self._rarstream.close()
		except:
			pass
		
	def _read(self):
		"""Archive processing is made in the following manner: (unrar)
		1. Read and check marker block
		2. Read archive header
		3. Read or skip HEAD_SIZE-sizeof(MAIN_HEAD) bytes
		4. If end of archive encountered then terminate archive processing,
		   else read 7 bytes into fields HEAD_CRC, HEAD_TYPE, HEAD_FLAGS,
		   HEAD_SIZE.
		5. Check HEAD_TYPE.
		   if HEAD_TYPE==0x74
			 read file header ( first 7 bytes already read )
			 read or skip HEAD_SIZE-sizeof(FILE_HEAD) bytes
			 if (HEAD_FLAGS & 0x100)
			   read or skip HIGH_PACK_SIZE*0x100000000+PACK_SIZE bytes
			 else
			   read or skip PACK_SIZE bytes
		   else
			 read corresponding HEAD_TYPE block:
			   read HEAD_SIZE-7 bytes
			   if (HEAD_FLAGS & 0x8000)
				 read ADD_SIZE bytes
		6. go to 4.
		
		EnvironmentError: 
		"""
		block_start_position = self._rarstream.tell()
		
		if block_start_position == self._file_length:
			return None # The end.
	
		# make sure we can at least read the basic block header
		#   otherwise you would get this error:
		#   error: unpack requires a string argument of length 7
		if block_start_position + HEADER_LENGTH > self._file_length:
			if (self._rar_end_block_encountered and self._readmode == self.RAR):
				return SrrRarPaddingBlock(padding_bytes=self._rarstream.read())
			else:
				raise EnvironmentError("Cannot read basic block header.")

		""" The block header is always 7 bytes: (see struct BaseBlock unrar)
		  - 2 for crc,                  H  unsigned short
			  HEAD_CRC      2 bytes     CRC of total block or block part
		  - 1 for block type,           B  unsigned char (8-bit integer)
			  HEAD_TYPE     1 byte      Block type
		  - 2 for flags,                H  unsigned short
			  HEAD_FLAGS    2 bytes     Block flags
		  - and 2 for header length.    H  unsigned short
			  HEAD_SIZE     2 bytes     Block size
			  ADD_SIZE      4 bytes     Optional field - added block size

		byte order: < little-endian
		
		Marker block: Rar!\x1A\x07\x00 (magic number)
					  (0x52 0x61 0x72 0x21 0x1a 0x07 0x00)
		is considered a fixed byte.
		"""
		header_buffer = self._rarstream.read(HEADER_LENGTH)
		fmt = str("<HBHH")
		(_crc, btype, flags, hsize) = struct.unpack(fmt, header_buffer)
		
		# detect padding bytes
		if (self._rar_end_block_encountered and self._readmode == self.RAR):
			return SrrRarPaddingBlock(
				padding_bytes=header_buffer + self._rarstream.read())
		
		# one more sanity check on the length before continuing
		if (hsize < HEADER_LENGTH or 
			block_start_position + hsize > self._file_length):
			#XXX: ValueError would be better, no?
#			print("Header buffer: %s" % header_buffer.encode('hex'))
			raise EnvironmentError("Invalid RAR block length (" + str(hsize) +\
					") at offset {0:#x}".format(self._rarstream.tell() - 2))
		elif hsize == HEADER_LENGTH: # Marker block
			if btype == BlockType.SrrHeader: # minimal block in C implementation
				return SrrHeaderBlock(header_buffer, block_start_position, 
									  self._rarstream) 
			if _DEBUG:
				assert btype == BlockType.RarMin or btype == BlockType.RarMax
			return RarBlock(header_buffer, block_start_position, 
							self._rarstream)
		
		# read the rest of the block (we already have the basic header)
		block_buffer = header_buffer + self._rarstream.read(hsize - 
		                                                    HEADER_LENGTH)
		
		# If RAR LONG_BLOCK flag is set -> extra block length
		# Or if this is a File or NewSub block. -> e.g. BiA Outcasts releases
		# (always additional length, but flag not always set (e.g. CMT))
		# The next 4 bytes are additional data size.
		add_size = struct.unpack(str("<I"), block_buffer[7:7+4])[0]  \
			if flags & RarBlock.LONG_BLOCK or  \
			btype == BlockType.RarPackedFile or  \
			btype == BlockType.RarNewSub else 0
		# RAR files larger than 4GB are possible: skip this data later

		# Check to see if this is a recovery record.  
		# * Old-style recovery records are stored in block type 0x78.
		# * New-style recovery records are stored in 
		#   the RAR NEWSUB block type (0x7A) and 
		#   have file name length of 2 (bytes 27 and 28)   NAME_SIZE
		#   and a file name of RR (bytes 33 and 34)        HIGH_PACK_SIZE
		is_recovery = btype == BlockType.RarOldRecovery or  \
				( btype == BlockType.RarNewSub and
				  hsize > 34 and
				  struct.unpack("<H", block_buffer[26:26+2])[0] == 2 and
				  block_buffer[32] == "R" and
				  block_buffer[33] == "R" )
				
		# What if we have a very old SRR with the actual RR stored?
		if self._readmode == self.SRR:
			if btype == BlockType.SrrRarFile:
				self.recovery_blocks_removed = (flags & 
				              SrrRarFileBlock.RECOVERY_BLOCKS_REMOVED)
			elif is_recovery and not self.recovery_blocks_removed:
				self._rarstream.seek(add_size, 1)
			
		# If there is additional data in the block, decide whether
		# we want to include it in the RarBlock we return.
		# We don't return the additional data for _file blocks_
		# or _recovery records_. 
		# We do not read files added to the SRR. (ReScene .NET 1.2 does) 
		if btype == BlockType.SrrStoredFile:
			# pass extra header info, but not the whole file!
			#  -> not a problem for .sfv, .nfo and .srr,
			#	 but we do not put huge samples unnecessary in memory
			# skip the file contents, relative to current position
			self._rarstream.seek(add_size, 1)
		elif btype != BlockType.RarPackedFile and  \
				not is_recovery and add_size > 0:
			block_buffer += self._rarstream.read(add_size)

		# If we're not returning the data, skip over it, 
		# but only for RAR or SFX mode. 
		# The data isn't there in the SRR, so need need to skip.
		elif self._readmode in (self.RAR, self.SFX) and add_size > 0:
			self._rarstream.seek(add_size, 1) # relative to current position

		assert (len(BTYPES_CLASSES) == 
				len([t for t in dir(BlockType) if not t.startswith("__")]))
		# for releases such as Haven.S02E05.HDTV.XviD-P0W4:
		# except for the header size field, everything in the rar
		# archive end block are null bytes -> still create RarBlock
		rar_block = BTYPES_CLASSES.get(btype, RarBlock)(block_buffer, 
				block_start_position, self._rarstream.name)
		
		# for very large RAR files, skipping add_size isn't enough
		if (btype == BlockType.RarPackedFile and 
			rar_block.flags & RarPackedFileBlock.LARGE_FILE ==
			RarPackedFileBlock.LARGE_FILE and
			self._readmode in (self.RAR, self.SFX)):
			self._rarstream.seek(block_start_position + hsize)
			self._rarstream.seek(rar_block.packed_size, os.SEEK_CUR)
			
		if btype == BlockType.RarMax:
			self._rar_end_block_encountered = True
		
		return rar_block
	
	def read_all(self):
		""" Parse the whole rar/srr file. The results are cached.
		Closes the open file. """
		# the list is not empty -> function has been called before: use cache
		try:
			return self._found_blocks 
		except AttributeError:
			self._rarstream.seek(self._initial_offset)
			self._found_blocks = []
			for block in self:
#				print(block)
				self._found_blocks.append(block)
#			self._found_blocks = [block for block in self]
			self.__del__()
			return self._found_blocks
	
	def list_files(self):
		""" 
		RAR, SFX: returns a list of archived files.
		SRR:	  returns a list of stored files.
				  (not the archives that can be reconstructed)
		"""
		self.read_all()
		
		if self._readmode in (self.RAR, self.SFX):
			files = [b.file_name for b in self._found_blocks
			                     if isinstance(b, RarPackedFileBlock)]
		else:
			files = [b.file_name for b in self._found_blocks
			                     if isinstance(b, SrrStoredFileBlock)]
		return files

	def file_type(self):
		""" Returns whether this RarReader reads a RAR, SRR or SFX file. """
		return self._readmode
	
	def __next__(self):
		if self._rarstream.closed:
			try:
				self._current_index += 1
				return self._found_blocks[self._current_index - 1]
			except:
				self._current_index = 0
				raise StopIteration
		try:
			block = self._read()
		except EnvironmentError: # corrupt file found
			self._rarstream.close() # so it's possible to move the bad file
			raise
		if not block:
			self._rarstream.seek(self._initial_offset)
			raise StopIteration
		return block
	
	def next(self): #@ReservedAssignment necessary for Python 2
		# http://www.python.org/dev/peps/pep-3114/
		return self.__next__()
	
	def __iter__(self):
		return self

	def close(self):
		self._rarstream.close()
