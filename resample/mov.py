#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2014 pyReScene
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

import os
import struct

from rescene.utility import is_rar
from rescene.rarstream import RarStream

BE_LONG = struct.Struct('>L') # unsigned long: 4 bytes
BE_LONGLONG = struct.Struct('>Q') # unsigned long long: 8 bytes

class MovReadMode(object):
	MP4, Sample, SRS = list(range(3))
	# MP4 == Sample, but doesn't throw InvalidDataException
	
class InvalidDataException(ValueError):
	pass
	
class Atom(object):
	def __init__(self, size, object_guid):
		"""size: full size of the atom (including 2 first header fields)
		object_guid: the type of the atom (moov, mdat,...)"""
		self.size = size
		self.type = object_guid
		self.raw_header = b""
		self.start_pos = -1
		
	def __repr__(self, *args, **kwargs):
		return "<Atom type=%r size=%d start_pos=%d>" % (self.type, 
		                                self.size, self.start_pos)
		
class MovReader(object):
	"""Implements a simple Reader class that reads through MP4 
	or MP4-SRS files one atom/box at a time.
	atom: QuickTime File Format
	box: ISO/IEC 14496-12:2008"""
	def __init__(self, read_mode, path=None, stream=None):
		assert path or stream
		if path:
			if is_rar(path):
				self._mov_stream = RarStream(path)
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
		                          self.atom_type == b"mdat")
		
		atom_start_position = self._mov_stream.tell()
		self.current_atom = None
		self.read_done = False
		
		# no room for size (4B) and type (4B) of the atom
		if atom_start_position + 8 > self._file_length:
			return False
		
		self._atom_header = self._mov_stream.read(8)
		# 4 bytes for atom length, 4 bytes for atom type
		(atom_length,) = BE_LONG.unpack_from(self._atom_header)
		self.atom_type = self._atom_header[4:]
		
		# special sizes
		hsize = 8
		if atom_length == 1:
			# 8-byte size field after the atom type
			bsize = self._mov_stream.read(8)
			(atom_length,) = BE_LONGLONG.unpack(bsize)
			self._atom_header += bsize
			hsize += 8
		elif atom_length == 0:
			#print("Box without size found.")
			# FoV/COMPULSiON samples have an atom that consists of just 8
			# null bytes. This is the case if it is followed by an mdat
			# try to make it work with those samples too
			# https://code.google.com/p/mp4parser/ can not open these files!
			if self.atom_type == b"\x00\x00\x00\x00":
				atom_length = 8
			else:
				# the atom extends to the end of the file
				atom_length = self._file_length - atom_start_position

		# sanity check on atom length
		# Skip check on mdat so we can still report expected size.
		# This is only applied on samples,
		# since a partial movie might still be useful.
		end_offset = atom_start_position + atom_length
		if (self.mode == MovReadMode.Sample and self.atom_type != b"mdat" and 
			end_offset > self._file_length):
			raise InvalidDataException("Invalid box length at 0x%08X" % 
			                           atom_start_position)
			
		self.current_atom = Atom(atom_length, self.atom_type)
		self.current_atom.raw_header = self._atom_header
		self.current_atom.start_pos = atom_start_position
		
		self._mov_stream.seek(atom_start_position, os.SEEK_SET)

		# Apple Computer reserves
		# all four-character codes consisting entirely of lowercase letters.

		return True
	
	def read_contents(self):
		# if read_done is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
			self._mov_stream.seek(self.current_atom.start_pos, os.SEEK_SET)

		self.read_done = True
		buff = b""
		
		if (self.mode != MovReadMode.SRS and self.atom_type == b"mdat"):
			raise NotImplementedError("Programming error: implement this "
				"for mdat atoms using the chunk method. These mdat atoms "
				"can become enormous and cause a MemoryError.")

		# do always when it's not a SRS file
		# else skip it when encountering removed data
		if (self.mode != MovReadMode.SRS or self.atom_type != b"mdat"):
			# skip header bytes
			hl = len(self.current_atom.raw_header)
			self._mov_stream.seek(hl, os.SEEK_CUR)
			buff = self._mov_stream.read(self.current_atom.size - hl)
		return buff
	
	def read_contents_chunks(self, chunk_size=65536):
		"""Lazy function (generator) to read a lot of data piece by piece."""
		if self.atom_type != b"mdat" or self.mode == MovReadMode.SRS:
			raise NotImplementedError("Only use this for 'mdat' atoms.")

		self.read_done = True
		# skip header bytes
		hl = len(self.current_atom.raw_header)
		self._mov_stream.seek(self.current_atom.start_pos + hl, os.SEEK_SET)
		end_offset = self.current_atom.start_pos + self.current_atom.size
		
		todo = self.current_atom.size - hl # to prevent ending up in a loop
		while todo != 0 and self._mov_stream.tell() + todo == end_offset:
			amount = end_offset - self._mov_stream.tell()
			if amount > chunk_size:
				amount = chunk_size
			todo -= amount
			yield self._mov_stream.read(amount)
	
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			# do always when it's not a SRS file
			# else skip it when encountering removed data
			if (self.mode != MovReadMode.SRS 
				or self.atom_type != b"mdat"):
				self._mov_stream.seek(self.current_atom.start_pos + 
				                      self.current_atom.size, 
				                      os.SEEK_SET)

	def move_to_child(self):
		self.read_done = True
		# skip the header bytes
		hl = len(self.current_atom.raw_header)
		self._mov_stream.seek(hl, os.SEEK_CUR)
		
	def close(self):
		try: # close the file/stream
			self._mov_stream.close()
		except:
			pass	
		
	def __del__(self):
		try: # close the file/stream
			self._mov_stream.close()
		except:
			pass
			