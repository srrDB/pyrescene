#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
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

# Docs for a quicker understanding:
# http://wiki.multimedia.cx/index.php?title=QuickTime_container
# http://code.google.com/p/mp4parser/

import struct

import sys
from os.path import join, dirname, realpath
# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..', 'rescene'))
import rescene

#S_BYTE = struct.Struct('>B') # unsigned char: 1 byte
#S_SHORT = struct.Struct('>H') # unsigned short: 2 bytes
S_LONG = struct.Struct('>L') # unsigned long: 4 bytes
S_LONGLONG = struct.Struct('>Q') # unsigned long long: 8 bytes

class SeekOrigin(object): # build into io, but not available in Python 2.6
	""" 'whence' parameter seek functions
	From where to start seeking in a file. 
	Internal class only used in RarStream. """
	SEEK_SET, SEEK_CUR, SEEK_END = list(range(3)) 

class MovReadMode(object):
	MP4, Sample, SRS = list(range(3))
	# MP4 == Sample, but doesn't throw InvalidDataException
	
class InvalidDataException(ValueError):
	pass

#class MovAtomType(object):
#	FTYPE = "ftyp"
	
class Atom(object):
	def __init__(self, size, atom_type):
		self.size = size
		self.type = atom_type
		self.raw_header = ""
		self.start_pos = -1
		
	def __repr__(self, *args, **kwargs):
		return "<Atom type=%s size=%d start_pos=%d>" % (self.type, 
													self.size, self.start_pos)
		
class Box(Atom):
	pass

class FullBox(Atom):
	pass
		
class SomethingAtom(Atom):
	pass
	
class MovReader(object):
	"""Implements a simple Reader class that reads through MP4 
	or MP4-SRS files one atom/box at a time.
	atom: QuickTime File Format
	box: ISO/IEC 14496-12:2008"""
	def __init__(self, read_mode, path=None, stream=None):
		assert path or stream
		if path:
			if rescene.utility.is_rar(path):
				self._mov_stream = rescene.rarstream.RarStream(path)
			else:
				self._mov_stream = open(path, 'rb')
		elif stream:
			self._mov_stream = stream
		self._mov_stream.seek(0, 2)
		self._file_length = self._mov_stream.tell()
		self._mov_stream.seek(0)
		self.mode = read_mode

		self.read_done = True
		self.current_atom = None
		self.atom_type = None

	def read(self):
		# "Read() is invalid at this time", "MoveToChild(), ReadContents(), or 
		# SkipContents() must be called before Read() can be called again")
		assert self.read_done or (self.mode == MovReadMode.SRS and
								self.atom_type == "mdat")
		
		
		atom_start_position = self._mov_stream.tell()
		self.current_atom = None
		self.read_done = False
		
		# no room for size (4B) and type (4B) of the atom
		if atom_start_position + 8 > self._file_length:
			return False
		
		self._atom_header = self._mov_stream.read(8)
		# 4 bytes for atom length, 4 bytes for atom type
		(atom_length,) = S_LONG.unpack(self._atom_header[:4])
		self.atom_type = self._atom_header[4:]
		
#		print atom_length
#		print self._atom_header[:4].encode('hex')
		
		# special sizes
		hsize = 8
		if atom_length == 1:
			# 8-byte size field after the atom type
			bsize = self._mov_stream.read(8)
			(atom_length,) = S_LONGLONG.unpack(bsize)
			self._atom_header += bsize
			hsize += 8
		elif atom_length == 0:
			# the atom extends to the end of the file
			atom_length = self._file_length - 8 - atom_start_position
			#print("Box without size found.")

		# sanity check on atom length
		# Skip check on mdat so we can still report expected size.
		# This is only applied on samples,
		# since a partial movie might still be useful.
		endOffset = atom_start_position+ atom_length # + hsize 
		if (self.mode == MovReadMode.Sample and self.atom_type != "mdat" and 
			endOffset > self._file_length):
#			print(atom_start_position, hsize, atom_length)
#			print(endOffset)
#			print(self._file_length)
			raise InvalidDataException("Invalid box length at 0x%08X" % 
									atom_start_position)
		
		self.current_atom = Atom(atom_length, self.atom_type)
		self.current_atom.raw_header = self._atom_header
		self.current_atom.start_pos = atom_start_position
#		print(self.current_atom)
		
		self._mov_stream.seek(atom_start_position, SeekOrigin.SEEK_SET)
		"moov"
		"ftyp"
		"mdat"
		# Apple Computer reserves
		# all four-character codes consisting entirely of lowercase letters.

#		if atom_type == "RIFF" or atom_type == "LIST":
#			# if the atom_type indicates a list type (RIFF or LIST), 
#			# there is another atom_type code in the next 4 bytes
#			listType = atom_type
#			self._atom_header += self._mov_stream.read(4)
#			atom_type = self._atom_header[8:4]
#			atom_length -= 4
#			
#			self.chunk_type = RiffChunkType.List
#			self.current_chunk = RiffList()
#			self.current_chunk.list_type = listType
#			self.current_chunk.fourcc = atom_type
#			self.current_chunk.length = atom_length
#			self.current_chunk.raw_header = self._atom_header
#			self.current_chunk.chunk_start_pos = atom_start_position
#		else:
#			if (self._atom_header[0].isdigit() and 
#				self._atom_header[1].isdigit()):
#				self.current_chunk = MoviChunk()
#				self.current_chunk.fourcc = atom_type
#				self.current_chunk.length = atom_length
#				self.current_chunk.raw_header = self._atom_header
#				self.current_chunk.chunk_start_pos = chunk_start_position
#				self.current_chunk.stream_number =  int(atom_type[:2])
#				self.chunk_type = RiffChunkType.Movi
#			else:
#				self.current_chunk = RiffChunk()
#				self.current_chunk.fourcc = atom_type
#				self.current_chunk.length = atom_length
#				self.current_chunk.raw_header = self._atom_header
#				self.current_chunk.chunk_start_pos = chunk_start_position
#				self.chunk_type = RiffChunkType.Unknown


		return True
	
	def read_contents(self):
		# if read_done is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
#			self._mov_stream.seek(-self.current_atom.size, SeekOrigin.SEEK_CUR)
			self._mov_stream.seek(self.current_atom.start_pos, 
			                      SeekOrigin.SEEK_SET)

		self.read_done = True
		buff = ""

		# do always when it's not a SRS file
		# else skip it when encountering removed data
		if (self.mode != MovReadMode.SRS or 
			self.atom_type != "mdat"):
			# skip header bytes
			hl = len(self.current_atom.raw_header)
			self._mov_stream.seek(hl, SeekOrigin.SEEK_CUR)
			buff = self._mov_stream.read(self.current_atom.size - hl)
		return buff
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			# do always when it's not a SRS file
			# else skip it when encountering removed data
			if (self.mode != MovReadMode.SRS 
				or self.atom_type != "mdat"):
				self._mov_stream.seek(self.current_atom.start_pos + 
				                      self.current_atom.size, 
				                      SeekOrigin.SEEK_SET)

	def move_to_child(self):
		self.read_done = True
		# skip the header bytes
		hl = len(self.current_atom.raw_header)
		self._mov_stream.seek(hl, SeekOrigin.SEEK_CUR)
	
	def __del__(self):
		try: # close the file/stream
			self._mov_stream.close()
		except:
			pass
			