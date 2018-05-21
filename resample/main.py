#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2012-2016 pyReScene
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

from __future__ import print_function, absolute_import
import struct
import io
import os
import sys
import logging
import unittest
import tempfile
import collections

from os.path import basename
from struct import Struct
from zlib import crc32

import resample

from rescene import rarstream, RarReader
from rescene import utility
from rescene.utility import sep, show_spinner, remove_spinner, fsunicode
from rescene.utility import calculate_crc32 as calc_crc32
from rescene.utility import is_rar
from rescene.utility import _DEBUG
from rescene.utility import FileType

from resample.ebml import EbmlReader, EbmlReadMode, EbmlElementType
from resample.ebml import GetEbmlUInt, MakeEbmlUInt, EbmlID
from resample.riff import RiffReader, RiffReadMode, RiffChunkType
from resample.riff import InvalidMatchOffsetException
from resample.mov import MovReader, MovReadMode
from resample.asf import AsfReader, AsfReadMode
from resample.asf import AsfDataPacket, asf_data_get_packet
from resample.asf import GUID_HEADER_OBJECT, GUID_DATA_OBJECT
from resample.asf import GUID_STREAM_OBJECT, GUID_FILE_OBJECT
from resample.asf import GUID_SRS_FILE, GUID_SRS_TRACK, GUID_SRS_PADDING
from resample.fpcalc import fingerprint
from resample.flac import FlacReader
from resample.mp3 import Mp3Reader
from resample.mp3 import decode_id3_size
from resample.stream import StreamReader
from resample.m2ts import M2tsReader, M2tsReadMode

logger = logging.getLogger(__name__)
if not _DEBUG:
	logger.addHandler(logging.NullHandler())

try:
	odict = collections.OrderedDict  # @UndefinedVariable
except AttributeError:
	# Python 2.6 OrderedDict
	from rescene import ordereddict
	odict = ordereddict.OrderedDict

"""
http://forum.doom9.org/showthread.php?s=&threadid=62723
http://sourceforge.net/projects/pymedia/files/pymedia/
https://code.google.com/p/mutagen/

http://jampal.sourceforge.net/tagbkup.html
"""

S_LONGLONG = Struct('<Q')  # unsigned long long: 8 bytes
S_LONG = Struct('<L')  # unsigned long: 4 bytes
S_SHORT = Struct('<H')  # unsigned short: 2 bytes
S_BYTE = Struct('<B')  # unsigned char: 1 byte

BE_SHORT = Struct('>H')
BE_LONG = Struct('>L')
BE_LONGLONG = Struct('>Q')

SIG_SIZE = 256

MARKER_STREAM_SRS = b"STRM\x08\x00\x00\x00"  # VOB, MPEG, M2TS, ... SRS
MARKER_M2TS_SRS = b"M2TS\x08\x00\x00\x00"  # M2TS SRS (not in use)

class IncompleteSample(Exception):
	pass

class InvalidMatchOffset(ValueError):
	pass

class InvalidPathValue(ValueError):
	pass

# srs.cs ----------------------------------------------------------------------
def file_type_info(ifile):
	"""Decide the type of file based on the magic marker.
	If the file is a sample (based on extension),
	it will not be detected as a RAR file. (this can happen for DVDR vobs)"""
	MARKER_MKV = b"\x1a\x45\xdf\xa3"  # .Eß£
	MARKER_AVI = b"\x52\x49\x46\x46"  # RIFF
	MARKER_RAR = b"\x52\x61\x72\x21\x1A\x07\x00"  # Rar!...
	MARKER_RAR5 = b"\x52\x61\x72\x21\x1A\x07\x01\x00"
	MARKER_MP4 = b"\x66\x74\x79\x70"  # ....ftyp
	MARKER_MP4_3GP = b"\x33\x67\x70\x35"  # 3gp5
	MARKER_WMV = b"\x30\x26\xB2\x75"
	MARKER_FLAC = b"\x66\x4C\x61\x43"  # fLaC
	MARKER_ID3 = b"\x49\x44\x33"  # ID3 (MP3/FLAC file with an ID3v2 container)
	MARKER_MPEG = b"\x47"  # transport stream sync byte


	archived_file_name = ""

	try:
		with open(ifile, 'rb') as ofile:
			marker = ofile.read(14)
	except IOError:
		if os.path.isdir(ifile):
			msg = "The input path does not point to a file"
			raise InvalidPathValue(msg)
		else:
			raise ValueError("Media file locked")

	# the file is too small (probably empty)
	# don't let this function throw an error
	if len(marker) < 14:
		return FileType(FileType.Unknown, archived_file_name)

	if marker.startswith(MARKER_RAR) and utility.is_rar(ifile):
		try:
			# Read first file from the RAR archives
			rr = RarReader(ifile)
			first_file = True
			for archf in rr.list_files():
				# use the first file with a supported file extension
				# (skipping .srt and other encountered files)
				extension = FileType.VideoExtensions + FileType.AudioExtensions
				if archf.endswith(extension):
					archived_file_name = archf  # first useful file
					break
				first_file = False
			rr.close()

			# first file from RAR is the default behavior: no message
			if not first_file and archived_file_name:
				print("Using %s from first RAR." % archived_file_name)
			rs = rarstream.RarStream(ifile, archived_file_name)
			marker = rs.read(8)
			rs.close()
		except Exception as ex:
			print(ex)
			print("File: %s" % os.path.basename(ifile))
			return FileType(FileType.Unknown, archived_file_name)
	elif marker.startswith(MARKER_RAR5):
		print("RAR5 not yet supported.")
		return FileType(FileType.Unknown, archived_file_name)

	if marker.startswith(MARKER_MKV):
		return FileType(FileType.MKV, archived_file_name)
	elif marker.startswith(MARKER_AVI):
		# Some old .mp3 files use the RIFF container too
		# e.g. (dj_tiesto_presents_allure)-we_ran_at_dawn_vinyl_djnl-bmi
		if ifile.endswith(".mp3"):
			return FileType(FileType.MP3, archived_file_name)
		return FileType(FileType.AVI, archived_file_name)
	if marker[4:].startswith(MARKER_MP4) or marker.startswith(MARKER_MP4_3GP):
		# http://wiki.multimedia.cx/index.php?title=QuickTime_container
		# Extensions: mov, qt, mp4, m4v, m4a, m4p, m4b, m4r, k3g, skm, 3gp, 3g2
		return FileType(FileType.MP4, archived_file_name)
	elif marker.startswith(MARKER_WMV):
		return FileType(FileType.WMV, archived_file_name)
	elif marker.startswith(MARKER_FLAC):
		return FileType(FileType.FLAC, archived_file_name)
	elif marker.startswith(MARKER_STREAM_SRS):
		return FileType(FileType.STREAM, archived_file_name)
	elif marker.startswith(MARKER_M2TS_SRS):
		return FileType(FileType.M2TS, archived_file_name)
	elif marker.startswith(MARKER_ID3):
		# can be MP3 or FLAC
		size = decode_id3_size(marker[6:10])
		with open(ifile, 'rb') as ofile:
			ofile.seek(10 + size)
			if ofile.read(4) == b"fLaC":
				return FileType(FileType.FLAC, archived_file_name)
		return FileType(FileType.MP3, archived_file_name)
	elif marker.startswith(b"SRSF"):
		return FileType(FileType.MP3, archived_file_name)
	else:
		(sync,) = BE_SHORT.unpack_from(marker, 0)
		if sync & 0xFFE0 == 0xFFE0:  # regular and valid mp3 music data start
			return FileType(FileType.MP3, archived_file_name)

		# last attempt to detect an MP3 file by using the ID3v1 tag
		# (last 128 bytes of mp3 file)
		with open(ifile, 'rb') as ofile:
			try:
				ofile.seek(-128, os.SEEK_END)
				if ofile.read(3) == b"TAG":
					return FileType(FileType.MP3, archived_file_name)
			except EnvironmentError:
				# IOError possible when RAR file is broken
				pass

		# check for stream types based on extension and sync for M2TS
		name = ifile.lower()
		if name.endswith(FileType.StreamExtensions):
			# M2TS disabled since it's not working nor completed
			# still differences in each track
# 			if marker[4:].startswith(MARKER_MPEG) and name.endswith(".m2ts"):
# 				return FileType(FileType.M2TS, archived_file_name)

# Test sample cut with tsMuxeR. It has more/different data:
# 256: subtitle info; stream does never match (different single bytes and ranges)
# 10 bytes more for each repeating part -> h to r in fourth byte
#
# 4097: some header does not match (7 bytes header it seems, but 4 bytes are different)
# 4113: video; large matches, but 4 byte differences
# 4352: audio; 4 byte differences, regular intervals, but larger than a packet
# 4353: 4 byte parts in the track data are different
# 4354: 4 byte headers are different (data matches)
#
# 0: exact match, earlier blocks are repeated the exact same way
# 31: exact match, but not a lot of data
# 8191: exact match, but not a lot of data

			return FileType(FileType.STREAM, archived_file_name)

		return FileType(FileType.Unknown, archived_file_name)

# SampleAttachmentInfo.cs -----------------------------------------------------
class AttachmentData(object):
	def __init__(self, name, size=0, attachment_file=None):
		self.name = name
		self.size = size
		self.attachment_file = attachment_file

	def __repr__(self, *args, **kwargs):
		return ("<attachment_data name=%r size=%r>" % (self.name, self.size))

# SampleFileInfo.cs -----------------------------------------------------------
class FileData(object):
	"""Stored tool and file data like size and crc32 from SRS file."""
	NO_FLAGS = 0x0
	SIMPLE_BLOCK_FIX = 0x1
	ATTACHMENTS_REMOVED = 0x2
	# BIGFILE = 0x4

	# //default to using new features
	SUPPORTED_FLAG_MASK = SIMPLE_BLOCK_FIX | ATTACHMENTS_REMOVED

	def __init__(self, buff=None, file_name=None):
		# default to using new features
		self.flags = self.SIMPLE_BLOCK_FIX | self.ATTACHMENTS_REMOVED
		self.crc32 = 0

		if file_name:
			self.name = file_name  # can be RAR
			if utility.is_rar(file_name):
				rs = rarstream.RarStream(file_name)
				self.size = rs.seek(0, os.SEEK_END)
				self.sample_name = rs.packed_file_name
				rs.close()
			else:
				self.sample_name = fsunicode(file_name)
				self.size = os.path.getsize(file_name)
		elif buff:
			# flags: unsigned integer 16
			# appname length: uint16
			# name length: uint16
			# crc: uint32
			(self.flags,) = S_SHORT.unpack_from(buff, 0)
			(applength,) = S_SHORT.unpack_from(buff, 2)
			self.appname = buff[4:4 + applength].decode("utf-8")
			(namelength,) = S_SHORT.unpack_from(buff, 4 + applength)
			self.sample_name = buff[4 + applength + 2:4 + applength + 2 + namelength]
			self.sample_name = self.sample_name.decode("utf-8")
			self.name = self.sample_name
			offset = 4 + applength + 2 + namelength
			(self.size,) = S_LONGLONG.unpack_from(buff, offset)
			(self.crc32,) = S_LONG.unpack_from(buff, offset + 8)
		else:
			raise AttributeError("Buffer or file expected.")

	def serialize(self):
		app_name = (resample.APPNAME).encode("utf-8")
		file_name = basename(self.sample_name).encode("utf-8")
		data_length = 18 + len(app_name) + len(file_name)

		buff = io.BytesIO()
		buff.write(S_SHORT.pack(self.flags))  # 2 bytes
		buff.write(S_SHORT.pack(len(app_name)))  # 2 bytes
		buff.write(app_name)
		buff.write(S_SHORT.pack(len(file_name)))  # 2 bytes
		buff.write(file_name)
		buff.write(S_LONGLONG.pack(self.size))  # 8 bytes
		buff.write(S_LONG.pack(self.crc32 & 0xFFFFFFFF))  # 4 bytes

		assert data_length == buff.tell()
		buff.seek(0)

		return buff.read()

	def serialize_as_ebml(self):
		data = self.serialize()
		elementLengthCoded = MakeEbmlUInt(len(data))
		element = EbmlID.RESAMPLE_FILE
		element += elementLengthCoded
		element += data
		return element

	def serialize_as_riff(self):
		data = self.serialize()
		chunk = b"SRSF"
		chunk += S_LONG.pack(len(data))
		chunk += data
		return chunk

	def serialize_as_mov(self):
		data = self.serialize()
		atom = struct.pack(">L", len(data) + 8)
		atom += b"SRSF"
		atom += data
		return atom

	def serialize_as_asf(self):
		data = self.serialize()
		asf_object = GUID_SRS_FILE
		asf_object += S_LONGLONG.pack(len(data) + 16 + 8)
		asf_object += data
		return asf_object

	def serialize_as_flac(self):
		data = self.serialize()
		flack_block = b"s"  # 0x73
		flack_block += struct.pack(">L", len(data))[1:]
		flack_block += data
		return flack_block

	def serialize_as_mp3(self):
		data = self.serialize()
		mp3_block = b"SRSF"
		mp3_block += S_LONG.pack(4 + 4 + len(data))
		mp3_block += data
		return mp3_block

	def serialize_as_stream(self):
		return self.serialize_as_mp3()

	def serialize_as_m2ts(self):
		return self.serialize_as_mp3()

# SampleTrackInfo.cs ----------------------------------------------------------
class TrackData(object):
	"""Flags: big sample or not?
	Track number
	Data length: size of the track
	Match offset: location in the main file where the track is located
	Signature length
	Signature: how we recognize the track location if we have no offset"""
	NO_FLAGS = 0x0
	BIG_FILE = 0x4  # Larger than 2GiB
	BIG_TACK_NUMBER = 0x8  # MP4 container has larger possible numbers

	SUPPORTED_FLAG_MASK = BIG_FILE | BIG_TACK_NUMBER

	def __init__(self, buff=None):
		if buff:
			(self.flags,) = S_SHORT.unpack_from(buff, 0)

			if self.flags & self.BIG_TACK_NUMBER:
				(self.track_number,) = S_LONG.unpack_from(buff, 2)
				e = 2  # extra because of the larger file
			else:
				(self.track_number,) = S_SHORT.unpack_from(buff, 2)
				e = 0

			if self.flags & self.BIG_FILE:
				struct_string = "Q"
				add = 8
			else:
				struct_string = "L"
				add = 4

			(self.data_length, self.match_offset, sig_length) = \
				struct.unpack_from("<%sQH" % struct_string, buff, e + 4)
			self.signature_bytes = buff[(e + 14 + add):(e + 14 + add + sig_length)]
		else:
			self.flags = self.NO_FLAGS
			self.track_number = 0
			self.data_length = 0
			self.match_offset = 0
			self.signature_bytes = b""
		self.match_length = 0
		self.check_bytes = b""
		self.track_file = None

		# not serialized
		self.codec = ""  # always ASCII string for MKV
		# uint indicating which algorithm
		# True when the algorithm isn't specified (compression element exists)
		self.compression_algorithm = None
		self.compression_settings = b""  # e.g. striped header bytes

	def __str__(self, *args, **kwargs):
		return ("<track flags={flags} "
			"number={number} "
			"data_length={length} "
			"match_length={mlength} "
			"match_offset={moffset} "
			"length_signature_bytes={lsb} "
			"length_check_bytes={lcb} "
			">"
			"".format(flags=self.flags, number=self.track_number,
		              length=self.data_length, mlength=self.match_length,
		              moffset=self.match_offset,
		              lsb=len(self.signature_bytes),
		              lcb=len(self.check_bytes)))
		
	def __repr__(self, *args, **kwargs):
		return self.__str__()

	def serialize(self):
		big_file = self.flags & self.BIG_FILE
		data_length = 14 + len(self.signature_bytes) + (8 if big_file else 4)

		buff = io.BytesIO()
		buff.write(S_SHORT.pack(self.flags))

		if self.track_number >= 2 ** 16:
			data_length += 2
			buff.write(S_LONG.pack(self.track_number))
		else:
			buff.write(S_SHORT.pack(self.track_number))

		if big_file:
			buff.write(S_LONGLONG.pack(self.data_length))
		else:
			buff.write(S_LONG.pack(self.data_length))

		buff.write(S_LONGLONG.pack(self.match_offset))
		buff.write(S_SHORT.pack(len(self.signature_bytes)))
		buff.write(self.signature_bytes)

		assert data_length == buff.tell()
		buff.seek(0)

		return buff.read()

	def serialize_as_ebml(self):
		data = self.serialize()
		elementLengthCoded = MakeEbmlUInt(len(data))
		element = EbmlID.RESAMPLE_TRACK
		element += elementLengthCoded
		element += data
		return element

	def serialize_as_riff(self):
		data = self.serialize()
		chunk = b"SRST"
		chunk += S_LONG.pack(len(data))
		chunk += data
		return chunk

	def serialize_as_mov(self):
		data = self.serialize()
		atom = struct.pack(">L", len(data) + 8)
		atom += b"SRST"
		atom += data
		return atom

	def serialize_as_asf(self):
		data = self.serialize()
		asf_object = GUID_SRS_TRACK
		asf_object += S_LONGLONG.pack(len(data) + 16 + 8)
		asf_object += data
		return asf_object

	def serialize_as_flac(self):
		data = self.serialize()
		flac_block = b"t"  # 0x74
		flac_block += struct.pack(">L", len(data))[1:]
		flac_block += data
		try:
			fp_block = b"u"  # 0x75
			fp_block += struct.pack(">L", 4 + 4 + len(self.fingerprint))[1:]
			fp_block += S_LONG.pack(int(self.duration))
			fp_block += S_LONG.pack(len(self.fingerprint))
			fp_block += self.fingerprint
			return flac_block + fp_block
		except:
			print("No finger printing data stored!!!")
			return flac_block

	def serialize_as_mp3(self):
		data = self.serialize()
		mp3_block = b"SRST"
		mp3_block += S_LONG.pack(8 + len(data))
		mp3_block += data
		try:
			fp_block = b"SRSP"
			fp_block += S_LONG.pack(8 + 4 + 4 + len(self.fingerprint))
			fp_block += S_LONG.pack(int(self.duration))
			fp_block += S_LONG.pack(len(self.fingerprint))
			fp_block += self.fingerprint
			return mp3_block + fp_block
		except:
			print("No finger printing data stored!!!")
			return mp3_block

	def serialize_as_stream(self):
		data = self.serialize()
		stream_block = b"SRST"
		stream_block += S_LONG.pack(8 + len(data))
		stream_block += data
		return stream_block

	def serialize_as_m2ts(self):
		return self.serialize_as_stream()

def read_fingerprint_data(track, data):
	(track.duration,) = S_LONG.unpack_from(data)
	(fp_length,) = S_LONG.unpack_from(data, 4)
	track.fingerprint = data[8:8 + fp_length]
	return track

def isascii(bytes_to_test):
	try:
		bytes_to_test.decode('ascii')
		return True
	except UnicodeError:
		return False

def enough_signature_data(track):
	"""x265 srs files can be bad when the encoding options surpass the
	included signature length to find the correct offset"""
	if track.data_length > 1000000:
		return not isascii(track.signature_bytes[-64:])
	else:
		return True  # subtitle tracks

class ReSample(object):
	archived_file_name = ""
	
	def msg_not_enough_signature_data(self, track):
		msg = "Not enough unique data for track {0}".format(track.track_number)
		print("WARNING: " + msg)
		logger.warn(msg)

def sample_class_factory(file_type):
	"""Choose the right class based on the sample's file type."""
	if file_type == FileType.AVI:
		return AviReSample()
	elif file_type == FileType.MKV:
		return MkvReSample()
	elif file_type == FileType.MP4:
		return Mp4ReSample()
	elif file_type == FileType.WMV:
		return WmvReSample()
	elif file_type == FileType.FLAC:
		return FlacReSample()
	elif file_type == FileType.MP3:
		return Mp3ReSample()
	elif file_type == FileType.M2TS:
		return M2tsReSample()
	elif file_type == FileType.STREAM:
		return StreamSample()

# AviReSample.cs --------------------------------------------------------------
class AviReSample(ReSample):
	file_type = FileType.AVI

	def profile_sample(self, *args, **kwargs):
		return avi_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return avi_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return avi_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return avi_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return avi_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return avi_rebuild_sample(self, *args, **kwargs)

# MkvReSample.cs --------------------------------------------------------------
class MkvReSample(ReSample):
	file_type = FileType.MKV

	def profile_sample(self, *args, **kwargs):
		return mkv_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return mkv_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return mkv_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return mkv_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return mkv_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return mkv_rebuild_sample(self, *args, **kwargs)

class Mp4ReSample(ReSample):
	file_type = FileType.MP4

	def profile_sample(self, *args, **kwargs):
		return mp4_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return mp4_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return mp4_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return mp4_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return mp4_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return mp4_rebuild_sample(self, *args, **kwargs)

class WmvReSample(ReSample):
	file_type = FileType.WMV

	def profile_sample(self, *args, **kwargs):
		return wmv_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return wmv_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return wmv_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return wmv_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return wmv_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return wmv_rebuild_sample(self, *args, **kwargs)

class FlacReSample(ReSample):
	file_type = FileType.FLAC

	def profile_sample(self, *args, **kwargs):
		return flac_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return flac_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return flac_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return flac_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return flac_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return flac_rebuild_sample(self, *args, **kwargs)

class Mp3ReSample(ReSample):
	file_type = FileType.MP3

	def profile_sample(self, *args, **kwargs):
		return mp3_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return mp3_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return mp3_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return mp3_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return mp3_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return mp3_rebuild_sample(self, *args, **kwargs)

class StreamSample(ReSample):
	file_type = FileType.STREAM

	def profile_sample(self, *args, **kwargs):
		return stream_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return stream_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return stream_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return stream_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return stream_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return stream_rebuild_sample(self, *args, **kwargs)

class M2tsReSample(ReSample):
	"""Used for m2ts files"""
	file_type = FileType.M2TS

	def profile_sample(self, *args, **kwargs):
		return m2ts_profile_sample(self, *args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return m2ts_create_srs(self, *args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return m2ts_load_srs(self, *args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return m2ts_find_sample_streams(self, *args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return m2ts_extract_sample_streams(self, *args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return m2ts_rebuild_sample(self, *args, **kwargs)

def avi_load_srs(self, infile):
	tracks = {}
	rr = RiffReader(RiffReadMode.SRS, infile)
	done = False
	while not done and rr.read():
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else:
			if rr.current_chunk.fourcc == b"SRSF":
				# resample file
				srs_data = FileData(rr.read_contents())
			elif rr.current_chunk.fourcc == b"SRST":  # resample track
				track = TrackData(rr.read_contents())
				tracks[track.track_number] = track
			elif rr.chunk_type == RiffChunkType.Movi:
				# if we get here in load mode,
				# we have already got what we need, so bail out
				done = True
# 				continue
				break
			else:
				rr.skip_contents()
	rr.close()
	return srs_data, tracks

def mkv_load_srs(self, infile):
	tracks = {}
	er = EbmlReader(EbmlReadMode.SRS, infile)
	header_stripping = False
	current_track_nb = 0
	done = False
	while not done and er.read():
		if er.element_type in (
				EbmlElementType.Segment,
				EbmlElementType.TrackList,
				EbmlElementType.Track,
				EbmlElementType.ContentEncodingList,
				EbmlElementType.ContentEncoding,
				EbmlElementType.Compression,
				EbmlElementType.ReSample,):
			er.move_to_child()
		elif er.element_type == EbmlElementType.TrackNumber:
			elm_content = er.read_contents()
			current_track_nb = GetEbmlUInt(elm_content, 0, len(elm_content))
			done = False
		elif er.element_type == EbmlElementType.TrackCodec:
			elm_content = er.read_contents()
			# subtitle tracks aren't stripped and
			# do not have a ReSampleTrack element for the track
			# e.g. Fury.2014.720p.BluRay.x264-SPARKS
			if current_track_nb in tracks:
				tracks[current_track_nb].codec =  \
					elm_content.decode("ascii", errors="ignore")
		elif er.element_type == EbmlElementType.CompressionAlgorithm:
			elm_content = er.read_contents()
			algorithm = GetEbmlUInt(elm_content, 0, len(elm_content))
			header_stripping = algorithm == 3  # 3: header stripping
		elif er.element_type == EbmlElementType.CompressionSettings:
			elm_content = er.read_contents()
			if header_stripping and current_track_nb in tracks:
				tracks[current_track_nb].compression_settings = elm_content
		elif er.element_type == EbmlElementType.ReSampleFile:
			srs_data = FileData(er.read_contents())
		elif er.element_type == EbmlElementType.ReSampleTrack:
			track = TrackData(er.read_contents())
			tracks[track.track_number] = track
		elif (er.element_type == EbmlElementType.Cluster or
			er.element_type == EbmlElementType.AttachmentList):
				# if we get to either of these elements,
				# we've passed the interesting part of the file, so bail out
				er.skip_contents()
				done = True
		else:
			er.skip_contents()
	er.close()
	
	for track in tracks.values():
		if not enough_signature_data(track):
			self.msg_not_enough_signature_data(track)
		
	return srs_data, tracks

def mp4_load_srs(self, infile):
	tracks = {}
	mr = MovReader(MovReadMode.SRS, infile)
	while mr.read():
		if mr.atom_type == b"SRSF":
			srs_data = FileData(mr.read_contents())
		elif mr.atom_type == b"SRST":
			track = TrackData(mr.read_contents())
			tracks[track.track_number] = track
		elif mr.atom_type == b"mdat":
			mr.move_to_child()
		else:
			mr.skip_contents()
	mr.close()
	return srs_data, tracks

def wmv_load_srs(self, infile):
	tracks = {}
	ar = AsfReader(AsfReadMode.SRS, infile)
	while ar.read():
		o = ar.current_object

		if o.type == GUID_SRS_FILE:
			srs_data = FileData(ar.read_contents())
		elif o.type == GUID_SRS_TRACK:
			track = TrackData(ar.read_contents())
			tracks[track.track_number] = track
		elif o.type == GUID_SRS_PADDING:
			# no 0-bytes used for padding
			srs_data.padding_bytes = ar.read_contents()
		else:
			ar.skip_contents()
	ar.close()
	return srs_data, tracks

def flac_load_srs(self, infile):
	tracks = {}
	fr = FlacReader(infile)
	while fr.read():
		if fr.block_type == ord("s"):
			srs_data = FileData(fr.read_contents())
		elif fr.block_type == ord("t"):
			track = TrackData(fr.read_contents())
			tracks[track.track_number] = track
		elif fr.block_type == ord("u"):
			tracks[1] = read_fingerprint_data(tracks[1], fr.read_contents())
		else:
			fr.skip_contents()
		# mandatory STREAMINFO metadata block (blocks we need are before that)
		# or when Last-metadata-block flag is set
		if fr.block_type == 0 or fr.current_block.is_last_block():
			break
	fr.close()
	return srs_data, tracks

def mp3_load_srs(self, infile):
	tracks = {}
	mr = Mp3Reader(infile)
	for block in mr.read():
		if block.type == "SRSF":
			srs_data = FileData(mr.read_contents()[8:])
		elif block.type == "SRST":
			track = TrackData(mr.read_contents()[8:])
			tracks[track.track_number] = track
		elif block.type == "SRSP":
			tracks[1] = read_fingerprint_data(tracks[1], mr.read_contents()[8:])
	mr.close()
	return srs_data, tracks

def stream_load_srs(self, infile):
	tracks = {}
	sr = StreamReader(infile)
	for block in sr.read():
		if block.type == "SRSF":
			srs_data = FileData(sr.read_contents())
		elif block.type == "SRST":
			track = TrackData(sr.read_contents())
			tracks[track.track_number] = track
	sr.close()
	return srs_data, tracks

def m2ts_load_srs(self, infile):
	# same as stream SRS file, but the header data is followed by a HDRS block
	return stream_load_srs(self, infile)

def avi_profile_sample(self, avi_data):  # FileData object
	tracks = {}
	attachments = {}  # not used for AVI

	other_length = 0
	blockcount = 0

	avi_data.crc32 = 0x0  # start value crc

	rr = RiffReader(RiffReadMode.Sample, avi_data.name)
	while rr.read():
		assert not rr.read_done
		c = rr.current_chunk

		other_length += len(c.raw_header)
		avi_data.crc32 = crc32(c.raw_header, avi_data.crc32)

		if rr.chunk_type == RiffChunkType.List:
			fsize = c.chunk_start_pos + len(c.raw_header) + c.length
			if c.list_type == b"RIFF" and fsize > avi_data.size:
				print("\nWarning: File size does not appear to be correct!",
				      "\t Expected at least: %s" % sep(fsize),
				      "\t Found            : %s\n" % sep(avi_data.size),
				      sep='\n', file=sys.stderr)
			rr.move_to_child()
		else:  # normal chunk
			if rr.chunk_type == RiffChunkType.Movi:
				# chunk containing stream data (our main focus)
				blockcount += 1
				if blockcount % 15 == 0:
					show_spinner(blockcount)

				track_number = c.stream_number
				if track_number not in tracks:
					tracks[track_number] = TrackData()

				track = tracks[track_number]
				track.track_number = track_number
				track.data_length += c.length

				movi_data = rr.read_contents()
				avi_data.crc32 = crc32(movi_data, avi_data.crc32)

				# in profile mode, we want to build track signatures
				b = track.signature_bytes
				if not b or len(b) < SIG_SIZE:
					if b:
						lsig = min(SIG_SIZE, len(b) + c.length)
						sig = b
						sig += movi_data[0:lsig - len(sig)]
						track.signature_bytes = sig
					else:
						lsig = min(SIG_SIZE, c.length)
						track.signature_bytes = movi_data[0:lsig]

			else:
				other_length += c.length
				avi_data.crc32 = crc32(rr.read_contents(), avi_data.crc32)

			if rr.has_padding:
				other_length += 1
				avi_data.crc32 = crc32(S_BYTE.pack(rr.padding_byte),
				                       avi_data.crc32)

	rr.close()
	remove_spinner()
	total_size = other_length

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(avi_data.size),
	                                           avi_data.crc32 & 0xFFFFFFFF))

	print()
	print("Stream Details: Stream  Length")
	print("                ------  -------------")
	for _, track in tracks.items():
		print("                {0:6n}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		total_size += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
	                        sep(other_length),
	                        sep(total_size - other_length), sep(total_size)))

	if avi_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The sample is likely corrupted or incomplete.\n")
		raise IncompleteSample(msg)

	return tracks, attachments

def mkv_profile_sample(self, mkv_data):  # FileData object
	"""
	* EBML Header [header|content]  \__full file size
	* Segment     [header|content]  /
		- 
	"""
	tracks = {}
	attachments = {}

	other_length = 0
	cluster_count = 0
	block_count = 0
	current_attachment_name = ""
	elm_content = None
	current_track_nb = 0
	current_flag = False

	mkv_data.crc32 = 0x0  # start value crc

	er = EbmlReader(EbmlReadMode.Sample, mkv_data.name)
	while er.read():
		assert not er.read_done
		e = er.current_element
		etype = er.element_type

		# 1) doing header
		other_length += len(e.raw_header)
		mkv_data.crc32 = crc32(e.raw_header, mkv_data.crc32)

		# 2) doing body
		if etype == EbmlElementType.Segment:
			# segment should be the first thing following the header.
			# this is a good time to do a check for file size.
			fsize = e.element_start_pos + len(e.raw_header) + e.length
			if (fsize != mkv_data.size):
				print("\nWarning: File size does not appear to be correct!",
				      "\t Expected: %s" % sep(fsize),
				      "\t Found   : %s\n" % sep(mkv_data.size),
				      sep='\n', file=sys.stderr)
			else:
				er.expected_file_size = sep(fsize)
			er.move_to_child()
		elif etype in (EbmlElementType.TimecodeScale, EbmlElementType.Timecode):
			# (same as else)
			other_length += er.current_element.length
			mkv_data.crc32 = crc32(er.read_contents(), mkv_data.crc32)
		elif etype == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while
			# (cluster is good because they're about 1mb each)
			cluster_count += 1
			show_spinner(cluster_count)
			er.move_to_child()
		elif etype in (EbmlElementType.BlockGroup,
		               EbmlElementType.TrackList,
		               EbmlElementType.Track,
		               EbmlElementType.ContentEncodingList,
		               EbmlElementType.ContentEncoding,
		               EbmlElementType.AttachmentList,
		               EbmlElementType.Attachment):
			# these elements have no useful info of their own,
			# but we want to step into them to examine their children
			er.move_to_child()
		elif etype == EbmlElementType.Compression:
			# exact algorithm can be specified later
			tracks[current_track_nb].compression_algorithm = True
			er.move_to_child()
		elif etype == EbmlElementType.Block:
			block_count += 1

			# initialization needed for releases such as
			# The.Leftovers.S03E06.WEB.h264-TBS due to block order
			if not er.current_element.track_number in tracks:
				td = TrackData()
				td.track_number = er.current_element.track_number
				tracks[er.current_element.track_number] = td

			try:
				track = tracks[er.current_element.track_number]
			except KeyError:
				# X-Men.Days.of.Future.Past.2014
				#     .THE.ROGUE.CUT.720p.BluRay.x264-SADPANDA
				# Expected: 54 775 583
				# Found   : 56 131 584
				# KeyError: 171157197 (on the track number)
				# 1 minute duration expected, but only plays for 24 seconds
				# Invalid element length at 0x011D7141 (after error element)
				# Sample raced when not completely written yet?
				raise ValueError("More available data than expected.")
			track.data_length += er.current_element.length

			other_length += len(er.current_element.raw_block_header)
			mkv_data.crc32 = crc32(er.current_element.raw_block_header,
			                       mkv_data.crc32)

			elm_content = er.read_contents()
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)

			# in profile mode, we want to build track signatures
			b = track.signature_bytes
			if not b or len(b) < SIG_SIZE:
				# here, we can completely ignore laces, because we know what
				# we're looking for always starts at the beginning
				if b:
					lsig = min(SIG_SIZE, len(b) + len(elm_content))
					sig = b
					sig += elm_content[0:lsig - len(sig)]
					track.signature_bytes = sig
				else:  # this branch can be eliminated + the test
					lsig = min(SIG_SIZE, len(elm_content))
					track.signature_bytes = elm_content[0:lsig]
		elif etype == EbmlElementType.TrackNumber:
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			current_track_nb = GetEbmlUInt(elm_content, 0, len(elm_content))
			if not current_track_nb in tracks:
				td = TrackData()
				td.track_number = current_track_nb
				tracks[current_track_nb] = td
		elif etype == EbmlElementType.TrackCodec:
			# https://matroska.org/technical/specs/codecid/index.html
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			tracks[current_track_nb].codec = elm_content.decode(
			                                    "ascii", errors="ignore")
		elif etype == EbmlElementType.CompressionAlgorithm:
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			# 0: zlib
			# 1: bzlib
			# 2: lzo1x
			# 3: header stripping
			algorithm = GetEbmlUInt(elm_content, 0, len(elm_content))
			tracks[current_track_nb].compression_algorithm = algorithm
			current_flag = algorithm == 3
		elif etype == EbmlElementType.CompressionSettings:
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			if current_flag:
				tracks[current_track_nb].compression_settings = elm_content
		elif etype == EbmlElementType.AttachedFileName:
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			current_attachment_name = elm_content.decode("utf-8")
		elif etype == EbmlElementType.AttachedFileData:
			elm_content = er.read_contents()
# 			attachments[current_attachment].size = len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			attkey = current_attachment_name
			while attkey in attachments:
				attkey += ".dupe"
			ad = AttachmentData(current_attachment_name, len(elm_content))
			attachments[attkey] = ad
		else:
			other_length += er.current_element.length
			mkv_data.crc32 = crc32(er.read_contents(), mkv_data.crc32)

		assert er.read_done
	er.close()
	remove_spinner()

	total_size = other_length
	attachment_size = 0

# 	import locale
# 	print(locale.getdefaultlocale())
# 	lc = locale.getdefaultlocale()[0]
# 	locale.setlocale(locale.LC_ALL, lc)
	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(mkv_data.size),
	                                           mkv_data.crc32 & 0xFFFFFFFF))
	# http://docs.python.org/library/string.html#formatstrings

	if len(attachments):
		print("Attachments:    File Name                  Size")
		print("                -------------------------  ------------")
		for _key, attachment in attachments.items():
			print("                {0:25}  {1:>12}".format(
			      attachment.name[0:25], sep(attachment.size)))
			total_size += attachment.size
			attachment_size += attachment.size

	print()
	print("Track Details:  Track  Length         Codec")
	print("                -----  -------------  --------------------")
	for _, track in tracks.items():
		print("                {0:5n}  {1:>13}  {2}".format(
			track.track_number, sep(track.data_length), track.codec))
		total_size += track.data_length

	print()
	print("Parse Details:  Metadata     Attachments   Track Data     Total")
	print("                -----------  ------------  -------------  -------------")
	print("                {0:>11}  {1:>12}  {2:>13}  {3:>13}\n".format(
	      sep(other_length), sep(attachment_size),
		  sep(total_size - attachment_size - other_length), sep(total_size)))

	if mkv_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The sample is likely corrupted or incomplete.\n")
		raise IncompleteSample(msg)

	return tracks, attachments

def profile_mp4(mp4_data,  # FileData object
		calculate_crc32=True, archived_file_name=""):
	"""Reads the necessary track header data and constructs track signatures
	
	Having calculate_crc32 set to True isn't necessary when profiling
	a main movie file."""
	tracks = odict()

	meta_length = 0
	mdat_size = 0
	current_track = None
	mp4_data.crc32 = 0x0  # start value CRC
	track_processed = False
	mr = MovReader(MovReadMode.Sample, mp4_data.name,
		archived_file_name=archived_file_name)
	while mr.read():
		a = mr.current_atom
		atype = mr.atom_type
# 		print(repr(atype))

		# 1) profiling atom header
		meta_length += len(a.raw_header)
		mp4_data.crc32 = crc32(a.raw_header, mp4_data.crc32)

		# 2) profiling atom body
		if atype in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
			mr.move_to_child()
		elif atype == b"mdat":
			mdat_size += a.size

			# crc32 calculation isn't used in all cases (optimization)
			if calculate_crc32:
				for data_piece in mr.read_contents_chunks():
					mp4_data.crc32 = crc32(data_piece, mp4_data.crc32)
# 					data_length += len(data_piece)
			else:
				mr.skip_contents()
		else:
			data = mr.read_contents()
			meta_length += len(data)
			mp4_data.crc32 = crc32(data, mp4_data.crc32)

		if atype in (b"tkhd",):
			# grab track id
			(track_id,) = BE_LONG.unpack_from(data, 12)
			assert track_id not in tracks
			tracks[track_id] = TrackData()
			tracks[track_id].track_number = track_id
			current_track = tracks[track_id]

			# initialization
			current_track.chunk_offsets = []
			current_track.chunk_lengths = []
			current_track.sample_lengths = []
			track_processed = False
# 			print(track_id)

		elif atype in (b"stco", b"co64"):
			# exactly one variant must be present
			assert current_track != None
			(entry_count,) = BE_LONG.unpack_from(data, 4)
			if atype == b"stco":
				size = 4
				structunp = BE_LONG
			else:  # b"co64"
				size = 8
				structunp = BE_LONGLONG
			for i in range(entry_count):
				j = 8 + i * size
				(offset,) = structunp.unpack_from(data, j)
				current_track.chunk_offsets.append(offset)
# 			print(current_track.chunk_offsets)

		elif atype == b"stsc":  # Sample To Chunk Box
			(entry_count,) = BE_LONG.unpack_from(data, 4)
			for i in range(entry_count):
				j = 8 + i * 12
				# first_chunk
				# samples_per_chunk
				# sample_description_index
				result_tuple = struct.unpack_from(">LLL", data, j)
				current_track.chunk_lengths.append(result_tuple)

			# enlarge compactly coded tables
			current_track.chunk_lengths = stsc(current_track.chunk_lengths)

# 			print(current_track.chunk_lengths)

		elif atype in (b"stsz", b"stz2"):  # Sample Size Boxes
			(sample_size,) = BE_LONG.unpack_from(data, 4)
			(sample_count,) = BE_LONG.unpack_from(data, 8)
			if sample_size == 0:
				for i in range(sample_count):
					j = 12 + i * 4
					(out,) = BE_LONG.unpack_from(data, j)
					current_track.sample_lengths.append(out)
			else:
				for i in range(sample_count):
					current_track.sample_lengths.append(sample_size)
# 			print(current_track.sample_lengths)

		if (current_track and (not track_processed) and
		    len(current_track.chunk_offsets) and
		    len(current_track.chunk_lengths) and
		    len(current_track.sample_lengths)):
			track_processed = True

			# in profile mode, we want to build track signatures
			# TODO: skip in other modes
			current_track.signature_bytes = mp4_signature_bytes(current_track,
			                                                    mp4_data.name)
			# the size of the track
			current_track.data_length = sum(current_track.sample_lengths)
	mr.close()

	mp4_data.other_length = meta_length
	mp4_data.mdat_size = mdat_size  # better size guess for broken files
# 	assert meta_length == mp4_data.size - data_length
	return tracks

def stsc(samples_chunk):
	"""Decompact compactly coded table."""
	old = samples_chunk
	new = []
	index = 1
	prev_samples_per_chunk = None
	prev_sample_description_index = None
	for (first_chunk, samples_per_chunk, sample_description_index) in old:
		if first_chunk > index:
			# fill between chunks
			for i in range(index, first_chunk):
				new.append((i, prev_samples_per_chunk,
						prev_sample_description_index))
				index += 1
		new.append((first_chunk, samples_per_chunk,
					sample_description_index))
		prev_samples_per_chunk = samples_per_chunk
		prev_sample_description_index = sample_description_index
		index += 1
	return new

def mp4_profile_sample(self, mp4_data):
	tracks = profile_mp4(mp4_data, calculate_crc32=True,
		archived_file_name=self.archived_file_name)
	# everything except stream data that will be removed
	total_size = mp4_data.other_length
	for _, track in tracks.items():
		total_size += track.data_length

	# Expected at least: 48 (broken file)
	if total_size < mp4_data.size and total_size < 100:
		# 100: small number safety check that might not be needed
		total_size += mp4_data.mdat_size

	if mp4_data.size != total_size:
		print("\nWarning: File size does not appear to be correct!",
		      "\t Expected at least: %s" % sep(total_size),
		      "\t Found            : %s\n" % sep(mp4_data.size),
		      sep='\n', file=sys.stderr)

	# no spinner to remove

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(mp4_data.size),
	                                           mp4_data.crc32 & 0xFFFFFFFF))
	# http://docs.python.org/library/string.html#formatstrings

	print("Track Details:  Track  Length")
	print("                -----  -------------")
	stream_length = 0
	for _, track in tracks.items():
		print("                {0:5d}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		stream_length += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
						sep(mp4_data.other_length),
						sep(stream_length),
						sep(total_size)))

	if mp4_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The sample is likely corrupted or incomplete.\n")
		raise IncompleteSample(msg)

	return tracks, {}  # attachments

def mp4_signature_bytes(track, mp4_file):
	"""Returns the signature bytes for a track. The signature bytes are
	the 256 first bytes in the track."""
	previous_samples = 0
	signature_bytes = b""
	# iterate different offsets in the file where data of current track
	# can be found
	for chnb, chunk_offset in enumerate(track.chunk_offsets):
		# each offset is a chunk
		# a chunk exists of a number of samples
		try:
			samples_in_chunk = track.chunk_lengths[chnb][1]
		except IndexError:
			# House.of.Cards.2013.S01E01.REPACK.HDTV.x264-ASAP
			# last element will contain right amount of samples
			samples_in_chunk = track.chunk_lengths[-1][1]
		# the sizes of the different samples of the chunk
		chunk_size = sum(track.sample_lengths[previous_samples:
		                 previous_samples + samples_in_chunk])

		chunk_content = b""
		with open(mp4_file, "rb") as mov:
			mov.seek(chunk_offset)
			chunk_content = mov.read(chunk_size)

		lsig = min(SIG_SIZE, len(signature_bytes) + chunk_size)
		signature_bytes += chunk_content[:lsig - len(signature_bytes)]

		previous_samples += samples_in_chunk
		if len(signature_bytes) == SIG_SIZE:
			return signature_bytes
	return signature_bytes

def profile_wmv(wmv_data):  # FileData object
	"""Reads the necessary track header data 
	and constructs track signatures"""
	tracks = odict()

	meta_length = 0
	wmv_data.crc32 = 0x0  # start value CRC
	ar = AsfReader(AsfReadMode.Sample, wmv_data.name)
	while ar.read():
		o = ar.current_object
		oguid = ar.object_guid

		# 1) doing header
		meta_length += len(o.raw_header)
		wmv_data.crc32 = crc32(o.raw_header, wmv_data.crc32)

		# 2) doing body
		if oguid in (GUID_HEADER_OBJECT):
			ar.move_to_child()
		elif oguid == GUID_DATA_OBJECT:
			padding_amount = 0
			padding_bytes = b""
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack_from(o.raw_header, i)
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) // total_data_packets
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				data = ar.read_data_part(start + i * psize, psize)
				wmv_data.crc32 = crc32(data, wmv_data.crc32)

				if i % 15 == 0:
					show_spinner(i)

				packet = AsfDataPacket()
				packet.data = data
				packet.data_file_offset = start + i * psize
				packet.data_size = len(data)  # psize

				asf_data_get_packet(packet, psize)

				header_data = data[:-packet.payload_data_len]
				payloads_sizes = 0
				headers_sizes = 0
				for payload in packet.payloads:
					header_data += payload.header_data

					if not payload.stream_number in tracks:
						# assert False # GUID_STREAM_OBJECT is bad
						td = TrackData()
						td.track_number = payload.stream_number
						tracks[payload.stream_number] = td

					track = tracks[payload.stream_number]
					track.data_length += payload.data_length
					assert payload.data_length == len(payload.data)
					assert payload.header_size == len(payload.header_data)


					payloads_sizes += payload.data_length
					headers_sizes += payload.header_size

					# create signature bytes
					b = track.signature_bytes
					if not b or len(b) < SIG_SIZE:
						lsig = min(SIG_SIZE, len(b) + payload.data_length)
						sig = b
						sig += payload.data[0:lsig - len(sig)]
						track.signature_bytes = sig

				assert (packet.payload_data_len - packet.padding_length ==
				        payloads_sizes + headers_sizes)
				meta_length += packet.data_size - payloads_sizes
				assert (packet.data_size - payloads_sizes ==
				        len(header_data) + packet.padding_length)
				assert (packet.payload_data_len - payloads_sizes ==
				        packet.padding_length + headers_sizes)

				if packet.padding_length:
					padding_amount += packet.padding_length
					padding_bytes += data[-packet.padding_length:]
					assert (len(data[-packet.padding_length:])
					        == packet.padding_length)

			# for wmv files without 0 as padding bytes (large SRS files)
			wmv_data.padding_bytes = padding_bytes
			wmv_data.padding_amount = padding_amount
		else:
			data = ar.read_contents()
			meta_length += len(data)
			wmv_data.crc32 = crc32(data, wmv_data.crc32)

		if oguid == GUID_STREAM_OBJECT:
			# grab track id
			i = 16 + 16 + 8 + 4 + 4
			(flags,) = S_SHORT.unpack_from(data, i)
			track_id = flags & 0xF
			assert track_id not in tracks
			tracks[track_id] = TrackData()
			tracks[track_id].track_number = track_id

		if oguid == GUID_FILE_OBJECT:
			# exact size is stored in one of the header objects
			i = 16
			(file_size,) = S_LONGLONG.unpack_from(data, i)
			if file_size != wmv_data.size:
				print("\nWarning: File size does not appear to be correct!",
				      "\t Expected: %s" % sep(file_size),
				      "\t Found   : %s\n" % sep(wmv_data.size),
				      sep='\n', file=sys.stderr)
	ar.close()

	wmv_data.other_length = meta_length
	remove_spinner()
	return tracks

def wmv_profile_sample(self, wmv_data):
	tracks = profile_wmv(wmv_data)

	# everything except stream data that will be removed
	total_size = wmv_data.other_length
	for _, track in tracks.items():
		total_size += track.data_length

	if wmv_data.size != total_size:
		print("\nWarning: File size does not appear to be correct!",
		      "\t Expected at least: %s" % sep(total_size),
		      "\t Found            : %s\n" % sep(wmv_data.size),
		      sep='\n', file=sys.stderr)

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(wmv_data.size),
	                                           wmv_data.crc32 & 0xFFFFFFFF))
	# http://docs.python.org/library/string.html#formatstrings

	print("Track Details:  Track  Length")
	print("                -----  -------------")
	stream_length = 0
	for _, track in tracks.items():
		print("                {0:5d}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		stream_length += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
						sep(wmv_data.other_length),
						sep(stream_length),
						sep(total_size)))

	if wmv_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The sample is likely corrupted or incomplete.\n")
		raise IncompleteSample(msg)

	return tracks, {}  # attachments

def flac_profile_sample(self, flac_data):  # FileData object
	tracks = {}
	flac_data.crc32 = 0x0  # start value crc
	meta_length = 0

	fr = FlacReader(flac_data.name)
	while fr.read():
		assert not fr.read_done
		e = fr.current_block

		meta_length += len(e.raw_header)
		flac_data.crc32 = crc32(e.raw_header, flac_data.crc32)

		if fr.block_type == "fLaC":
			fr.skip_contents()
		else:
			read = 0
			to_read = 65536
			while read < e.size:
				if read + to_read > e.size:
					to_read = e.size - read
				data = fr.read_part(to_read, read)
				flac_data.crc32 = crc32(data, flac_data.crc32)
				read += to_read
			if e.is_frame_data():
				# do track stuff
				track = TrackData()
				track.track_number = 1
				track.data_length = e.size

				# in profile mode, we want to build track signatures
				if SIG_SIZE < e.size:
					track.signature_bytes = fr.read_part(SIG_SIZE)
				else:
					track.signature_bytes = fr.read_part(e.size)

				tracks[1] = track
			else:
				meta_length += e.size
			fr.skip_contents()

		assert fr.read_done
	fr.close()

	total_size = meta_length

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(flac_data.size),
	                                           flac_data.crc32 & 0xFFFFFFFF))

	print()
	print("Stream Details: Stream  Length")
	print("                ------  -------------")
	for _, track in tracks.items():
		print("                {0:6n}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		total_size += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
	                        sep(meta_length),
	                        sep(total_size - meta_length), sep(total_size)))

	# this error will never be shown
	if flac_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The file is likely corrupted or incomplete.")
		raise IncompleteSample(msg)

	# create a finger print of the file
	duration, fp = fingerprint(flac_data.name, utility.temporary_directory)

	try:
		tracks[1].duration = duration
		tracks[1].fingerprint = fp
	except KeyError:
		pass
	return tracks, {}

def mp3_profile_sample(self, mp3_data):  # FileData object
	tracks = {}
	mp3_data.crc32 = 0x0  # start value crc
	meta_length = 0

	mr = Mp3Reader(mp3_data.name)
	for block in mr.read():
		if block.type in ("MP3", "fLaC"):  # main MP3 data
			read = 0
			to_read = 65536
			while read < block.size:
				if read + to_read > block.size:
					to_read = block.size - read
				data = mr.read_part(to_read, read)
				mp3_data.crc32 = crc32(data, mp3_data.crc32)
				read += to_read

			# do track stuff
			track = TrackData()
			track.track_number = 1
			track.data_length = block.size

			# in profile mode, we want to build track signatures
			if SIG_SIZE < block.size:
				track.signature_bytes = mr.read_part(SIG_SIZE)
			else:
				track.signature_bytes = mr.read_part(block.size)

			tracks[1] = track
		else:
			meta_length += block.size
			mp3_data.crc32 = crc32(mr.read_contents(), mp3_data.crc32)
	mr.close()

	total_size = meta_length

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(mp3_data.size),
	                                           mp3_data.crc32 & 0xFFFFFFFF))

	print()
	print("Stream Details: Stream  Length")
	print("                ------  -------------")
	for _, track in tracks.items():
		print("                {0:6n}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		total_size += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
	                        sep(meta_length),
	                        sep(total_size - meta_length), sep(total_size)))

	# this error will never be shown
	if mp3_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The file is likely corrupted or incomplete.")
		raise IncompleteSample(msg)

	# create a finger print of the file
	duration, fp = fingerprint(mp3_data.name, utility.temporary_directory)

	try:
		tracks[1].duration = duration
		tracks[1].fingerprint = fp
	except KeyError:
		pass
	return tracks, {}

def stream_profile_sample(self, stream_data):  # FileData object
	"""Profiles a stream container: look at it as one big blob"""
	tracks = {}
	stream_data.crc32 = 0x0  # start value crc
	meta_length = 0

	stream_data.crc32 = calc_crc32(stream_data.name)

	# do track stuff
	track = TrackData()
	track.track_number = 1
	track.data_length = os.path.getsize(stream_data.name)

	# in profile mode, we want to build track signatures
	with open(stream_data.name, "rb") as sample:
		track.signature_bytes = sample.read(SIG_SIZE)

	tracks[1] = track

	total_size = meta_length

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(stream_data.size),
	                                           stream_data.crc32 & 0xFFFFFFFF))

	print()
	print("Stream Details: Stream  Length")
	print("                ------  -------------")
	for _, track in tracks.items():
		print("                {0:6n}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		total_size += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
	                        sep(meta_length),
	                        sep(total_size - meta_length), sep(total_size)))

	return tracks, {}

def m2ts_profile_sample(self, m2ts_data):  # FileData object
	"""Profiles an M2TS container"""
	tracks = {}
	m2ts_data.crc32 = 0x0  # start value crc
	meta_length = 0

	if _DEBUG:
		allcrc32 = calc_crc32(m2ts_data.name)

	def new_track_found(track_number):
		t = TrackData()
		t.track_number = track_number
		return t

	# 32 packets in an aligned unit (6144B) of BDAV MPEG-2 transport stream
	mr = M2tsReader(path=m2ts_data.name)
	while mr.read():
		packet = mr.current_packet
		track = tracks.setdefault(packet.pid, new_track_found(packet.pid))

		# 1) doing header
		meta_length += len(packet.raw_header)
		m2ts_data.crc32 = crc32(packet.raw_header, m2ts_data.crc32)

		# 2) doing body
		data = mr.read_contents()
		track.data_length += len(data)
		m2ts_data.crc32 = crc32(data, m2ts_data.crc32)

		# in profile mode, we want to build track signatures
		b = track.signature_bytes
		if not b or len(b) < SIG_SIZE:
			if b:
				lsig = min(SIG_SIZE, len(b) + packet.size)
				sig = b
				sig += data[0:lsig - len(b)]
				track.signature_bytes = sig
			else:
				lsig = min(SIG_SIZE, packet.size)
				track.signature_bytes = data[0:lsig]

	mr.close()

	total_size = meta_length

	print("File Details:   Size           CRC")
	print("                -------------  --------")
	print("                {0:>13}  {1:08X}\n".format(sep(m2ts_data.size),
	                                           m2ts_data.crc32 & 0xFFFFFFFF))

	print()
	print("Stream Details: Stream  Length")
	print("                ------  -------------")
	for _, track in tracks.items():
		print("                {0:6n}  {1:>13}".format(track.track_number,
		                                               sep(track.data_length)))
		total_size += track.data_length

	print()
	print("Parse Details:   Metadata     Stream Data    Total")
	print("                 -----------  -------------  -------------")
	print("                 {0:>11}  {1:>13}  {2:>13}\n".format(
	                        sep(meta_length),
	                        sep(total_size - meta_length), sep(total_size)))

	if _DEBUG:
		assert allcrc32 == m2ts_data.crc32

		# write out all tracks to separate files
		mr = M2tsReader(path=m2ts_data.name)
		track_data = {}
		for track in tracks.keys():
			track_data[track] = io.BytesIO()

		count = 0
		while mr.read():
			count += 1
			if count % 1000 == 0:
				print(count)
			data = mr.read_contents()
			track_data[mr.current_packet.pid].write(data)

		for key, tdata in track_data.items():
			tdata.seek(0)
			track_name = "".join([m2ts_data.name, ".", str(key)])
			with open(track_name, "xb") as trck:
				trck.write(tdata.read())

	return tracks, {}

def avi_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		rr = RiffReader(RiffReadMode.AVI, sample)
		while rr.read():
			c = rr.current_chunk

			srsf.write(c.raw_header)

			if rr.chunk_type == RiffChunkType.List:
				# in store mode, create and write our custom chunks
				# as the first child of LIST movi
				# we put them after the avi headers
				# so mediainfo can still read them from the SRS
				if c.list_type == b"LIST" and c.fourcc == b"movi":
					file_chunk = sample_data.serialize_as_riff()
					assert file_chunk
					srsf.write(file_chunk)
					if len(file_chunk) % 2 == 1:
						srsf.write(b"\0")

					for track in tracks.values():
						if big_file:
							track.flags |= TrackData.BIG_FILE
						track_chunk = track.serialize_as_riff()
						srsf.write(track_chunk)
						if len(track_chunk) % 2 == 1:
							srsf.write(b"\0")

				rr.move_to_child()
			else:
				if rr.chunk_type == RiffChunkType.Movi:
					# don't copy stream data
					rr.skip_contents()
				else:
					# do copy everything else
					srsf.write(rr.read_contents())

				if rr.has_padding:
					srsf.write(S_BYTE.pack(rr.padding_byte))
		rr.close()

def mkv_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		er = EbmlReader(EbmlReadMode.MKV, sample)
		while er.read():
			e = er.current_element

			srsf.write(e.raw_header)

			if er.element_type == EbmlElementType.Segment:
				# in store mode, create and write our custom ebml element
				# as the first child of the segment
				file_element = sample_data.serialize_as_ebml()
				element_size = len(file_element)

				track_elements = []
				for track in tracks.values():
					if big_file:
						track.flags |= TrackData.BIG_FILE
					track_ebml = track.serialize_as_ebml()
					track_elements.append(track_ebml)
					element_size += len(track_ebml)

				srsf.write(EbmlID.RESAMPLE)
				srsf.write(MakeEbmlUInt(element_size))
				srsf.write(file_element)
				for track in track_elements:
					srsf.write(track)

				er.move_to_child()
			elif er.element_type in [EbmlElementType.Cluster,
						EbmlElementType.BlockGroup,
						EbmlElementType.AttachmentList,
						EbmlElementType.Attachment]:
				# these elements have no useful info of their own,
				# but we want to step into them to examine their children
				er.move_to_child()
			elif er.element_type == EbmlElementType.AttachedFileData:
				# eliminate the data from any attachments
				er.skip_contents()
			elif er.element_type == EbmlElementType.Block:
				# copy block header, but eliminate any frame data
				srsf.write(e.raw_block_header)
				er.skip_contents()
			else:
				# anything not caught above is considered metadata,
				# so we copy it as is
				# EbmlElementType.Timecode
				# EbmlElementType.TimecodeScale
				# EbmlElementType.AttachedFileName
				srsf.write(er.read_contents())
		er.close()

def mp4_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as movf:
		mr = MovReader(MovReadMode.MP4, sample)
		while mr.read():
			atom = mr.current_atom

			if atom.type == b"mdat":
				# in store mode, create and write our custom atoms
				# as atom child in the root
				file_atom = sample_data.serialize_as_mov()
				movf.write(file_atom)

				for track in tracks.values():
					if big_file:
						track.flags |= TrackData.BIG_FILE
					track_atom = track.serialize_as_mov()
					movf.write(track_atom)

			movf.write(atom.raw_header)

			if atom.type == b"mdat":
				# don't copy stream data
				mr.skip_contents()
			else:
				# do copy everything else
				movf.write(mr.read_contents())
		mr.close()

def wmv_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		ar = AsfReader(AsfReadMode.WMV, sample)
		while ar.read():
			o = ar.current_object

			srsf.write(o.raw_header)

			if o.type == GUID_DATA_OBJECT:
				i = 16 + 8 + 16
				(total_data_packets,) = S_LONGLONG.unpack_from(o.raw_header, i)
				# data packet/media object size
				psize = (o.size - len(o.raw_header)) // total_data_packets
				start = o.start_pos + len(o.raw_header)
				for i in range(total_data_packets):
					data = ar.read_data_part(start + i * psize, psize)

					packet = AsfDataPacket()
					packet.data = data
					packet.data_file_offset = start + i * psize
					packet.data_size = len(data)  # psize

					asf_data_get_packet(packet, psize)

					header_data = data[:-packet.payload_data_len]
					srsf.write(header_data)

					for payload in packet.payloads:
						header_data = payload.header_data
						srsf.write(header_data)

				# in store mode, create and write our custom objects
				# as object child in the root
				file_atom = sample_data.serialize_as_asf()
				srsf.write(file_atom)

				for track in tracks.values():
					if big_file:
						track.flags |= TrackData.BIG_FILE
					track_object = track.serialize_as_asf()
					srsf.write(track_object)

				# padding object
				if (sample_data.padding_bytes !=
				bytearray(sample_data.padding_amount)):
					size = 16 + 8 + len(sample_data.padding_bytes)
					print("Larger (%dB) SRS file because of irregular"
					      " padding bytes." % size)
					asf_object = GUID_SRS_PADDING
					asf_object += S_LONGLONG.pack(size)
					asf_object += sample_data.padding_bytes
					srsf.write(asf_object)

			else:
				# do copy everything else
				srsf.write(ar.read_contents())
		ar.close()

def flac_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as flacf:
		fr = FlacReader(sample)
		while fr.read():
			block = fr.current_block

			flacf.write(block.raw_header)

			if fr.block_type == "fLaC":
				# in store mode, create and write our custom blocks
				file_block = sample_data.serialize_as_flac()
				flacf.write(file_block)

				for track in tracks.values():
					if big_file:
						track.flags |= TrackData.BIG_FILE
					track_block = track.serialize_as_flac()
					flacf.write(track_block)

			if block.is_frame_data():
				# don't copy stream data
				fr.skip_contents()
			else:
				# do copy everything else
				flacf.write(fr.read_contents())
		fr.close()

def mp3_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as mp3f:
		mr = Mp3Reader(sample)
		for block in mr.read():
			if block.type in ("MP3", "fLaC"):
				# in store mode, create and write our custom blocks
				file_block = sample_data.serialize_as_mp3()
				mp3f.write(file_block)

				for track in tracks.values():
					if big_file:
						track.flags |= TrackData.BIG_FILE
					track_block = track.serialize_as_mp3()
					mp3f.write(track_block)
			else:  # "ID3", "TAG",...
				# do copy everything else
				mp3f.write(mr.read_contents())
		mr.close()

def stream_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as streamf:
		# in store mode, create and write our custom blocks
		streamf.write(MARKER_STREAM_SRS)
		file_block = sample_data.serialize_as_stream()
		streamf.write(file_block)

		for track in tracks.values():
			if big_file:
				track.flags |= TrackData.BIG_FILE
			track_block = track.serialize_as_stream()
			streamf.write(track_block)

def m2ts_create_srs(self, tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as streamf:
		# in store mode, create and write our custom blocks
		streamf.write(MARKER_M2TS_SRS)
		file_block = sample_data.serialize_as_m2ts()
		streamf.write(file_block)

		for track in tracks.values():
			if big_file:
				track.flags |= TrackData.BIG_FILE
			track_block = track.serialize_as_m2ts()
			streamf.write(track_block)

		# indicate that headers are following
		streamf.write(b"HDRS")
		headers_size = streamf.tell()
		streamf.write(b"0000")

		# store all 8 bytes of header data
		mr = M2tsReader(path=sample)
		while mr.read():
			streamf.write(mr.current_packet.raw_header)
			mr.skip_contents()
		headers_end = streamf.tell()

		# fix up the size field
		streamf.seek(headers_size, os.SEEK_SET)
		streamf.write(S_LONG.pack(headers_end - headers_size + 4))

def avi_find_sample_streams(self, tracks, main_avi_file):
	rr = RiffReader(RiffReadMode.AVI, main_avi_file,
		archived_file_name=self.archived_file_name)
	block_count = 0
	done = False

	while rr.read() and not done:
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else:  # normal chunk
			tracks, block_count, done = _avi_normal_chunk_find(tracks, rr,
			                                      block_count, done)
	remove_spinner()

	rr.close()
	return tracks

def _avi_normal_chunk_find(tracks, rr, block_count, done):
	# contains the stream data
	if rr.chunk_type == RiffChunkType.Movi:
		block_count += 1
		if block_count % 15 == 0:
			show_spinner(block_count)

		# grab track or create new track
		track_number = rr.current_chunk.stream_number
		if track_number not in tracks:
			tracks[track_number] = TrackData()
		track = tracks[track_number]
		track.track_number = track_number

		if (track.match_offset == 0 or
			len(track.check_bytes) < len(track.signature_bytes)):
			# It's possible the sample didn't require or contain data
			# for all tracks in the main file. If that happens,
			# we obviously don't want to try to match the data
			if track.signature_bytes:
				if (0 < len(track.check_bytes) < len(track.signature_bytes)):
					lcb = min(len(track.signature_bytes),
								rr.current_chunk.length +
								len(track.check_bytes))
					check_bytes = track.check_bytes
					check_bytes += rr.read_contents()[:lcb -
					                                  len(track.check_bytes)]

					# track found!
					if track.signature_bytes.startswith(check_bytes):
						track.check_bytes = check_bytes
					else:
						# It was only a partial match. Start over.
						track.check_bytes = b""
						track.match_offset = 0
						track.match_length = 0

				# this is a bit weird, but if we had a false positive match
				# going and discovered it above, we check this frame again
				# to see if it's the start of a new match
				# (probably will never happen with AVI,
				# but it does in MKV, so just in case...)
				if not track.check_bytes:
					chunk_bytes = rr.read_contents()

					search_byte = track.signature_bytes[0]
					found_pos = chunk_bytes.find(search_byte, 0)

					while found_pos > -1:
						lcb = min(len(track.signature_bytes),
									len(chunk_bytes) - found_pos)
						check_bytes = chunk_bytes[found_pos:found_pos + lcb]

						# track found!
						if track.signature_bytes.startswith(check_bytes):
							track.check_bytes = check_bytes
							track.match_offset = (
							                rr.current_chunk.chunk_start_pos
							                + len(rr.current_chunk.raw_header)
							                + found_pos)
							track.match_length = min(track.data_length,
							                     len(chunk_bytes) - found_pos)
							break
						found_pos = chunk_bytes.find(search_byte, found_pos + 1)
			else:
				track.match_length = min(track.data_length
				                         - track.match_length,
				                         rr.current_chunk.length)


		elif track.match_length < track.data_length:
			track.match_length += min(track.data_length - track.match_length,
			                          rr.current_chunk.length)

			track_done = True
			for track in tracks.values():
				if track.match_length < track.data_length:
					track_done = False
					break
			done = track_done
		rr.skip_contents()
	else:
		rr.skip_contents()

	return tracks, block_count, done

def mkv_find_sample_streams(self, tracks, main_mkv_file):
	er = EbmlReader(EbmlReadMode.MKV, main_mkv_file,
		archived_file_name=self.archived_file_name)
	cluster_count = 0
	done = False
	current_track_nb = 0
	header_stripping = False
	tracks_main = {}  # contains TrackData objects; main mkv info

	while er.read() and not done:
		if er.element_type in (
				EbmlElementType.Segment,
				EbmlElementType.BlockGroup,
				EbmlElementType.TrackList,
				EbmlElementType.Track,
				EbmlElementType.ContentEncodingList,
				EbmlElementType.ContentEncoding,
				EbmlElementType.Compression):
			er.move_to_child()
		elif er.element_type == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while
			# (cluster is good because they're about 1mb each)
			cluster_count += 1
			show_spinner(cluster_count)
			er.move_to_child()
		elif er.element_type == EbmlElementType.Block:
			# tracks and tracks_main get modified
			done = _mkv_block_find(tracks, er, done, tracks_main)
		elif er.element_type == EbmlElementType.TrackNumber:
			elm_content = er.read_contents()
			current_track_nb = GetEbmlUInt(elm_content, 0, len(elm_content))
			if not current_track_nb in tracks_main:
				td = TrackData()
				td.track_number = current_track_nb
				tracks_main[current_track_nb] = td
			done = False
		elif er.element_type == EbmlElementType.TrackCodec:
			# not necessary, but might be useful for debugging output
			elm_content = er.read_contents()
			tracks_main[current_track_nb].codec = elm_content.decode(
			                                        "ascii", errors="ignore")
		elif er.element_type == EbmlElementType.CompressionAlgorithm:
			elm_content = er.read_contents()
			algorithm = GetEbmlUInt(elm_content, 0, len(elm_content))
			header_stripping = algorithm == 3
		elif er.element_type == EbmlElementType.CompressionSettings:
			elm_content = er.read_contents()
			if header_stripping:
				tracks_main[current_track_nb].compression_settings = elm_content
		else:
			er.skip_contents()

	remove_spinner()

	er.close()
	return tracks

def _mkv_block_find(tracks, er, done, tracks_main):
	# grab track or create new track
	track_number = er.current_element.track_number
	if track_number not in tracks:
		tracks[track_number] = TrackData()
		tracks[track_number].track_number = track_number
	if track_number not in tracks_main:
		tracks_main[track_number] = TrackData()
		tracks_main[track_number].track_number = track_number
	track = tracks[track_number]
	track2 = tracks_main[track_number]
	sforsample = b""  # settings for the sample tracks
	sformain = b""  # settings for main tracks

	# keep track of the compression settings differences
	if ((track.compression_settings or track2.compression_settings) and
		(track.compression_settings != track2.compression_settings)):
		if track.compression_settings:
			sformain = track.compression_settings
		if track2.compression_settings:
			sforsample = track2.compression_settings

	# it's possible the sample didn't require
	# or contain data for all tracks in the main file
	# if that happens, we obviously don't want to try to match the data
	if track.signature_bytes and (track.match_offset == 0 or
		(len(track.check_bytes) < len(track.signature_bytes))):
		# here, the data we're looking for might not start in the first frame
		# (lace) of the block, so we need to check them all
		buff = er.read_contents()
		offset = 0
		for i in range(len(er.current_element.frame_lengths)):
			flength = (er.current_element.frame_lengths[i] +
			           len(sforsample) - len(sformain))
			# see if a false positive match was detected
			if (0 < len(track.check_bytes) < len(track.signature_bytes)):
				lcb = min(len(track.signature_bytes),
				          flength + len(track.check_bytes))
				check_bytes = track.check_bytes  # from sample
				check_bytes += sforsample  # stored settings from main video
				check_bytes += buff[offset + len(sformain):
									offset + len(sformain) + lcb -
									len(track.check_bytes) - len(sforsample)]

				if track.signature_bytes.startswith(check_bytes):
					track.check_bytes = check_bytes
				else:
					# It was only a partial match. Start over.
					track.check_bytes = b""
					track.match_offset = 0
					track.match_length = 0
			# this is a bit weird, but if we had a false positive match going
			# and discovered it above, we check this frame again
			# to see if it's the start of a new match
			# (rare problem, but it can happen with subtitles especially)

			if not track.check_bytes:
				lcb = min(len(track.signature_bytes), flength)
				check_bytes = sforsample
				check_bytes += buff[offset + len(sformain):
				                    offset + len(sformain) + lcb - len(sforsample)]
				if track.signature_bytes.startswith(check_bytes):
					track.check_bytes = check_bytes
					track.match_offset = (er.current_element.element_start_pos
					                      + len(er.current_element.raw_header)
					                      + len(er.current_element.raw_block_header)
					                      + offset)
					track.match_length = min(track.data_length, flength)
			else:
				track.match_length += min(track.data_length -
				                          track.match_length, flength)
			offset += er.current_element.frame_lengths[i]
	elif track.match_length < track.data_length:
		track.match_length += min(track.data_length - track.match_length,
		                          er.current_element.length)
		er.skip_contents()

		tracks_done = True
		for track in tracks.values():
			if track.match_length < track.data_length:
				tracks_done = False
				break

		done = tracks_done
	else:
		er.skip_contents()

	return done

def mp4_find_sample_stream(track, mtrack, main_mp4_file):
	"""Check if the track from the sample exist in the main file. This is
	done based on the track signature alone, not the whole data stream."""
	mtrack = mp4_add_track_stream(mtrack)
	# open stream here so we open and close the mp4 file just once
	mtrack.trackstream.stream = open_main(main_mp4_file)

	data = mtrack.trackstream.read(len(track.signature_bytes))
# 	from binascii import hexlify
# 	print(hexlify(data).decode('ascii'))
# 	print(mtrack.trackstream.current_offset())
# 	print(hexlify(track.signature_bytes).decode('ascii'))
	if data == track.signature_bytes:
		track.match_offset = mtrack.trackstream.current_offset()
	next_chunk = True

	# walk through the stream one sample at the time
	while data != track.signature_bytes and next_chunk:
		next_chunk = next(mtrack.trackstream)
		data = mtrack.trackstream.read(len(track.signature_bytes))
		if data == track.signature_bytes:
			# this indicates that we have the track found
			track.match_offset = mtrack.trackstream.current_offset()

	mtrack.trackstream.stream.close()
	return track

def mp4_add_track_stream(track):
	ts = TrackStream()

	samples_amount = 0
	prev_chunk = None
	for chnb, chunk_offset in enumerate(track.chunk_offsets):
		try:
			samples_in_chunk = track.chunk_lengths[chnb][1]
		except IndexError:
			# House.of.Cards.2013.S01E01.REPACK.HDTV.x264-ASAP
			# ASAP again, why aren't we surprised?
			samples_in_chunk = track.chunk_lengths[-1][1]
		chunk = TrackChunk(chunk_offset, samples_in_chunk, prev_chunk)
		# bidirectional links
		if prev_chunk:
			prev_chunk.next_chunk = chunk

		chunk.samples = track.sample_lengths[samples_amount:
		                                     samples_amount + samples_in_chunk]
		samples_amount += samples_in_chunk
		chunk.samples_in_chunk = len(chunk.samples)
		assert chunk.samples_in_chunk == len(chunk.samples)

		ts.add_chunk(chunk)
		prev_chunk = chunk

	track.trackstream = ts
	return track

class TrackStream(object):
	"""MP4 stream existing of chunks."""
	def __init__(self):
		self.chunks = []
		self.stream = None
		self._current_offset = 0  # chunk + sample offset
		self._current_chunk = None
		self._current_sample = 0  # of the current chunk

	def add_chunk(self, chunk):
		self.chunks.append(chunk)

	def current_offset(self):
		return self._current_offset

	def seek(self, offset):
		"""The offset must be the beginning of a sample."""
		self._current_offset = offset
		for chunk in self.chunks:
			if chunk.chunk_offset <= offset:
				self._current_chunk = chunk
		assert self._current_chunk
		# Will raise InvalidMatchOffset when not on start of a sample
		self._current_sample = self._current_chunk.get_sample_nb(offset)

	def read(self, amount):
		"""amount: max amount to read"""
		if self._current_chunk == None:  # bootstrap
			self._current_chunk = self.chunks[0]
			self._current_offset = self._current_chunk.chunk_offset

		# what we can read from the current chunk
		lb = self._current_chunk.bytes_left_in_chunk(self._current_sample)
		if lb > amount:
			# if we can read all from the same chunk
			self.stream.seek(self._current_offset, os.SEEK_SET)
			data = self.stream.read(amount)
			return data
		else:
			# we need to grab extra data from the next chunk(s)
			self.stream.seek(self._current_offset, os.SEEK_SET)
			firstb = self.stream.read(lb)

			next_chunk = self._current_chunk
			while len(firstb) < amount:
				next_chunk = next_chunk.next_chunk
				if not next_chunk:
					# at the end of the stream, so return what we have
					return firstb

				bl = next_chunk.bytes_left_in_chunk(0)
				self.stream.seek(next_chunk.chunk_offset)
				bytes_read = self.stream.read(min(amount - len(firstb), bl))
				firstb += bytes_read
			return firstb

	def __next__(self):
		# are there still samples left in the chunk?
		if self._current_sample + 1 < self._current_chunk.samples_in_chunk:
			self._current_sample += 1
			# this is the global offset
			self._current_offset = (self._current_chunk.chunk_offset +
			    self._current_chunk.bytes_consumed(self._current_sample))
		else:
			self._current_chunk = self._current_chunk.next_chunk
			self._current_sample = 0
			if self._current_chunk:
				self._current_offset = self._current_chunk.chunk_offset
			else:
				return False
		return True
	next = __next__  # Python < 3 compatibility

class TrackChunk(object):
	"""MP4 data block that consists of samples."""
	def __init__(self, chunk_offset, samples_in_chunk, prev_chunk):
		# absolute location in the main movie file
		self.chunk_offset = chunk_offset
		# chunk consists of samples
		self.samples_in_chunk = samples_in_chunk
		# point to previous chunk
		self.prev_chunk = prev_chunk
		self.next_chunk = None
		self.samples = []

	def bytes_left_in_chunk(self, sample_number):
		return sum(self.samples[sample_number:self.samples_in_chunk])

	def bytes_consumed(self, sample_number):
		amount = 0
		for i in range(sample_number):
			amount += self.samples[i]
		return amount

	def get_sample_nb(self, offset):
		sample_sum = 0
		count = 0
		for sample in self.samples:
			if offset <= self.chunk_offset + sample_sum:
				if offset != self.chunk_offset + sample_sum:
					raise InvalidMatchOffset
				assert self.chunk_offset + sample_sum == offset
				return count
			count += 1
			sample_sum += sample
		return count

def mp4_find_sample_streams(self, tracks, main_mp4_file):
	mtracks = profile_mp4(FileData(file_name=main_mp4_file),
	                      calculate_crc32=False,
	                      archived_file_name=self.archived_file_name)

	# check for each movie track if it contains the sample data
	for mtrack in mtracks.values():
		try:
			track = tracks[mtrack.track_number]
			track = mp4_find_sample_stream(track, mtrack, main_mp4_file)
# 			print(track)
# 			print(mtrack)
			track.main_track = mtrack
			tracks[mtrack.track_number] = track
		except KeyError:
			# track in main file that is not in the sample file
			# do not search for match
			continue
	return tracks

def wmv_find_sample_streams(self, tracks, main_wmv_file):
	ar = AsfReader(AsfReadMode.WMV, main_wmv_file,
		archived_file_name=self.archived_file_name)
	done = False
	while ar.read() and not done:
		o = ar.current_object

		if o.type == GUID_DATA_OBJECT:
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack_from(
				o.raw_header, i)
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) // total_data_packets
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				if i % 15 == 0:
					show_spinner(i)
				data = ar.read_data_part(start + i * psize, psize)

				packet = AsfDataPacket()
				packet.data = data
				packet.data_file_offset = start + i * psize
				packet.data_size = len(data)  # psize

				asf_data_get_packet(packet, psize, AsfReadMode.WMV)

				prev_payloads_size = 0
				for payload in packet.payloads:
					# grab track or create new track
					track_number = payload.stream_number
					if track_number not in tracks:
						tracks[track_number] = TrackData()
					track = tracks[track_number]
					track.track_number = track_number

					if (track.match_offset == 0 or
						len(track.check_bytes) < len(track.signature_bytes)):
						# It's possible the sample didn't require or contain data
						# for all tracks in the main file. If that happens,
						# we obviously don't want to try to match the data
						if track.signature_bytes:
							if (0 <
							    len(track.check_bytes)
							    < len(track.signature_bytes)):
								lcb = min(len(track.signature_bytes),
											payload.data_length +
											len(track.check_bytes))
								check_bytes = track.check_bytes
								check_bytes += payload.data[:lcb -
								                        len(track.check_bytes)]

								# track found!
								if track.signature_bytes.startswith(
								    check_bytes):
									track.check_bytes = check_bytes
								else:
									# It was only a partial match. Start over.
									track.check_bytes = b""
									track.match_offset = 0
									track.match_length = 0

						# this is a bit weird, but if we had a false positive match
						# going and discovered it above, we check this payload again
						# to see if it's the start of a new match
						# (probably will never happen with AVI
						# but it does in MKV, so just in case...)
						if not track.check_bytes:
							payload_bytes = payload.data

							search_byte = track.signature_bytes[0]
							found_pos = payload_bytes.find(search_byte, 0)

							while found_pos > -1:
								lcb = min(len(track.signature_bytes),
											len(payload_bytes) - found_pos)
								check_bytes = payload_bytes[found_pos:
								                          found_pos + lcb]

								# track found!
								if track.signature_bytes.startswith(
								    check_bytes):
									track.check_bytes = check_bytes
									track.match_offset = (
									    packet.data_file_offset +
									    prev_payloads_size +
									    payload.header_size +
									    found_pos)
									track.match_length = min(
									    track.data_length,
									    len(payload_bytes) - found_pos)
									break
								found_pos = payload_bytes.find(search_byte,
								                             found_pos + 1)
						else:
							track.match_length = min(track.data_length
							                         - track.match_length,
							                         payload.data_length)


					elif track.match_length < track.data_length:
						track.match_length += min(track.data_length -
						                          track.match_length,
						                          payload.data_length)

						track_done = True
						for track in tracks.values():
							if track.match_length < track.data_length:
								track_done = False
								break
						done = track_done

					prev_payloads_size += (payload.data_length +
					                       payload.header_size)
				if done:
					break
			ar.skip_contents()
			done = True
		else:
			ar.skip_contents()
	ar.close()

	remove_spinner()

	return tracks

def flac_find_sample_streams(self, tracks, main_flac_file):
	fr = FlacReader(main_flac_file, archived_file_name=self.archived_file_name)
	while fr.read():
		assert not fr.read_done
		if fr.current_block.is_frame_data():
			track = tracks[1]
			sig_size = len(track.signature_bytes)
			read_size = sig_size
			if fr.current_block.size < sig_size:
				read_size = fr.current_block.size

			# no more data in memory than necessary
			data = fr.read_part(read_size)
			if track.signature_bytes == data:
				# this is the right FLAC file
				track.check_bytes = track.signature_bytes
				track.match_offset = fr.current_block.start_pos
				track.match_length = min(track.data_length,
					                     fr.current_block.size)
				tracks[1] = track
				break
			# no support for FLAC samples
			# it must be the same complete FLAC file
		fr.skip_contents()
		assert fr.read_done
	fr.close()

	return tracks

def mp3_find_sample_streams(self, tracks, main_mp3_file):
	mr = Mp3Reader(main_mp3_file, archived_file_name=self.archived_file_name)
	for block in mr.read():
		if block.type in ("MP3", "fLaC"):
			track = tracks[1]
			sig_size = len(track.signature_bytes)
			read_size = sig_size
			if block.size < sig_size:
				read_size = block.size

			data = mr.read_part(read_size)
			if track.signature_bytes == data:
				# this is the right MP3 file
				track.match_offset = block.start_pos
				track.match_length = min(track.data_length, block.size)
			elif len(data[:2]) == 2:
				# this isn't the right MP3 file?
				track.match_offset = -1
				# only try to search for the signature when the MP3 data block
				# doesn't start with the MP3 maker
				# (otherwise too slow for just wrong tracks?)
				(sync,) = BE_SHORT.unpack(data[:2])
				if sync & 0xFFE0 != 0xFFE0:
					track = mp3_match_signature(track, block, mr)
				# only works for prepended crap; not MP3 sample files
			else:
				# very weird border case
				track.match_offset = -1
			tracks[1] = track
			break
	mr.close()

	return tracks

def mp3_match_signature(track, block, mr):
	boffset = 0
	batchsize = 0x10000

	while boffset <= block.size:
		size = min(block.size - boffset, batchsize)
		data = mr.read_part(size, boffset)
		found_offset = data.find(track.signature_bytes)
		if found_offset > -1:
			track.match_offset = boffset + found_offset
			track.match_length = min(track.data_length, block.size)
			break
		boffset += (batchsize - SIG_SIZE + 1)
	return track

def stream_find_sample_streams(self, tracks, main_file):
	if is_rar(main_file):
		stream = rarstream.RarStream(main_file, self.archived_file_name)
	else:
		stream = open(main_file, 'rb')
	try:
		track = tracks[1]
		sig_size = len(track.signature_bytes)
		ramount = 0x10000  # read each time 64KiB

		# search for a match
		x = stream.read(ramount)
		p = b""  # previous read
		count = 0
		while x:
			show_spinner(count)
			if p:
				match = (p + x).find(track.signature_bytes, ramount - sig_size)
			else:
				match = x.find(track.signature_bytes)

			if match > -1:
				track.check_bytes = track.signature_bytes
				track.match_offset = stream.tell() - len(x) - len(p) + match
				track.match_length = sig_size
				tracks[1] = track
				break

			p = x
			x = stream.read(ramount)
			count += 1
		else:
			# no match found at all
			track.match_offset = -1
			tracks[1] = track

		remove_spinner()
	finally:
		stream.close()

	return tracks

def m2ts_find_sample_streams(self, tracks, main_m2ts_file):
	mr = M2tsReader(path=main_m2ts_file, read_mode=M2tsReadMode.M2ts,
	                archived_file_name=self.archived_file_name)
	source_packet_count = 0
	done = False

	while mr.read() and not done:
		assert not mr.read_done
		# spinner after each aligned unit
		source_packet_count += 1
		pskip = 64
		if source_packet_count % pskip == 0:
			show_spinner(source_packet_count // pskip)

		packet = mr.current_packet
		track_number = packet.pid
		try:
			track = tracks[track_number]
		except KeyError:
			tracks[track_number] = TrackData()
			tracks[track_number].track_number = track_number

		# it's possible the sample didn't require
		# or contain data for all tracks in the main file
		# if that happens, we obviously don't want to try to match the data
		# - a track we need to match -and-
		#   - no location with match found yet -or-
		#   - whole length of the signature not matched yet
		if track.signature_bytes and (track.match_offset == 0 or
			(len(track.check_bytes) < len(track.signature_bytes))):
			# assume that the data always starts at the start of a packet
			buff = mr.read_contents()

			# see if a false positive match was detected
			if 0 < len(track.check_bytes) < len(track.signature_bytes):
				check_bytes = (
					track.check_bytes + buff)[:len(track.signature_bytes)]

				if track.signature_bytes.startswith(check_bytes):
					track.check_bytes = check_bytes
				else:
					# It was only a partial match: start over.
					track.check_bytes = b""
					track.match_offset = 0
					track.match_length = 0
					if _DEBUG:
						print("Partial match detected")
				# this is a bit weird, but if we had a false positive match going
				# and discovered it above, we check this packet again
				# to see if it's the start of a new match
				# (behavior copied from mkv. also for m2ts?)

			if not track.check_bytes:
				if track.signature_bytes.startswith(buff):
					track.check_bytes = buff
					track.match_offset = packet.start_pos + 8
					track.match_length = min(
						track.data_length, packet.payload_size)
			else:
				track.match_length += min(packet.payload_size,
					track.data_length - track.match_length)
		elif track.match_length < track.data_length:
			track.match_length += min(track.data_length - track.match_length,
						  packet.payload_size)
			if track.match_length >= track.data_length:
				tracks_done = True
				for track in tracks.values():
					if track.match_length < track.data_length:
						tracks_done = False
						break
				done = tracks_done
			mr.skip_contents()
		else:
			mr.skip_contents()
		assert mr.read_done
	remove_spinner()

	return tracks

def m2ts_extract_sample_streams(self, tracks, main_file):
	start_offset = 2 ** 63  # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)

	try:
		mr = M2tsReader(read_mode=M2tsReadMode.M2ts, path=main_file,
		                match_offset=start_offset,
		                archived_file_name=self.archived_file_name)
	except InvalidMatchOffsetException as ex:
		raise InvalidMatchOffset(format(ex))

	source_packet_count = 0
	done = False

	while mr.read() and not done:
		# spinner after each aligned unit
		source_packet_count += 1
		if source_packet_count % 32 == 0:
			show_spinner(source_packet_count // 32)

		packet = mr.current_packet
		track_number = packet.pid
		if track_number not in tracks:
			tracks[track_number] = TrackData()
			tracks[track_number].track_number = track_number
		track = tracks[track_number]

		# test if located on a chunk with the required data
		if (packet.start_pos + 192 > track.match_offset):
			if track.track_file == None:
				track.track_file = tempfile.TemporaryFile()

			previously_read = track.track_file.tell()
			if previously_read < track.data_length:
				# read in data to temporary file track (whole packets)
				track.track_file.write(packet.read_contents())

			if previously_read + 192 >= track.data_length:
				# check for tracks completion
				tracks_done = True
				for track_data in tracks.values():
					if (track_data.track_file == None or
					track_data.track_file.tell() < track_data.data_length):
						tracks_done = False
						break
				done = tracks_done
		else:
			mr.skip_contents()

	remove_spinner()

	mr.close()
	return tracks, {}  # attachments

def avi_extract_sample_streams(self, tracks, movie):
	# search for first match offset (possibly skipping some parsing)
	start_offset = 2 ** 63  # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)

	try:
		rr = RiffReader(RiffReadMode.AVI, movie,
		                match_offset=start_offset,
		                archived_file_name=self.archived_file_name)
	except InvalidMatchOffsetException as ex:
		raise InvalidMatchOffset(format(ex))

	block_count = 0
	done = False

	while rr.read() and not done:
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else:  # normal chunk
			tracks, block_count, done = _avi_normal_chunk_extract(
			                                tracks, rr, block_count, done)
	remove_spinner()

	rr.close()
	return tracks, {}  # attachments

def _avi_normal_chunk_extract(tracks, rr, block_count, done):
	if rr.chunk_type == RiffChunkType.Movi:
		block_count += 1
		show_spinner(block_count)

		# grab track or create new track
		track_number = rr.current_chunk.stream_number
		if track_number not in tracks:
			tracks[track_number] = TrackData()
			tracks[track_number].track_number = track_number
		track = tracks[track_number]

		# test if located on a chunk with the required data
		if (rr.current_chunk.chunk_start_pos +
		len(rr.current_chunk.raw_header) +
		rr.current_chunk.length > track.match_offset):
			if track.track_file == None:
				track.track_file = tempfile.TemporaryFile()

			if track.track_file.tell() < track.data_length:
				# read in data to temporary file track
				if (rr.current_chunk.chunk_start_pos +
				len(rr.current_chunk.raw_header) >= track.match_offset):
					# read contents starting from the beginning of the chunk
					track.track_file.write(
					    rr.read_contents()[:rr.current_chunk.length])
				else:
					# read contents starting from offset in the chunk
					chunk_offset = (track.match_offset -
					                (rr.current_chunk.chunk_start_pos +
					                len(rr.current_chunk.raw_header)))
					track.track_file.write(rr.read_contents()[chunk_offset:
					                       rr.current_chunk.length])

			# check for tracks completion
			tracks_done = True
			for track_data in tracks.values():
				if (track_data.track_file == None or
				track_data.track_file.tell() < track_data.data_length):
					tracks_done = False
					break
			done = tracks_done
		rr.skip_contents()
	else:
		rr.skip_contents()

	return tracks, block_count, done

def mkv_extract_sample_streams(self, tracks, movie):
	er = EbmlReader(EbmlReadMode.MKV, movie,
		archived_file_name=self.archived_file_name)

	# search for first offset so we can skip unnecessary clusters later on
	start_offset = 2 ** 63  # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)

	attachments = {}
	tracks_main = {}  # contains TrackData objects; main mkv info
	current_attachment = None
	cluster_count = 0
	done = False
	current_track_nb = 0
	header_stripping = False

	while er.read() and not done:
		if er.element_type in (EbmlElementType.Segment,
		                       EbmlElementType.BlockGroup,
							   EbmlElementType.TrackList,
							   EbmlElementType.Track,
							   EbmlElementType.ContentEncodingList,
							   EbmlElementType.ContentEncoding,
							   EbmlElementType.Compression,
		                       EbmlElementType.AttachmentList,
		                       EbmlElementType.Attachment):
			er.move_to_child()
		elif er.element_type in (EbmlElementType.TimecodeScale,
		                         EbmlElementType.Timecode,
		                         EbmlElementType.TrackCodec):
			er.skip_contents()
		elif er.element_type == EbmlElementType.Block:
			done = _mkv_block_extract(tracks, tracks_main, er, done)
		elif er.element_type == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while
			# (cluster is good because they're about 1MB each)
			cluster_count += 1
			show_spinner(cluster_count)

			# in extract mode, we know the first data offset we're looking for,
			# so skip any clusters before that
			if (er.current_element.element_start_pos +
				len(er.current_element.raw_header) +
				er.current_element.length < start_offset):
				er.skip_contents()
			else:
				er.move_to_child()
		elif er.element_type == EbmlElementType.TrackNumber:
			elm_content = er.read_contents()
			current_track_nb = GetEbmlUInt(elm_content, 0, len(elm_content))
			if not current_track_nb in tracks_main:
				td = TrackData()
				td.track_number = current_track_nb
				tracks_main[current_track_nb] = td
			done = False
		elif er.element_type == EbmlElementType.TrackCodec:
			# not necessary, but might be useful for debugging output
			elm_content = er.read_contents()
			tracks_main[current_track_nb].codec = elm_content.decode(
			                                        "ascii", errors="ignore")
		elif er.element_type == EbmlElementType.CompressionAlgorithm:
			elm_content = er.read_contents()
			algorithm = GetEbmlUInt(elm_content, 0, len(elm_content))
			header_stripping = algorithm == 3
		elif er.element_type == EbmlElementType.CompressionSettings:
			elm_content = er.read_contents()
			if header_stripping:
				tracks_main[current_track_nb].compression_settings = elm_content
		elif er.element_type == EbmlElementType.AttachedFileName:
			current_attachment = er.read_contents()
			if current_attachment not in attachments:
				att = AttachmentData(current_attachment)
				attachments[current_attachment] = att
		elif er.element_type == EbmlElementType.AttachedFileData:
			attachment = attachments[current_attachment]
			attachment.size = er.current_element.length

			# in extract mode,
			# extract all attachments in case we need them later
			if attachment.attachment_file == None:
				attachment.attachment_file = tempfile.TemporaryFile()
				attachment.attachment_file.write(er.read_contents())
				attachment.attachment_file.seek(0)
		else:
			er.skip_contents()

	remove_spinner()

	er.close()
	return tracks, attachments

def _mkv_block_extract(tracks, tracks_main, er, done):
	# grab the current track for main mkv and .srs meta data
	try:
		track = tracks[er.current_element.track_number]
	except KeyError:
		# 2001.A.Space.Odyssey.1968.1080p.MULTI.BluRay.x264-1080 sample
		# System.Collections.Generic.KeyNotFoundException on .NET version
		er.skip_contents()
		return done
	track_main = tracks_main[er.current_element.track_number]

	# grab compression settings
	sforsample = b""  # settings for the sample tracks
	sformain = b""  # settings for main tracks
	if track.compression_settings:
		sformain = track.compression_settings
	if track_main.compression_settings:
		sforsample = track_main.compression_settings
	header_stripping_both_files = sformain and sforsample

	if (er.current_element.element_start_pos +
		len(er.current_element.raw_header) +
		len(er.current_element.raw_block_header) +
		er.current_element.length > track.match_offset):
		if track.track_file == None:
			track.track_file = tempfile.TemporaryFile()
		buff = er.read_contents()
		offset = 0
		for i in range(len(er.current_element.frame_lengths)):
			if (er.current_element.element_start_pos +
			len(er.current_element.raw_header) +
			len(er.current_element.raw_block_header) +
			offset >= track.match_offset and
			track.track_file.tell() < track.data_length):
				if header_stripping_both_files:
					if sforsample == sformain:
						# no removed header to be added
						track.track_file.write(buff[offset:offset + 
							er.current_element.frame_lengths[i]])
					elif len(sforsample) < len(sformain):
						# more stripped in sample
						cut = len(sformain) - len(sforsample) 
						track.track_file.write(buff[offset + cut:offset + 
							er.current_element.frame_lengths[i]])
					elif len(sforsample) > len(sformain):
						# more stripped in main (weird, but possible in theory)
						add = len(sforsample) - len(sformain)
						track.track_file.write(sforsample[-add:])
						track.track_file.write(buff[offset:offset + 
							er.current_element.frame_lengths[i]])
				else:
					track.track_file.write(sforsample)
					track.track_file.write(buff[offset + len(sformain):offset +
					   er.current_element.frame_lengths[i]])
			offset += er.current_element.frame_lengths[i]

		tracks_done = True
		for track_data in tracks.values():
			if (track_data.track_file == None or
			track_data.track_file.tell() < track_data.data_length):
				tracks_done = False
				break
		done = tracks_done
	else:
		er.skip_contents()

	return done

def mp4_extract_sample_streams(self, tracks, main_mp4_file):
	mtracks = profile_mp4(FileData(file_name=main_mp4_file),
	                      calculate_crc32=False,
	                      archived_file_name=self.archived_file_name)

	for track_nb, track in tracks.items():
		mtrack = mtracks[track_nb]
		track = mp4_extract_sample_stream(track, mtrack, main_mp4_file)
		tracks[track_nb] = track

	return tracks, {}  # attachments

def open_main(big_file):
	if utility.is_rar(big_file):
		return rarstream.RarStream(big_file)
	else:
		return open(big_file, "rb")

def mp4_extract_sample_stream(track, mtrack, main_mp4_file):
	"""Can throw InvalidMatchOffset"""
	track.track_file = tempfile.TemporaryFile()
	mtrack = mp4_add_track_stream(mtrack)
	mtrack.trackstream.stream = open_main(main_mp4_file)

	mtrack.trackstream.seek(track.match_offset)
	track.track_file.write(mtrack.trackstream.read(track.data_length))

	mtrack.trackstream.stream.close()
	return track

def wmv_extract_sample_streams(self, tracks, main_wmv_file):
	ar = AsfReader(AsfReadMode.Sample, main_wmv_file,
		archived_file_name=self.archived_file_name)

	# search for first match offset
	start_offset = 2 ** 63  # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)

	done = False
	while ar.read() and not done:
		o = ar.current_object
		oguid = ar.object_guid

		if oguid == GUID_DATA_OBJECT:
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack_from(o.raw_header, i)
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) // total_data_packets
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				# don't do unnecessary processing
				if start + i * psize + psize < start_offset:
					continue
				data = ar.read_data_part(start + i * psize, psize)
				assert len(data) == psize

				if i % 15 == 0:
					show_spinner(i)

				packet = AsfDataPacket()
				packet.data = data
				packet.data_file_offset = start + i * psize
				packet.data_size = len(data)  # psize

				tmp = asf_data_get_packet(packet, psize)
				assert tmp == packet.length == psize

				prev_payloads_size = 0
				for payload in packet.payloads:
					# grab track or create new track
					track_number = payload.stream_number
					if track_number not in tracks:
						tracks[track_number] = TrackData()
						tracks[track_number].track_number = track_number
					track = tracks[track_number]

					if (packet.data_file_offset + prev_payloads_size
						+ payload.header_size
						+ payload.data_length >= track.match_offset):
						if track.track_file == None:
							track.track_file = tempfile.TemporaryFile()

						# check if we grabbed enough data
						if track.track_file.tell() < track.data_length:
							if (packet.data_file_offset + prev_payloads_size
								 + payload.header_size
								>= track.match_offset):
								# all the payload data
								track.track_file.write(payload.data)
							else:
								# stream started from the middle of a payload
								print("WMV does this too? Tell me.")
								payload_offset = (track.match_offset -
								    (packet.data_file_offset +
									 prev_payloads_size + payload.header_size))
								track.track_file.write(payload.data[
								    payload_offset:])

						tracks_done = True
						for track_data in tracks.values():
							if (track_data.track_file == None or
								track_data.track_file.tell() <
								track_data.data_length):
								tracks_done = False
								break
						done = tracks_done

					prev_payloads_size += (payload.data_length +
					                       payload.header_size)
				if done:
					break
			ar.skip_contents()
		else:
			ar.skip_contents()
	ar.close()

	remove_spinner()

	return tracks, {}  # attachments

def flac_extract_sample_streams(self, tracks, main_flac_file):
	fr = FlacReader(main_flac_file, archived_file_name=self.archived_file_name)
	while fr.read():
		if fr.current_block.is_frame_data():
			track = tracks[1]
			track.track_file = tempfile.TemporaryFile()
			track.track_file.write(fr.read_contents())
			tracks[1] = track
		fr.skip_contents()
	fr.close()

	return tracks, {}

def mp3_extract_sample_streams(self, tracks, main_mp3_file):
	mr = Mp3Reader(main_mp3_file, archived_file_name=self.archived_file_name)
	for block in mr.read():
		if block.type in ("MP3", "fLaC"):
			track = tracks[1]
			track.track_file = tempfile.TemporaryFile()
			# offset is always zero for now (no sample support)
			# (start offset must match in mp3_find_sample_streams)
			offset = track.match_offset - block.start_pos
			assert offset >= 0, "MP3 read offset can't be negative"
			track.track_file.write(mr.read_part(track.match_length, offset))
			tracks[1] = track
			break
	mr.close()

	return tracks, {}

def stream_extract_sample_streams(self, tracks, main_file):
	if is_rar(main_file):
		stream = rarstream.RarStream(main_file, self.archived_file_name)
	else:
		stream = open(main_file, 'rb')

	try:
		track = tracks[1]
		track.track_file = tempfile.TemporaryFile()
		stream.seek(track.match_offset)
		assert stream.read(len(track.signature_bytes)) == track.signature_bytes
		stream.seek(track.match_offset)
		track.track_file.write(stream.read(track.data_length))
		tracks[1] = track
	finally:
		stream.close()

	return tracks, {}

def avi_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	rr = RiffReader(RiffReadMode.SRS, path=srs)

	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)

	with open(out_file, "wb") as sample:
		block_count = 0
		while rr.read():
			# skip over our custom chunks in rebuild mode
			# (only read it in load mode)
			if rr.current_chunk.fourcc in (b"SRSF", b"SRST"):
				rr.skip_contents()
				continue

			sample.write(rr.current_chunk.raw_header)
			crc = crc32(rr.current_chunk.raw_header, crc) & 0xFFFFFFFF

			if rr.chunk_type == RiffChunkType.List:
				rr.move_to_child()
			else:  # normal chunk
				if rr.chunk_type == RiffChunkType.Movi:
					block_count += 1
					if block_count % 15 == 0:
						show_spinner(block_count)

					track = tracks[rr.current_chunk.stream_number]
					buff = track.track_file.read(rr.current_chunk.length)
					sample.write(buff)
					crc = crc32(buff, crc) & 0xFFFFFFFF
					rr.skip_contents()
				else:
					buff = rr.read_contents()
					sample.write(buff)
					crc = crc32(buff, crc) & 0xFFFFFFFF

				if rr.has_padding:
					pb = S_BYTE.pack(rr.padding_byte)
					sample.write(pb)
					crc = crc32(pb, crc) & 0xFFFFFFFF

	remove_spinner()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF

	if ofile.crc32 != srs_data.crc32:
		# TODO: try again with the correct interleaving for LOL samples
		pass

	rr.close()
	return ofile

def mkv_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	er = EbmlReader(EbmlReadMode.SRS, path=srs)

	for track in tracks.values():
		if track.track_file:
			track.track_file.seek(0)
		# fixes The.Butterfly.Effect.3.Revelations.2009.STV
		# .FRENCH.720p.BluRay.x264-ROUGH reconstruction bug
		# It gives an error in ReSample .NET 1.2:
		#   Unexpected Error:
		#   System.NullReferenceException

	with open(out_file, "wb") as sample:
		current_attachment = None
		cluster_count = 0
		while er.read():
			# the ReSample element is the only part of the SRS file
			# we don't want copied into the new sample.
			if er.element_type == EbmlElementType.ReSample:
				er.skip_contents()
				continue

			sample.write(er.current_element.raw_header)
			crc = crc32(er.current_element.raw_header, crc) & 0xFFFFFFFF

			if er.element_type in (EbmlElementType.Segment,
			                       EbmlElementType.AttachmentList,
			                       EbmlElementType.Attachment,
			                       EbmlElementType.BlockGroup):
				# these elements have no useful info of their own,
				# but we want to step into them to examine their children
				er.move_to_child()
			elif er.element_type == EbmlElementType.Cluster:
				# simple progress indicator since this can take a while
				# (cluster is good because they're about 1mb each)
				cluster_count += 1
				show_spinner(cluster_count)
				er.move_to_child()
			elif er.element_type == EbmlElementType.AttachedFileName:
				current_attachment = er.read_contents()
				sample.write(current_attachment)
				crc = crc32(current_attachment, crc) & 0xFFFFFFFF
			elif er.element_type == EbmlElementType.AttachedFileData:
				attachment = attachments[current_attachment]
				# restore data from extracted attachments
				buff = attachment.attachment_file.read()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF
				if srs_data.flags & FileData.ATTACHMENTS_REMOVED != 0:
					er.move_to_child()  # really means do nothing in this case
				else:
					er.skip_contents()
			elif er.element_type == EbmlElementType.Block:
				track = tracks[er.current_element.track_number]
				# restore data from extracted tracks
				buff = track.track_file.read(er.current_element.length)
				rbh = er.current_element.raw_block_header
				sample.write(rbh)
				crc = crc32(rbh, crc) & 0xFFFFFFFF
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF
				er.move_to_child()  # really means do nothing in this case
			else:
				# anything not caught above is considered metadata,
				# so we copy it as is
				buff = er.read_contents()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF

	er.close()
	remove_spinner()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def mp4_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue

	tracks = profile_mp4_srs(srs, tracks)
	for track in tracks.values():
		track.track_file.seek(0)
		track = mp4_add_track_stream(track)  # for the sorting later on

	mr = MovReader(MovReadMode.SRS, path=srs)

	with open(out_file, "wb") as sample:
		while mr.read():
			# we don't want the SRS elements copied into the new sample.
			if mr.atom_type in (b"SRSF", b"SRST"):
				mr.skip_contents()
				continue

			sample.write(mr.current_atom.raw_header)
			crc = crc32(mr.current_atom.raw_header, crc) & 0xFFFFFFFF

			if mr.atom_type == b"mdat":
				mr.move_to_child()

				# order the interleaved chunks
				for (chunk, track_nb) in order_chunks(tracks):
					track = tracks[track_nb]
					buff = track.track_file.read(sum(chunk.samples))
					# write all the stream data
					sample.write(buff)
					crc = crc32(buff, crc) & 0xFFFFFFFF
			else:
				# anything not caught above is considered meta data,
				# so we copy it as is
				buff = mr.read_contents()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF
	mr.close()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def order_chunks(tracks):
	all_chunks = []
	for track in tracks.values():
		for chunk in track.trackstream.chunks:
			all_chunks.append((chunk, track.track_number))

	all_chunks = sorted(all_chunks, key=lambda c: c[0].chunk_offset)
	return all_chunks

def profile_mp4_srs(srs, tracks):  # XXX: copy paste edit from other function
	"""Reads the necessary track header data 
	and adds this info to the tracks"""
	current_track = None
	track_processed = False
	mr = MovReader(MovReadMode.SRS, srs)
	while mr.read():
		atype = mr.atom_type

		# doing body
		if atype in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
			mr.move_to_child()
		elif atype == b"mdat":
			mr.move_to_child()
		else:
			data = mr.read_contents()

		if atype in (b"tkhd",):
			# grab track id
			(track_id,) = BE_LONG.unpack_from(data, 12)
			current_track = tracks[track_id]

			# initialization
			current_track.chunk_offsets = []
			current_track.chunk_lengths = []
			current_track.sample_lengths = []
			track_processed = False
		elif atype in (b"stco", b"co64"):
			# exactly one variant must be present
			assert current_track != None
			(entry_count,) = BE_LONG.unpack_from(data, 4)
			if atype == b"stco":
				size = 4
				structunp = BE_LONG
			else:  # b"co64"
				size = 8
				structunp = BE_LONGLONG
			for i in range(entry_count):
				j = 8 + i * size
				(offset,) = structunp.unpack_from(data, j)
				current_track.chunk_offsets.append(offset)
		elif atype == b"stsc":  # Sample To Chunk Box
			(entry_count,) = BE_LONG.unpack_from(data, 4)
			for i in range(entry_count):
				j = 8 + i * 12
				# first_chunk
				# samples_per_chunk
				# sample_description_index
				result_tuple = struct.unpack_from(">LLL", data, j)
				current_track.chunk_lengths.append(result_tuple)

			# enlarge compactly coded tables
			current_track.chunk_lengths = stsc(current_track.chunk_lengths)
		elif atype in (b"stsz", b"stz2"):  # Sample Size Boxes
			(sample_size,) = BE_LONG.unpack_from(data, 4)
			(sample_count,) = BE_LONG.unpack_from(data, 8)
			if sample_size == 0:
				for i in range(sample_count):
					j = 12 + i * 4
					(out,) = BE_LONG.unpack_from(data, j)
					current_track.sample_lengths.append(out)
			else:
				for i in range(sample_count):
					current_track.sample_lengths.append(sample_size)


		if (current_track and (not track_processed) and
		    len(current_track.chunk_offsets) and
		    len(current_track.chunk_lengths) and
		    len(current_track.sample_lengths)):
			track_processed = True
	mr.close()

	return tracks

def wmv_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	ar = AsfReader(AsfReadMode.SRS, path=srs)
	padding_index = 0

	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)

	with open(out_file, "wb") as sample:
		while ar.read():
			# skip over our custom chunks in rebuild mode
			# (only read it in load mode)
			if (ar.current_object.type == GUID_SRS_FILE or
			    ar.current_object.type == GUID_SRS_TRACK or
			    ar.current_object.type == GUID_SRS_PADDING):
				ar.skip_contents()
				continue

			o = ar.current_object
			oguid = ar.object_guid

			# 1) header
			sample.write(ar.current_object.raw_header)
			crc = crc32(ar.current_object.raw_header, crc) & 0xFFFFFFFF

			# 2) body
			if oguid == GUID_DATA_OBJECT:
				i = 16 + 8 + 16
				(total_data_packets,) = S_LONGLONG.unpack_from(o.raw_header, i)
				# data packet/media object size
				psize = (o.osize - len(o.raw_header)) // total_data_packets
				rp_offsets = 0
				start = o.start_pos + len(o.raw_header)
				for i in range(total_data_packets):
					if i % 15 == 0:
						show_spinner(i)

					packet = AsfDataPacket()
					packet.data_file_offset = start + rp_offsets
					data = ar.read_data_part(packet.data_file_offset, psize)
					packet.data = data
					packet.data_size = len(data)

					s = asf_data_get_packet(packet, psize, AsfReadMode.SRS)
					rp_offsets += s

					# 1) packet header
					pheader_data = data[:packet.header_length]
					sample.write(pheader_data)
					crc = crc32(pheader_data, crc) & 0xFFFFFFFF

					# 2) packet payload
					for payload in packet.payloads:
						track = tracks[payload.stream_number]

						# 1) header data
						sample.write(payload.header_data)
						crc = crc32(payload.header_data, crc) & 0xFFFFFFFF
						assert payload.header_size == len(payload.header_data)

						# 2) payload data
						buff = track.track_file.read(payload.data_length)
						sample.write(buff)
						crc = crc32(buff, crc) & 0xFFFFFFFF

					# 3) padding bytes
					try:
						data = srs_data.padding_bytes[padding_index:
						          padding_index + packet.padding_length]
						sample.write(data)
						crc = crc32(data, crc) & 0xFFFFFFFF
						padding_index += packet.padding_length
					except AttributeError:
						data = b"\x00" * packet.padding_length
						sample.write(data)
						crc = crc32(data, crc) & 0xFFFFFFFF

				ar.skip_contents()
			else:
				buff = ar.read_contents()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFF
	ar.close()
	remove_spinner()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def flac_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	fr = FlacReader(path=srs)

	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)

	with open(out_file, "wb") as flac:
		srs_flac_blocks = 0
		while fr.read():
			assert not fr.read_done

			if fr.block_type == "fLaC":
				flac.write(b"fLaC")
				crc = crc32(b"fLaC", crc)
				fr.skip_contents()
			elif (fr.block_type in bytearray(b"stu") and
					srs_flac_blocks <= 3):
				srs_flac_blocks += 1
				fr.skip_contents()
			else:
				crc = crc32(fr.current_block.raw_header, crc)
				flac.write(fr.current_block.raw_header)
				data = fr.read_contents()
				crc = crc32(data, crc)
				flac.write(data)
				if fr.current_block.is_last_block():
					track = tracks[1]
					crc = crc32(track.track_file.read(), crc)
					track.track_file.seek(0)
					flac.write(track.track_file.read())

			assert fr.read_done
	fr.close()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def mp3_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	mr = Mp3Reader(path=srs)

	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)

	main_data_written = False
	with open(out_file, "wb") as mp3:
		for block in mr.read():
			if block.type in ("SRSF", "SRST", "SRSP"):
				if not main_data_written:
					# we are on an SRS block and no sound data is written yet
					track = tracks[1]
					crc = crc32(track.track_file.read(), crc)
					track.track_file.seek(0)
					mp3.write(track.track_file.read())
					main_data_written = True
			else:
				data = mr.read_contents()
				mp3.write(data)
				crc = crc32(data, crc)
	mr.close()

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def stream_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	crc = 0  # Crc32.StartValue
	with open(out_file, "wb") as stream:
		track = tracks[1]
		track.track_file.seek(0)
		data = track.track_file.read()
		crc = crc32(data, crc)
		stream.write(data)

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def m2ts_rebuild_sample(self, srs_data, tracks, attachments, srs, out_file):
	raise NotImplemented()
	crc = 0  # Crc32.StartValue
	with open(out_file, "wb") as stream:

		track = tracks[1]
		data = b""
		track.track_file.seek(0)
		data += track.track_file.read()
		crc = crc32(data, crc)
		stream.write(data)

	ofile = FileData(file_name=out_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

if __name__ == "__main__":
	unittest.main()
