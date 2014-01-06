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
import copy

GUID_HEADER_OBJECT = b"\x30\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C"
GUID_DATA_OBJECT = b"\x36\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C"
GUID_STREAM_OBJECT = b"\x91\x07\xDC\xB7\xB7\xA9\xCF\x11\x8E\xE6\x00\xC0\x0C\x20\x53\x65"
GUID_FILE_OBJECT = b"\xA1\xDC\xAB\x8C\x47\xA9\xCF\x11\x8E\xE4\x00\xC0\x0C\x20\x53\x65"

# http://www.famkruithof.net/guid-uuid-make.html
GUID_SRS_FILE = b"SRSFSRSFSRSFSRSF"
GUID_SRS_TRACK = b"SRSTSRSTSRSTSRST"
GUID_SRS_PADDING = b"PADDINGBYTESDATA"

S_LONGLONG = struct.Struct('<Q') # unsigned long long: 8 bytes
S_LONG = struct.Struct('<L') # unsigned long: 4 bytes
S_SHORT = struct.Struct('<H') # unsigned short: 2 bytes
S_BYTE = struct.Struct('<B') # unsigned char: 1 byte

_DEBUG = bool(os.environ.get("RESCENE_DEBUG")) # leave empty for False

class AsfReadMode(object):
	WMV, Sample, SRS = list(range(3))
	# WMV == Sample, but doesn't throw InvalidDataException
	
class InvalidDataException(ValueError):
	pass
	
class Object(object):
	def __init__(self, size, object_guid):
		self.size = size
		self.type = object_guid
		self.raw_header = b""
		self.start_pos = -1
		
	def __repr__(self, *args, **kwargs):
		return "<Object type=%r size=%d start_pos=%d>" % (self.type, 
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
		
		# Calculate the size for the data object in SRS mode
		if (self.mode == AsfReadMode.SRS and 
		    self.object_guid == GUID_DATA_OBJECT):
			# size of the data object cannot be relied upon
			# so change size and end_offset
			o = self.current_object
			
			size = len(o.raw_header)
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack_from(o.raw_header, i)
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) // total_data_packets
			rp_offsets = 0
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				# calculate real packet size
				packet = AsfDataPacket()
				packet.data_file_offset = start + rp_offsets
				self._asf_stream.seek(packet.data_file_offset)
				# just read all of it to make it easier
				# SRS files are small anyway
				packet.data = self._asf_stream.read()
#				packet.data_size = len(data) # psize
				
				s = asf_data_get_packet(packet, psize, AsfReadMode.SRS)
				rp_offsets += s
			
			self.current_object.osize = self.current_object.size
			self.current_object.size = rp_offsets + size
		
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

		# skip header bytes
		hl = len(self.current_object.raw_header)
		self._asf_stream.seek(hl, os.SEEK_CUR)
		buff = self._asf_stream.read(self.current_object.size - hl)
		return buff
	
	def read_data_part(self, offset, length):
		if (offset + length == self.current_object.start_pos + 
		                       self.current_object.size):
			self.read_done = True
		self._asf_stream.seek(offset, os.SEEK_SET)
		return self._asf_stream.read(length)
		
	def skip_contents(self):
		if not self.read_done:
			self.read_done = True
			self._asf_stream.seek(self.current_object.start_pos + 
			                      self.current_object.size, os.SEEK_SET)

	def move_to_child(self):
		self.read_done = True
		# skip the header bytes
		hl = len(self.current_object.raw_header)
		self._asf_stream.seek(hl, os.SEEK_CUR)

	def close(self):
		try: # close the file/stream
			self._asf_stream.close()
		except:
			pass
			
	def __del__(self):
		try: # close the file/stream
			self._asf_stream.close()
		except:
			pass
			
# -- start LGPLed code \/------------------------------------------------------
# https://github.com/juhovh/libasf
# http://www.google.com/patents?id=kY57AAAAEBAJ
# http://avifile.sourceforge.net/asf-1.0.htm
				
class AsfDataPacket(object):
	def __init__(self):
		self.ec_length = 0
		self.ec_data = None
	
		self.length = 0
		self.padding_length = 0
		self.send_time = 0
		self.duration = 0
	
		self.payload_count = 0 # value read from data
		self.payloads = [] # AsfPayload objects
		self.payloads_size = 0 # == packet.payload_count
	
		self.payload_data_len = 0 # payload headers included
		self.payload_data = None
	
		self.data = None
		self.data_file_offset = 0
		self.data_size = 0 # includes headers
		
		self.header_length = 0 # for reconstruction only
		
	def get_data(self, stream):
		stream.seek(self.data_file_offset, os.SEEK_SET)
		return stream.read(self.data_size)

class AsfPayload(object):
	def __init__(self):
		self.stream_number = 0 # also grabbed from GUID_STREAM_OBJECT object
		self.key_frame = 0 # the segment (payload) contains a keyframe
		self.pts = 0
		
		self.media_object_number = 0 # because it can be split across payloads
		self.media_object_offset = 0 # if split, the offset of this part
		self.replicated_length = 0
		self.replicated_data = None
		
		self.header_size = 0
		self.header_data = None
		
		self.data_length = 0 # does not include header
		self.data = None
		
def getlen2b(bits):
	"""bits, description
	00  The field does not exist. 
	01  The field is coded using a BYTE. 
	10  The field is coded using a WORD. 
	11  The field is coded using a DWORD."""
	return 4 if (bits == 0x03) else bits

def getvalue2b(bits, data):
	length = getlen2b(bits)
	if bits != 0x03:
		if bits != 0x02:
			if bits != 0x01:
				return 0
			else:
				return S_BYTE.unpack(data[:length])[0]
		else:
			return S_SHORT.unpack(data[:length])[0]
	else:
		return S_LONG.unpack(data[:length])[0]

def asf_data_read_packet_fields(packet, flags, data, length,
	                            mode=AsfReadMode.Sample):
	if mode != AsfReadMode.SRS:                         
		assert len(data) == length
	
	datalength = (getlen2b((flags >> 1) & 0x03) +
	              getlen2b((flags >> 3) & 0x03) +
	              getlen2b((flags >> 5) & 0x03) + 6)

	if datalength > length:
		raise ValueError("Invalid length")

	skip = 0
	# Packet size	UINT16	0 or 2 ( present if bit 0x40 is set in flags )
	packet.length = getvalue2b((flags >> 5) & 0x03, data[skip:])
	skip += getlen2b((flags >> 5) & 0x03)
	
	packet.sequence = getvalue2b((flags >> 1) & 0x03, data[skip:])
	skip += getlen2b((flags >> 1) & 0x03)
	
	# Padding size	Variable	0, 1 or 2 ( depends on flags )
	packet.padding_length = getvalue2b((flags >> 3) & 0x03, data[skip:])
	skip += getlen2b((flags >> 3) & 0x03)
	
	# Send time, milliseconds	UINT32	4
	packet.send_time = S_LONG.unpack_from(data, skip)[0] # 4 bytes
	skip += 4
	
	# Duration, milliseconds	UINT16	2
	packet.duration = S_SHORT.unpack_from(data, skip)[0] # 2 bytes
	skip += 2

	if _DEBUG:
		print("Packet length: %d" % packet.length)
		print("Packet sequence: %d" % packet.sequence)
		print("Packet padding length: %d" % packet.padding_length)
		print("Packet send time: %d" % packet.send_time)
		print("Packet duration: %d" % packet.duration)
	
	assert datalength == skip
	return datalength

def asf_data_read_payload_fields(payload, flags, data, size,
	                             mode=AsfReadMode.Sample):
	datalen = (getlen2b(flags & 0x03) +
	           getlen2b((flags >> 2) & 0x03) +
	           getlen2b((flags >> 4) & 0x03))

	if datalen > size and mode != AsfReadMode.SRS:
		raise ValueError("Invalid length")
	
	skip = 0
	payload.media_object_number = getvalue2b((flags >> 4) & 0x03, data[skip:])
	skip += getlen2b((flags >> 4) & 0x03)
	payload.media_object_offset = getvalue2b((flags >> 2) & 0x03, data[skip:])
	skip += getlen2b((flags >> 2) & 0x03)
	payload.replicated_length = getvalue2b(flags & 0x03, data[skip:])
	skip += getlen2b(flags & 0x03)
	
	assert skip == datalen
	return datalen;

def asf_data_get_packet(packet, packet_size, mode=AsfReadMode.Sample):
	read = 0
	
	# Error correction data ---------------------------------------------------
	flags = S_BYTE.unpack_from(packet.data, read)[0]
	assert flags == 0x82
	read += 1
	
	if flags & 0x80:
		packet.ec_length = flags & 0x0F
		opaque_data = (flags >> 4) & 0x01
		ec_length_type = (flags >> 5) & 0x03

		if (ec_length_type != 0x00 or opaque_data != 0 or 
		    packet.ec_length != 0x02):
			raise ValueError("Incorrect error correction flags")
		
		if read + packet.ec_length > packet_size:
			raise ValueError("Invalid length")

		packet.ec_data = packet.data[read:read+packet.ec_length]
		read += packet.ec_length
		if _DEBUG:
			print("Error correction length: %d" % packet.ec_length)
	else:
		packet.ec_length = 0
		packet.ec_data = None
		
	if read + 2 > packet_size:
		raise ValueError("Invalid length")
	
	# Packet parsing information ----------------------------------------------
	# Flags	UINT8	1
	(packet_flags,) = S_BYTE.unpack_from(packet.data, read)
	read += 1
	
	# Segment type ID	UINT8	1
	(packet_property,) = S_BYTE.unpack_from(packet.data, read)
	read += 1
	
	if _DEBUG:
		print("Packet flags: %d" % packet_flags)
		print("Packet property: %d" % packet_property)
	
	tmp = asf_data_read_packet_fields(packet, packet_flags,
	                                  packet.data[read:],
	                                  packet_size - read,
	                                  mode)
	read += tmp
	
	#/* this is really idiotic, packet length can (and often will) be
	# * undefined and we just have to use the header packet size as the size
	# * value */
	if ((packet_flags >> 5) & 0x03) == 0:
		packet.length = packet_size

	#/* this is also really idiotic, if packet length is smaller than packet
	# * size, we need to manually add the additional bytes into padding length
	# * because the padding bytes only count up to packet length value */
	if packet.length < packet_size:
		packet.padding_length += packet_size - packet.length
		packet.length = packet_size
		
	if packet.length != packet_size:
		raise ValueError("packet with invalid length value")
	
	# check if we have multiple payloads
	# Number of segments & segment properties UINT8	0 or 1 ( depends on flags )
	if packet_flags & 0x01:
		# 0x01 More than one segment
		if read + 1 > packet.length:
			raise ValueError("invalid value")

		tmp = S_BYTE.unpack_from(packet.data, read)[0]
		read += 1

		packet.payload_count = tmp & 0x3F
		payload_length_type = (tmp >> 6) & 0x03

		if packet.payload_count == 0:
			raise ValueError("there should always be at least one payload")
			
		if payload_length_type != 0x02:
			raise ValueError("in multiple payloads "
			                 "datalen should always be a word")
	else:
		packet.payload_count = 1
	packet.payload_data_len = packet.length - read
	if _DEBUG:
		print("Payload count: %d" % packet.payload_count)
		print("Payload data length: %d (incl. padding)" % 
		      packet.payload_data_len)
	
	if packet.payload_count > packet.payloads_size:
		packet.payloads_size = packet.payload_count
		
	packet.payload_data = packet.data[read:]
	if mode != AsfReadMode.SRS:
		read += packet.payload_data_len
	else:
		packet.header_length = read
	
	# The return value will be consumed bytes, not including the padding
	tmp = asf_data_read_payloads(packet, packet_flags & 0x01,
	                        packet_property, packet.payload_data,
	                        packet.payload_data_len - packet.padding_length,
	                        mode)
	assert packet.payload_count == len(packet.payloads)
	if mode != AsfReadMode.SRS:
		assert packet.payload_data_len == tmp + packet.padding_length
		assert read == packet_size
	else:
		read += tmp
		
	return read
	
def asf_data_read_payloads(packet, multiple, flags, data, datalen,
	                       mode=AsfReadMode.Sample):
	skip = 0
	i = 0
	while i < packet.payload_count:
		pl = AsfPayload()
		pts_delta = 0
		compressed = 0
		if skip + 1 > datalen and mode != AsfReadMode.SRS:
			raise ValueError("Invalid length")
		
		pl.stream_number = (S_BYTE.unpack_from(data, skip)[0] & 0x7F)
		pl.key_frame = bool(S_BYTE.unpack_from(data, skip)[0] & 0x80)
		skip += 1
		pl.header_size += 1

		tmp = asf_data_read_payload_fields(pl, flags, 
		                                   data[skip:], datalen - skip, mode)
		skip += tmp
		pl.header_size += tmp
		
		if pl.replicated_length > 1:
			if pl.replicated_length < 8 or pl.replicated_length + skip > datalen:
				raise ValueError("Not enough data")
			pl.replicated_data = data[skip:skip+pl.replicated_length]
			skip += pl.replicated_length
			pl.header_size += pl.replicated_length
			
			pl.pts = S_LONG.unpack_from(pl.replicated_data, 4)[0]
		elif pl.replicated_length == 1:
			if skip + 1 > datalen:
				raise ValueError("Not enough data")
			
			# in compressed payload object offset is actually pts
			pl.pts = pl.media_object_offset
			pl.media_object_offset = 0
			
			pl.replicated_length = 0
			pl.replicated_data = None
			
			pts_delta = S_BYTE.unpack_from(data, skip)[0]
			skip += 1
			pl.header_size += 1
			compressed = 1
		else:
			pl.pts = packet.send_time
			pl.replicated_data = None
			
		# substract preroll value from pts since it's counted in */
		#		if (pl.pts > preroll) {
		#			pl.pts -= preroll;
		#		} else {
		#			pl.pts = 0;
		#		}
		
		if multiple:
			# Data length	UINT16	0 or 2
			if skip + 2 > datalen:
				raise ValueError("Not enough data")
			pl.data_length = S_SHORT.unpack_from(data, skip)[0]
			skip += 2
			pl.header_size += 2
		else:
			pl.data_length = datalen - skip
			
		if compressed:
			start = skip
			used, payloads, idx = 0, 0, 0
			
			# count how many compressed payloads this payload includes
			if mode != AsfReadMode.SRS:
				while used < pl.data_length:
					payloads += 1
					used += (1 + S_BYTE.unpack_from(data, start+used))
			else:
				used_srs = 0
				while used < pl.data_length:
					payloads += 1
					size = S_BYTE.unpack_from(data, start+used_srs)[0]
					used += (1 + size)
					used_srs += 1
				
			if used != pl.data_length:
				raise ValueError("invalid compressed data size")
			
			# add additional payloads excluding the already allocated one
			packet.payload_count += (payloads - 1)
			if packet.payload_count > packet.payloads_size:
				packet.payloads_size = packet.payload_count
			
			while idx < payloads:
				pl.data_length = S_BYTE.unpack_from(
					data, skip)[0]
				skip += 1
				
				# Set data correctly
				if idx == 0:
					pl.header_size += 1
				else:
					pl.header_size = 1
				pl.header_data = data[skip-pl.header_size:skip]
				pl.data = data[skip:skip+pl.data_length]
				if mode != AsfReadMode.SRS:
					skip += pl.data_length
				
				# Copy the final payload and update the PTS
				packet.payloads.append(pl)
				pl.pts = pl.pts + idx * pts_delta
				i += 1
				idx += 1

				if _DEBUG:
					print("payload(%d/%d) stream: %d, key frame: %d, object: "
						"%d, offset: %d, pts: %d, datalen: %d" % (i, 
						packet.payload_count, pl.stream_number, 
					    pl.key_frame, pl.media_object_number,
					    pl.media_object_offset, pl.pts + idx * pts_delta, 
					    pl.data_length))
				pl = copy.deepcopy(pl)
		else:
			pl.header_data = data[skip-pl.header_size:skip]
			pl.data = data[skip:skip+pl.data_length]
			packet.payloads.append(pl)
			
			# update the skipped data amount and payload index
			if mode != AsfReadMode.SRS:
				skip += pl.data_length
				assert len(pl.data) == pl.data_length
			i += 1

			if _DEBUG:
				print("payload(%d/%d) stream: %d, key frame: %d, object: %d, "
			      "offset: %d, pts: %d, datalen: %d" % (i, packet.payload_count,
			      pl.stream_number, pl.key_frame, pl.media_object_number,
			      pl.media_object_offset, pl.pts, pl.data_length))
	return skip
		
# -- end LGPLed code /\--------------------------------------------------------