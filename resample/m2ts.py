#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 pyReScene
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

"""Read MPEG2-Transport Stream packets. Not used for SRS files."""

import os
import struct

from rescene.utility import is_rar, _DEBUG
from rescene.rarstream import RarStream

S_BYTE = struct.Struct('<B')   # 1 byte: C unsigned char -> Python int
S_SHORT = struct.Struct('>H')  # unsigned short: 2 bytes

PACKET_SIZE = 192
HEADER_SIZE = 8  # TP_extra_header + transport stream header
PAYLOAD_SIZE = PACKET_SIZE - HEADER_SIZE

class InvalidDataException(ValueError):
	pass
	
class InvalidMatchOffsetException(ValueError):
	pass

class M2tsReadMode(object):
	M2ts, SRS = list(range(2))

class Packet(object):
	def __init__(self, start_pos):
		self.size = PACKET_SIZE
		self.payload_size = PAYLOAD_SIZE
		self.start_pos = start_pos
		# 01 – no adaptation field, payload only
		# 10 – adaptation field only, no payload
		# 11 – adaptation field followed by payload
		# 00 - RESERVED for future use
		self.adaptation_field = 0
		self.continuity_counter = 0
		# the packet identifier refers to a unique stream
		self.pid = 0
		self.raw_header = b""

	def __repr__(self, *args, **kwargs):
		return ("<Packet start_pos={0} adaptation_field={1} "
		    "continuity_counter={2:X} pid={3}>".format(
		        self.start_pos, self.adaptation_field,
		        self.continuity_counter, self.pid))
		
class M2tsReader(object):
	"""Implements a simple Reader class that reads M2TS files."""
	def __init__(self, read_mode=M2tsReadMode.M2ts, path=None, stream=None,
		         match_offset=0, archived_file_name=""):
		assert path or stream
		if path:
			if is_rar(path):
				self._stream = RarStream(path, archived_file_name)
			else:
				self._stream = open(path, 'rb')
		elif stream:
			self._stream = stream
		self._stream.seek(0, 2)
		self._file_length = self._stream.tell()
		self.mode = read_mode
		self.read_done = True

		self.current_packet = None
		self.current_offset = 0
		
		if self._file_length < 192:
			raise InvalidDataException("File too small")
		
		# faster reconstructing when match_offset is provided
		if match_offset >= 8 and match_offset < self._file_length:
			# use lowest muliple of 192 < offset as a starting point
			start = match_offset // PACKET_SIZE
			self._stream.seek(start)
			self.current_offset = start
		elif match_offset >= self._file_length:
			msg = "Invalid match offset for video: {0}".format(match_offset)
			raise InvalidMatchOffsetException(msg)
		else:
			# no useful matching offset against the main movie file
			self._stream.seek(0)

	def read(self):
		# read() is invalid at this time: read_contents() or 
		# skip_contents() must be called before read() can be called again
		assert self.read_done or self.mode == M2tsReadMode.SRS

		self.read_done = False
		self._stream.seek(self.current_offset)
		# TP_extra_header (4 Bytes) + MPEG-2 transport stream header (4 B)
		header = self._stream.read(HEADER_SIZE)
		
		if not len(header):
			return False

		if M2tsReadMode.M2ts:
			if self.current_offset + PACKET_SIZE > self._file_length:
				msg = "Invalid packet length at 0x{0:08X}"
				raise InvalidDataException(msg.format(self.current_offset))
		else:
			# SRS header data must be a multiple of 8
			if self.current_offset + HEADER_SIZE > self._file_length:
				raise InvalidDataException("Broken SRS file")

		if header[5] == b'\x47':
			msg = "Invalid synchronization byte at 0x{0:08X}"
			raise InvalidDataException(msg.format(self.current_offset))

		packet = Packet(self.current_offset)
		packet.raw_header = header
		(byte8,) = S_BYTE.unpack_from(header, 7)
		# two bits: bit 3 and 4 of last byte in the header
		packet.adaptation_field = (byte8 & 0x30) >> 4
		# last four bits of last byte in the header
		packet.continuity_counter = (byte8 & 0xF)
		(byte67,) = S_SHORT.unpack_from(header, 5)
		packet.pid = byte67 & 0x1FFF

		self.current_offset += PACKET_SIZE
		self.current_packet = packet

# 		if _DEBUG and packet.adaptation_field != 1:
# # 		if _DEBUG:
# 			print(packet)
# 			print(bin(byte67))

		return True

	def read_contents(self):
		"""Reads the transport stream packet payload. (no 8B header)"""
		buff = b""
		if self.read_done:
			self._stream.seek(-PAYLOAD_SIZE, os.SEEK_CUR)
		self.read_done = True
		if self.mode != M2tsReadMode.SRS:
			buff = self._stream.read(PAYLOAD_SIZE)
		return buff
		
	def skip_contents(self):
		"""Skips over the payload data to the next packet."""
		if not self.read_done:
			self.read_done = True
			if self.mode != M2tsReadMode.SRS:
				self._stream.seek(PAYLOAD_SIZE, os.SEEK_CUR)

	def close(self):
		try:  # close the file/stream
			self._stream.close()
		except:
			pass	
		
	def __del__(self):
		try:  # close the file/stream
			self._stream.close()
		except:
			pass	