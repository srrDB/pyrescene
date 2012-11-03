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

# Docs for a quicker understanding:
# http://www.microsoft.com/en-us/download/details.aspx?displaylang=en&id=14995

import os
import struct

from rescene.utility import is_rar
from rescene.rarstream import RarStream

GUID_HEADER_OBJECT = "\x30\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C"
GUID_DATA_OBJECT = "\x36\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C"
GUID_STREAM_OBJECT = "\x91\x07\xDC\xB7\xB7\xA9\xCF\x11\x8E\xE6\x00\xC0\x0C\x20\x53\x65"
GUID_FILE_OBJECT = "\xA1\xDC\xAB\x8C\x47\xA9\xCF\x11\x8E\xE4\x00\xC0\x0C\x20\x53\x65"

# http://www.famkruithof.net/guid-uuid-make.html
GUID_SRS_FILE = "SRSFSRSFSRSFSRSF"
GUID_SRS_TRACK = "SRSTSRSTSRSTSRST"

class AsfReadMode(object):
	WMV, Sample, SRS = list(range(3))
	# WMV == Sample, but doesn't throw InvalidDataException
	
class InvalidDataException(ValueError):
	pass
	
class Object(object):
	def __init__(self, size, object_guid):
		self.size = size
		self.type = object_guid
		self.raw_header = ""
		self.start_pos = -1
		
	def __repr__(self, *args, **kwargs):
		return "<Object type=%s size=%d start_pos=%d>" % (self.type, 
		                                self.size, self.start_pos)
		
class AsfReader(object):
	"""Implements a simple Reader class that reads through WMV 
	or WMV-SRS files one Object at a time."""
	def __init__(self, read_mode, path=None, stream=None):
		assert path or stream
		if path:
			if is_rar(path):
				self._asf_stream = RarStream(path)
			else:
				self._asf_stream = open(path, 'rb')
		elif stream:
			self._asf_stream = stream
		self._asf_stream.seek(0, 2)
		self._file_length = self._asf_stream.tell()
		self._asf_stream.seek(0)
		self.mode = read_mode

		self.read_done = True
		self.current_object = None
		self.object_guid = None

	def read(self):
		# "Read() is invalid at this time", "MoveToChild(), ReadContents(), or 
		# SkipContents() must be called before Read() can be called again")
		assert self.read_done or (self.mode == AsfReadMode.SRS and
		                          self.object_guid == GUID_DATA_OBJECT)
		
		
		object_start_position = self._asf_stream.tell()
		self.current_object = None
		self.read_done = False
		
		# no room for GUID (16B) and size (8B) of the object
		if object_start_position + 24 > self._file_length:
			return False
		
		self._atom_header = self._asf_stream.read(24)
		# 16 bytes for GUID, 8 bytes for object size
		self.object_guid, size = struct.unpack("<16sQ", self._atom_header)

		# sanity check on object length
		# Skip check on GUID_DATA_OBJECT so we can still report expected size.
		# This is only applied on samples,
		# since a partial movie might still be useful.
		end_offset = object_start_position + size
		print(object_start_position)
#		print(size)
#		print(self._file_length)
		if (self.mode == AsfReadMode.Sample and 
		    self.object_guid != GUID_DATA_OBJECT and 
			end_offset > self._file_length):
			raise InvalidDataException("Invalid object length at 0x%08X" % 
			                           object_start_position)
		
		if self.object_guid == GUID_HEADER_OBJECT:
			self._atom_header += self._asf_stream.read(6)
		elif self.object_guid == GUID_DATA_OBJECT:
			self._atom_header += self._asf_stream.read(26)
			
			
		self.current_object = Object(size, self.object_guid)
		self.current_object.raw_header = self._atom_header
		self.current_object.start_pos = object_start_position
		
		self._asf_stream.seek(object_start_position, os.SEEK_SET)

		# New top-level objects should be added only between the  
		# Data Object and Index Object(s).

		return True
	
	def read_contents(self):
		# if read_done is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
			self._asf_stream.seek(self.current_object.start_pos, 
			                      os.SEEK_SET)

		self.read_done = True
		buff = ""

		# do always when it's not a SRS file
		# else skip it when encountering removed data
		if (self.mode != AsfReadMode.SRS or 
			self.object_guid != GUID_DATA_OBJECT):
			# skip header bytes
			hl = len(self.current_object.raw_header)
			self._asf_stream.seek(hl, os.SEEK_CUR)
			buff = self._asf_stream.read(self.current_object.size - hl)
		return buff
	
	def read_data_part(self, offset, length):
		self.read_done = True
		self._asf_stream.seek(offset, os.SEEK_SET)
		return self._asf_stream.read(length)
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			# do always when it's not a SRS file
			# else skip it when encountering removed data
			if (self.mode != AsfReadMode.SRS 
				or self.object_guid != GUID_DATA_OBJECT):
				self._asf_stream.seek(self.current_object.start_pos + 
				                      self.current_object.size, 
				                      os.SEEK_SET)

	def move_to_child(self):
		self.read_done = True
		# skip the header bytes
		hl = len(self.current_object.raw_header)
		self._asf_stream.seek(hl, os.SEEK_CUR)
	
	def __del__(self):
		try: # close the file/stream
			self._asf_stream.close()
		except:
			pass
			