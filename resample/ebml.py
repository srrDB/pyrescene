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

import struct
import os

from rescene.utility import is_rar
from rescene.rarstream import RarStream

S_BYTE = struct.Struct('<B') # 1 byte
S_SHORT = struct.Struct('<H') # 2 bytes

class InvalidDataException(ValueError):
	pass

# EbmlReader.cs ---------------------------------------------------------------
# http://www.matroska.org/technical/specs/index.html

def GetUIntLength(length_descriptor):
	"""Returns the amount of bytes that will be consumed,
	based on the first read byte, the Length Descriptor."""
	assert 0 <= length_descriptor <= 0xFF
	length = 0
	for i in range(8): # big endian
		if (length_descriptor & (0x80 >> i)) != 0: # 128, 64, 32, ..., 1
			length = i + 1
			break
		
	assert 0 <= length <= 8
	return length
	
def GetEbmlElementID(stream):
	first_byte = stream.read(1)
	length = GetUIntLength(S_BYTE.unpack(first_byte)[0])

	return first_byte + stream.read(length - 1) # Element ID bytes

def GetEbmlUInt(buff, offset, count):
	"""buff: header bytes
	offset: offset start integer in buffer
	count: Lenght Descriptor byte"""
	# length descriptor bytes not wanted: remove those from the first byte
	size = S_BYTE.unpack(buff[offset])[0] & (0xFF >> count) # 255, 127, ...
	for i in range(1, count):
		size = (size << 8) + S_BYTE.unpack(buff[offset+i])[0]

	return size # integer size

def GetEbmlUIntStream(stream):
	(first_byte,) = S_BYTE.unpack(stream.read(1))
	bytes_consumed = GetUIntLength(first_byte)

	# length descriptor bytes not wanted: remove those from the first byte
	size = first_byte & (0xFF >> bytes_consumed)
	
	# construct the data size by adding a new byte each time
	for _ in range(1, bytes_consumed):
		size = (size << 8) + S_BYTE.unpack(stream.read(1))[0]

	return size, bytes_consumed

def MakeEbmlUInt(number):
	length_mask = 0

	for i in range(1, 8):
		length_mask = 1L << (i * 8 - i)
		if number < length_mask:
			length_descriptor = i
			number |= length_mask
			break

	data = bytearray(length_descriptor)
	for i in range(length_descriptor):
		data[i] = ((number >> ((length_descriptor - (i + 1)) * 8)) & 0xFF)

	return data

def GetBlockFrameLengths(lace_type, data_length, stream):
	# Matroska uses 'lacing' to store more than one frame of data 
	# in a single block, thereby saving the overhead of a full block per frame
	# this method determines the length of each frame so they can be 
	# re-separated and searched. See the Matroska specs for details...
	# http://www.matroska.org/technical/specs/index.html
	bytes_consumed = 0
	lace_frame_count = 1
	if lace_type != EbmlLaceType.NONE:
		lace_frame_count = S_BYTE.unpack(stream.read(1))[0] + 1
		bytes_consumed += 1

	frame_sizes = [0] * lace_frame_count
	for i in range(lace_frame_count):
		if lace_type == EbmlLaceType.NONE:
			frame_sizes[i] = data_length
		elif lace_type == EbmlLaceType.FIXED:
			frame_sizes[i] = data_length / lace_frame_count
		elif lace_type == EbmlLaceType.XIPH:
			if (i < lace_frame_count - 1):
				nextByte = 0xFF
				while nextByte == 0xFF:
					(nextByte,) = S_BYTE.unpack(stream.read(1))
					bytes_consumed += 1
					frame_sizes[i] += nextByte
			else:
				frame_sizes[i] = data_length - bytes_consumed
				for j in range(i):
					frame_sizes[i] -= frame_sizes[j]
		else: # EbmlLaceType.Ebml
			bc = 0

			if i == 0:
				frame_sizes[i], bc = GetEbmlUIntStream(stream)
			elif i < lace_frame_count - 1:
				# convert UInt to SInt then add to previous
				length, bc = GetEbmlUIntStream(stream)
#				print "i", i
#				print "lace frame count", lace_frame_count
#				print "bytes consumed", bc
				assert bc
				length -= ((1 << (bc * 8 - (bc + 1))) - 1)
				frame_sizes[i] = frame_sizes[i - 1] + length
			else:
				frame_sizes[i] = data_length - bytes_consumed
				for j in range(i):
					frame_sizes[i] -= frame_sizes[j]

			bytes_consumed += bc

	return frame_sizes, bytes_consumed

class EbmlReadMode(object):
	MKV, Sample, SRS = list(range(3))
	# MKV: when reading before writing

class EbmlElementType(object):
	(Ebml, Segment, TimecodeScale, Cluster, Timecode, BlockGroup, Block,
	AttachmentList,	Attachment,	AttachedFileName, AttachedFileData,
	ReSample, ReSampleFile,	ReSampleTrack, Crc32, Unknown) = list(range(16))

EbmlElementTypeName = dict(zip(list(range(16)), ["Ebml", "Segment", 
	"TimecodeScale", "Cluster", "Timecode", "BlockGroup", "Block",
	"AttachmentList", "Attachment", "AttachedFileName", "AttachedFileData",
	"ReSample", "ReSampleFile",	"ReSampleTrack", "Crc32", "Unknown"]))

class EbmlLaceType(object):
	NONE = 0
	XIPH = 2
	FIXED = 4
	EBML = 6
	
class EbmlElement(object):
	"""Elements incorporate an Element ID, 
	a descriptor for the size of the element, 
	and the binary data itself."""
	def __init__(self):
		self.raw_header = ""
		self.element_start_pos = 0
		self.length = 0
	
class BlockElement(EbmlElement):
	def __init__(self):
		self.track_number = 0
		self.timecode = 0
		self.frame_lengths = []
		self.raw_block_header = ""
	
class EbmlID(object):
	"""Element IDs (also called EBML IDs)"""
	EBML = "1A45DFA3"
	SEGMENT = "18538067"
	TIMECODE_SCALE = "2AD7B1"

	CLUSTER = "1F43B675"
	TIMECODE = "E7"
	BLOCK_GROUP = "A0"
	BLOCK = "A1"
	SIMPLE_BLOCK = "A3"

	ATTACHMENT_LIST = "1941A469"
	ATTACHMENT = "61A7"
	ATTACHED_FILE_NAME = "466E"
	ATTACHED_FILE_DATA = "465C"

	RESAMPLE = "1F697576" # Class D - \x1fiuv
	RESAMPLE_FILE = "6A75" # ju
	RESAMPLE_TRACK = "6B75" # ku

	CRC32 = "BF"

class EbmlReader(object):
	"""Implements a simple Reader class that reads through MKV or 
	MKV-SRS files one element at a time."""
	def __init__(self, read_mode, path=None, stream=None):
		assert path or stream
		self.elementHeader = "" # 12 bytes
		
		self._ebml_stream = None
		self.mode = None
		self.read_done = True
	
		self.current_element = None
		self.element_type = None
		
		if path:
			if is_rar(path):
				self._ebml_stream = RarStream(path)
			else:
				self._ebml_stream = open(path, 'rb')
		elif stream:
			self._ebml_stream = stream
		else:
			assert False
		self._ebml_stream.seek(0, 2)
		self._file_length = self._ebml_stream.tell()
		self._ebml_stream.seek(0)
		self.mode = read_mode

	def read(self):
		# "Read() is invalid at this time", "MoveToChild(), ReadContents(), or 
		# SkipContents() must be called before Read() can be called again"
		assert self.read_done or (self.mode == EbmlReadMode.SRS and
		       self.element_type == EbmlElementType.Block)
		
		element_start_position = self._ebml_stream.tell()

		# too little data (+2: 1B element ID + 1B data size)
		if element_start_position + 2 > self._file_length:
			return False
		
		self.current_element = None
		self.read_done = False
		
		# 1) Element ID -------------------------------------------------------
		# length descriptor: the leading bits of the header
		# used to identify the length of the ID (ID: like xml tags)
		read_byte = self._ebml_stream.read(1)
		(id_length_descriptor,) = S_BYTE.unpack(read_byte)
		id_length_descriptor = GetUIntLength(id_length_descriptor)
		self.elementHeader = read_byte
		self.elementHeader += self._ebml_stream.read(id_length_descriptor - 1)
		
		# 2) Data size --------------------------------------------------------
		read_byte = self._ebml_stream.read(1)
		(data_length_descriptor,) = S_BYTE.unpack(read_byte)
		data_length_descriptor = GetUIntLength(data_length_descriptor)
		self.elementHeader += read_byte
		self.elementHeader += self._ebml_stream.read(data_length_descriptor - 1)
		
		assert id_length_descriptor + data_length_descriptor == len(self.elementHeader)
		
		# 3) Data -------------------------------------------------------------
		# these comparisons are ordered by the frequency with which they 
		# will be encountered to avoid unnecessary processing
		eh = self.elementHeader[0:id_length_descriptor].encode('hex').upper()
		if eh == EbmlID.BLOCK or eh == EbmlID.SIMPLE_BLOCK:
			self.element_type = EbmlElementType.Block
		elif eh == EbmlID.BLOCK_GROUP:
			self.element_type = EbmlElementType.BlockGroup
		elif eh == EbmlID.CLUSTER:
			self.element_type = EbmlElementType.Cluster
		elif eh == EbmlID.TIMECODE:
			self.element_type = EbmlElementType.Timecode
		elif eh == EbmlID.SEGMENT:
			self.element_type = EbmlElementType.Segment
		elif eh == EbmlID.TIMECODE_SCALE:
			self.element_type = EbmlElementType.TimecodeScale
		elif eh == EbmlID.CRC32:
			self.element_type = EbmlElementType.Crc32
		elif eh == EbmlID.ATTACHMENT_LIST:
			self.element_type = EbmlElementType.AttachmentList
		elif eh == EbmlID.ATTACHMENT:
			self.element_type = EbmlElementType.Attachment
		elif eh == EbmlID.ATTACHED_FILE_NAME:
			self.element_type = EbmlElementType.AttachedFileName
		elif eh == EbmlID.ATTACHED_FILE_DATA:
			self.element_type = EbmlElementType.AttachedFileData
		elif eh == EbmlID.RESAMPLE:
			self.element_type = EbmlElementType.ReSample
		elif eh == EbmlID.RESAMPLE_FILE:
			self.element_type = EbmlElementType.ReSampleFile
		elif eh == EbmlID.RESAMPLE_TRACK:
			self.element_type = EbmlElementType.ReSampleTrack
		else:
			self.element_type = EbmlElementType.Unknown
			
		element_length = GetEbmlUInt(self.elementHeader, 
		                             id_length_descriptor, 
		                             data_length_descriptor)
		
		# sanity check on element length.  skip check on Segment element so we
		# can still report expected size.  this is only applied on samples 
		# since a partial movie might still be useful
		endOffset = (element_start_position + id_length_descriptor + 
					data_length_descriptor + element_length)
		if (self.mode == EbmlReadMode.Sample and 
			self.element_type != EbmlElementType.Segment and 
			endOffset > self._file_length):
			raise InvalidDataException("Invalid element length at 0x{0:x8}"
			                           .format(element_start_position))
			
		if self.element_type != EbmlElementType.Block:
			self.current_element = EbmlElement()
			self.current_element.raw_header = self.elementHeader
			self.current_element.element_start_pos = element_start_position
			self.current_element.length = element_length
		else: # it's a block
			# first thing in the block is the track number
			trackDescriptor = self._ebml_stream.read(1)
			blockHeader = trackDescriptor
			trackDescriptor = GetUIntLength(S_BYTE.unpack(trackDescriptor)[0])

			# incredibly unlikely the track number is > 1 byte,
			# but just to be safe...
			if trackDescriptor > 1:
				blockHeader += self._ebml_stream.read(trackDescriptor - 1)
			
			trackno = GetEbmlUInt(blockHeader, 0, trackDescriptor)

			# read in time code (2 bytes) and flags (1 byte)
			blockHeader += self._ebml_stream.read(3)
			timecode = ((S_BYTE.unpack(blockHeader[
			                               len(blockHeader) - 3])[0] << 8) + 
			            S_BYTE.unpack(blockHeader[len(blockHeader) - 2])[0])

			# need to grab the flags (last byte of the header) 
			# to check for lacing
			lace_type = (S_BYTE.unpack(blockHeader[len(blockHeader) - 1])[0] & 
					EbmlLaceType.EBML)

			data_length = element_length - len(blockHeader)
			frameSizes, bytesConsumed = GetBlockFrameLengths(lace_type, 
			                              data_length, self._ebml_stream)
			if bytesConsumed > 0:
				newBlockHeader = blockHeader
				self._ebml_stream.seek(-bytesConsumed, os.SEEK_CUR)
				newBlockHeader += self._ebml_stream.read(bytesConsumed)
				blockHeader = newBlockHeader

			element_length -= len(blockHeader)
			
			self.current_element = BlockElement()
			self.current_element.track_number = trackno
			self.current_element.timecode = timecode
			self.current_element.frame_lengths = frameSizes
			self.current_element.raw_block_header = blockHeader
			
			self.current_element.raw_header = self.elementHeader
			self.current_element.element_start_pos = element_start_position
			self.current_element.length = element_length
			
		# the following line will write mkvinfo-like output from the parser 
		# (extremely useful for debugging)
		print("{0}: {3} + {1} bytes @ {2}".format(
		                            EbmlElementTypeName[self.element_type],
		                            element_length, # without header
		                            element_start_position,
		                            len(self.elementHeader)))

		return True
	
	def read_contents(self):
		# if readReady is set, we've already read or skipped it.
		# back up and read again?
		if self.read_done:
			self._ebml_stream.seek(-self.current_element.length, 
			                       os.SEEK_CUR)

		self.read_done = True
		buff = None

		if (self.mode != EbmlReadMode.SRS or 
			self.element_type != EbmlElementType.Block):
			buff = self._ebml_stream.read(self.current_element.length)
		return buff
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			if (self.mode != EbmlReadMode.SRS or 
				self.element_type != EbmlElementType.Block):
				self._ebml_stream.seek(self.current_element.length, 
				                       os.SEEK_CUR)
	
	def move_to_child(self):
		self.read_done = True
	
	def __del__(self):
		try: # close the file/stream
			self._ebml_stream.close()
		except:
			pass
