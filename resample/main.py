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

from __future__ import print_function, absolute_import
import struct
import io
import os
import sys
import unittest
import tempfile
import collections

from os.path import basename
from struct import Struct
from zlib import crc32

import resample

from rescene import rarstream
from rescene import utility
from rescene.utility import sep, show_spinner, remove_spinner

from resample.ebml import (EbmlReader, EbmlReadMode, EbmlElementType, 
                           MakeEbmlUInt, EbmlID)
from resample.riff import RiffReader, RiffReadMode, RiffChunkType
from resample.mov import MovReader, MovReadMode
from resample.asf import (AsfReader, AsfReadMode, GUID_HEADER_OBJECT, 
						GUID_DATA_OBJECT, GUID_STREAM_OBJECT, GUID_FILE_OBJECT,
						GUID_SRS_FILE, GUID_SRS_TRACK, AsfDataPacket,
						asf_data_get_packet, GUID_SRS_PADDING)

try:
	odict = collections.OrderedDict #@UndefinedVariable
except AttributeError:
	# Python 2.6 OrderedDict
	from rescene import ordereddict
	odict = ordereddict.OrderedDict

"""
http://forum.doom9.org/showthread.php?s=&threadid=62723
http://sourceforge.net/projects/pymedia/files/pymedia/
https://code.google.com/p/mutagen/

"""

S_LONGLONG = Struct('<Q') # unsigned long long: 8 bytes
S_LONG = Struct('<L') # unsigned long: 4 bytes
S_SHORT = Struct('<H') # unsigned short: 2 bytes
S_BYTE = Struct('<B') # unsigned char: 1 byte

BE_LONG = Struct('>L')
BE_LONGLONG = Struct('>Q')

SIG_SIZE = 256

class IncompleteSample(Exception):
	pass

# srs.cs ----------------------------------------------------------------------
class FileType(object):
	MKV, AVI, MP4, WMV, MP3, FLAC, M2TS, VOB, Unknown =  \
		("MKV", "AVI", "MP4", "WMV", "MP3", "FLAC", "M2TS", "VOB", "Unknown")

def get_file_type(ifile):
	"""Decide the type of file based on the magic marker"""
	MARKER_MKV = b"\x1a\x45\xdf\xa3" # .Eߣ
	MARKER_AVI = b"\x52\x49\x46\x46" # RIFF
	MARKER_RAR = b"\x52\x61\x72\x21\x1A\x07\x00" # Rar!...
	MARKER_MP4 = b"\x66\x74\x79\x70" # ....ftyp
	MARKER_MP4_3GP = b"\x33\x67\x70\x35" # 3gp5
	MARKER_WMV = b"\x30\x26\xB2\x75"
	MARKER_MP3 = b"\x49\x44\x33" # ID3 (different for an EOS mp3)
	
	with open(ifile, 'rb') as ofile:
		marker = ofile.read(14)
		
	if marker.startswith(MARKER_RAR):
		# Read first file from the RAR archive
		rs = rarstream.RarStream(ifile)
		marker = rs.read(8)
		rs.close()
		
	if marker.startswith(MARKER_MKV):
		return FileType.MKV
	elif marker.startswith(MARKER_AVI):
		return FileType.AVI
	if marker[4:].startswith(MARKER_MP4) or marker.startswith(MARKER_MP4_3GP):
		# http://wiki.multimedia.cx/index.php?title=QuickTime_container
		# Extensions: mov, qt, mp4, m4v, m4a, m4p, m4b, m4r, k3g, skm, 3gp, 3g2
		return FileType.MP4
	elif marker.startswith(MARKER_WMV):
		return FileType.WMV
	elif marker.startswith(MARKER_MP3):
		return FileType.Unknown
	else:
		return FileType.Unknown

# SampleAttachmentInfo.cs -----------------------------------------------------
class AttachmentData(object):
	def __init__(self, name, size=0, attachment_file=None):
		self.size = size
		self.name = name
		self.attachment_file = attachment_file
		
	def __repr__(self, *args, **kwargs):
		return ("<attachement_data name=%r size=%r>" % self.name, self.size)

# SampleFileInfo.cs -----------------------------------------------------------
class FileData(object):
	"""Stored tool and file data like size and crc32 from SRS file."""
	NO_FLAGS = 0x0
	SIMPLE_BLOCK_FIX = 0x1
	ATTACHEMENTS_REMOVED = 0x2
	#BIGFILE = 0x4
	
	# //default to using new features
	SUPPORTED_FLAG_MASK = SIMPLE_BLOCK_FIX | ATTACHEMENTS_REMOVED
	
	def __init__(self, buff=None, file_name=None):
		# default to using new features
		self.flags = self.SIMPLE_BLOCK_FIX | self.ATTACHEMENTS_REMOVED 
		self.crc32 = 0
		
		if file_name:
			self.name = file_name # can be RAR
			if utility.is_rar(file_name):
				rs = rarstream.RarStream(file_name)
				self.size = rs.seek(0, os.SEEK_END)
				self.sample_name = str(rs.packed_file_name)
				rs.close()
			else:
				self.sample_name = file_name
				self.size = os.path.getsize(file_name)
		elif buff:
			# flags: unsigned integer 16
			# appname length: uint16
			# name length: uint16
			# crc: uint32
			(self.flags,) = S_SHORT.unpack_from(buff, 0)
			(applength,) = S_SHORT.unpack_from(buff, 2)
			self.appname = buff[4:4+applength]
			(namelength,) = S_SHORT.unpack_from(buff, 4+applength)
			self.sample_name = buff[4+applength+2:4+applength+2+namelength]
			self.name = self.sample_name
			offset = 4+applength+2+namelength
			(self.size,) = S_LONGLONG.unpack_from(buff, offset)
			(self.crc32,) = S_LONG.unpack_from(buff, offset+8)
		else:
			raise AttributeError("Buffer or file expected.")
		
	def serialize(self):
		#"".encode("utf-8")
		app_name = resample.APPNAME
		file_name = basename(self.sample_name)
		data_length = 18 + len(app_name) + len(file_name)
	
		buff = io.BytesIO()
		buff.write(S_SHORT.pack(self.flags)) # 2 bytes
		buff.write(S_SHORT.pack(len(app_name))) # 2 bytes
		buff.write(app_name)
		buff.write(S_SHORT.pack(len(file_name))) # 2 bytes
		buff.write(file_name)
		buff.write(S_LONGLONG.pack(self.size)) # 8 bytes
		buff.write(S_LONG.pack(self.crc32 & 0xFFFFFFFF)) # 4 bytes
		
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
		chunk = "SRSF"
		chunk += S_LONG.pack(len(data))
		chunk += data
		return chunk
		
	def serialize_as_mov(self):
		data = self.serialize()
		atom = struct.pack(">L", len(data) + 8)
		atom += "SRSF"
		atom += data
		return atom
	
	def serialize_as_asf(self):
		data = self.serialize()
		asf_object = GUID_SRS_FILE 
		asf_object += S_LONGLONG.pack(len(data) + 16 + 8)
		asf_object += data
		return asf_object
	
# SampleTrackInfo.cs ----------------------------------------------------------					
class TrackData(object):
	"""Flags: big sample or not?
	Track number
	Data length: size of the track
	Match offset: location in the main file where the track is located
	Signature length
	Signature: how we recognize the track location if we have no offset"""
	NO_FLAGS = 0x0
	BIG_FILE = 0x4 # Larger than 2GB
	BIG_TACK_NUMBER = 0x8 # MP4 container has larger possible numbers
	
	SUPPORTED_FLAG_MASK = BIG_FILE | BIG_TACK_NUMBER
	
	def __init__(self, buff=None):
		if buff:
			(self.flags,) = struct.unpack("<H", buff[0:2])
			
			if self.flags & self.BIG_TACK_NUMBER:
				(self.track_number,) = S_LONG.unpack(buff[2:6])
				e = 2 # extra because of the larger file
			else:
				(self.track_number,) = S_SHORT.unpack(buff[2:4])
				e = 0
			
			if self.flags & self.BIG_FILE:
				struct_string = "Q"
				add = 8
			else:
				struct_string = "L"
				add = 4
				
			(self.data_length, self.match_offset, sig_length) =  \
				struct.unpack(str("<%sQH" % struct_string), 
				              buff[e+4:e+4+add+10])
			self.signature_bytes = buff[(e+14+add):(e+14+add+sig_length)]
		else:
			self.flags = self.NO_FLAGS
			self.track_number = 0
			self.data_length = 0
			self.match_offset = 0
			self.signature_bytes = ""
		self.match_length = 0
		self.check_bytes = ""
		self.track_file = None 
		
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
			
	def serialize(self):
		big_file = self.flags & self.BIG_FILE
		data_length = 14 + len(self.signature_bytes) + (8 if big_file else 4)
		
		buff = io.BytesIO()
		buff.write(S_SHORT.pack(self.flags))
		
		if self.track_number >= 2**16:
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
		chunk = "SRST"
		chunk += S_LONG.pack(len(data))
		chunk += data
		return chunk	
	
	def serialize_as_mov(self):
		data = self.serialize()
		atom = struct.pack(">L", len(data) + 8)
		atom += "SRST"
		atom += data
		return atom
	
	def serialize_as_asf(self):
		data = self.serialize()
		asf_object = GUID_SRS_TRACK
		asf_object += S_LONGLONG.pack(len(data) + 16 + 8)
		asf_object += data
		return asf_object
	
class ReSample(object):
	pass

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
	
# AviReSample.cs --------------------------------------------------------------	
class AviReSample(ReSample):
	file_type = FileType.AVI
	
	def profile_sample(self, *args, **kwargs):
		return avi_profile_sample(*args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return avi_create_srs(*args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return avi_load_srs(*args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return avi_find_sample_streams(*args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return avi_extract_sample_streams(*args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return avi_rebuild_sample(*args, **kwargs)

# MkvReSample.cs --------------------------------------------------------------
class MkvReSample(ReSample):
	file_type = FileType.MKV
	
	def profile_sample(self, *args, **kwargs):
		return mkv_profile_sample(*args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return mkv_create_srs(*args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return mkv_load_srs(*args, **kwargs)		
	def find_sample_streams(self, *args, **kwargs):
		return mkv_find_sample_streams(*args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return mkv_extract_sample_streams(*args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return mkv_rebuild_sample(*args, **kwargs)

class Mp4ReSample(ReSample):
	file_type = FileType.MP4
	
	def profile_sample(self, *args, **kwargs):
		return mp4_profile_sample(*args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return mp4_create_srs(*args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return mp4_load_srs(*args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return mp4_find_sample_streams(*args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return mp4_extract_sample_streams(*args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return mp4_rebuild_sample(*args, **kwargs)

class WmvReSample(ReSample):
	file_type = FileType.WMV
	
	def profile_sample(self, *args, **kwargs):
		return wmv_profile_sample(*args, **kwargs)
	def create_srs(self, *args, **kwargs):
		return wmv_create_srs(*args, **kwargs)
	def load_srs(self, *args, **kwargs):
		return wmv_load_srs(*args, **kwargs)
	def find_sample_streams(self, *args, **kwargs):
		return wmv_find_sample_streams(*args, **kwargs)
	def extract_sample_streams(self, *args, **kwargs):
		return wmv_extract_sample_streams(*args, **kwargs)
	def rebuild_sample(self, *args, **kwargs):
		return wmv_rebuild_sample(*args, **kwargs)
	
def avi_load_srs(infile):
	tracks = {}
	rr = RiffReader(RiffReadMode.SRS, infile)
	done = False
	while not done and rr.read():
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else:
			if rr.current_chunk.fourcc == "SRSF": # resample file
				srs_data = FileData(rr.read_contents())
			elif rr.current_chunk.fourcc == "SRST": # resample track
				track = TrackData(rr.read_contents())
				tracks[track.track_number] = track
			elif rr.chunk_type == RiffChunkType.Movi:
				# if we get here in load mode, 
				# we have already got what we need, so bail out
				done = True
#				continue
				break
			else:
				rr.skip_contents()
	rr.close()
	return srs_data, tracks

def mkv_load_srs(infile):
	tracks = {}
	er = EbmlReader(EbmlReadMode.SRS, infile)
	done = False
	while not done and er.read():
		if (er.element_type == EbmlElementType.Segment or
			er.element_type == EbmlElementType.ReSample):
				er.move_to_child()
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
	return srs_data, tracks

def mp4_load_srs(infile):
	tracks = {}
	mr = MovReader(MovReadMode.SRS, infile)
	while mr.read():
		if mr.atom_type == "SRSF":
			srs_data = FileData(mr.read_contents())
		elif mr.atom_type == "SRST":
			track = TrackData(mr.read_contents())
			tracks[track.track_number] = track
		elif mr.atom_type == "mdat":
			mr.move_to_child()
		else:
			mr.skip_contents()	
	mr.close()
	return srs_data, tracks

def wmv_load_srs(infile):
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

def avi_profile_sample(avi_data): # FileData object
	tracks = {}
	attachments = {} # not used for AVI
	
	other_length = 0
	blockcount = 0

	avi_data.crc32 = 0x0 # start value crc
	
	rr = RiffReader(RiffReadMode.Sample, avi_data.name)
	while rr.read():
		assert not rr.read_done
		c = rr.current_chunk
		
		other_length += len(c.raw_header)
		avi_data.crc32 = crc32(c.raw_header, avi_data.crc32)
		
		if rr.chunk_type == RiffChunkType.List:
			fsize = c.chunk_start_pos + len(c.raw_header) + c.length
			if c.list_type == "RIFF" and fsize > avi_data.size:
				print("\nWarning: File size does not appear to be correct!",
				      "\t Expected at least: %s" % sep(fsize),
				      "\t Found            : %s\n" % sep(avi_data.size), 
				      sep='\n', file=sys.stderr)
			rr.move_to_child()
		else: # normal chunk
			if rr.chunk_type == RiffChunkType.Movi:
				# chunk containing stream data (our main focus)
				blockcount += 1
				if blockcount % 15 == 0:
					show_spinner(blockcount)
				
				track_number = c.stream_number
				if not tracks.has_key(track_number):
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
						sig += movi_data[0:lsig-len(sig)]
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
		       "       The sample is likely corrupted or incomplete.") 
		raise IncompleteSample(msg)
	
	return tracks, attachments

def mkv_profile_sample(mkv_data): # FileData object
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
	current_attachment = None
	elm_content = None
	
	mkv_data.crc32 = 0x0 # start value crc
	
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
			er.move_to_child()
		elif etype == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while 
			# (cluster is good because they're about 1mb each)
			cluster_count += 1
			show_spinner(cluster_count)
			er.move_to_child()
		elif etype in (EbmlElementType.BlockGroup, 
		               EbmlElementType.Attachment,
		               EbmlElementType.AttachmentList):
			# these elements have no useful info of their own, 
			# but we want to step into them to examine their children
			er.move_to_child()
		elif etype == EbmlElementType.AttachedFileName:
			elm_content = er.read_contents()
			other_length += len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
			current_attachment = elm_content
			if not current_attachment in attachments:
				ad = AttachmentData(current_attachment)
				attachments[current_attachment] = ad
		elif etype == EbmlElementType.AttachedFileData:
			elm_content = er.read_contents()
			attachments[current_attachment].size = len(elm_content)
			mkv_data.crc32 = crc32(elm_content, mkv_data.crc32)
		elif etype == EbmlElementType.Block:
			block_count += 1
			if not er.current_element.track_number in tracks:
				td = TrackData()
				td.track_number = er.current_element.track_number
				tracks[er.current_element.track_number] = td
				
			track = tracks[er.current_element.track_number]
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
					sig += elm_content[0:lsig-len(sig)]
					track.signature_bytes = sig
				else: # this branch can be eliminated + the test
					lsig = min(SIG_SIZE, len(elm_content))
					track.signature_bytes = elm_content[0:lsig]
		else:
			other_length += er.current_element.length
			mkv_data.crc32 = crc32(er.read_contents(), mkv_data.crc32)
		
		assert er.read_done
	er.close()
	remove_spinner()
	
	total_size = other_length
	attachmentSize = 0
	
#	import locale
#	print(locale.getdefaultlocale())
#	lc = locale.getdefaultlocale()[0]
#	locale.setlocale(locale.LC_ALL, lc)
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
			attachmentSize += attachment.size
			
	print()
	print("Track Details:  Track  Length")
	print("                -----  -------------")
	for _, track in tracks.items():
		print("                {0:5n}  {1:>13}".format(track.track_number, 
		                                               sep(track.data_length)))
		total_size += track.data_length
		
	print()
	print("Parse Details:  Metadata     Attachments   Track Data     Total")
	print("                -----------  ------------  -------------  -------------")
	print("                {0:>11}  {1:>12}  {2:>13}  {3:>13}\n".format(
	      sep(other_length), sep(attachmentSize), 
		  sep(total_size - attachmentSize - other_length), sep(total_size)))
	
	if mkv_data.size != total_size:
		msg = ("Error: Parsed size does not equal file size.\n"
		       "       The sample is likely corrupted or incomplete.") 
		raise IncompleteSample(msg)
	
	return tracks, attachments

def profile_mp4(mp4_data): # FileData object
	"""Reads the necessary track header data 
	and constructs track signatures"""
	tracks = odict()
	
	meta_length = 0
	current_track = None
	mp4_data.crc32 = 0x0 # start value CRC 
	track_processed = False
	mr = MovReader(MovReadMode.Sample, mp4_data.name)
	while mr.read():
		a = mr.current_atom
		atype = mr.atom_type
#		print(atype)
		
		# 1) doing header
		meta_length += len(a.raw_header)
		mp4_data.crc32 = crc32(a.raw_header, mp4_data.crc32)
	
		# 2) doing body
		if atype in ("moov", "trak", "mdia", "minf", "stbl"):
			mr.move_to_child()
		elif atype == "mdat":
			data = mr.read_contents()
#			data_length = len(data)
			mp4_data.crc32 = crc32(data, mp4_data.crc32)
		else:
			data = mr.read_contents()
			meta_length += len(data)
			mp4_data.crc32 = crc32(data, mp4_data.crc32)
		
		if atype in ("tkhd",):
			# grab track id 
			(track_id,) = BE_LONG.unpack(data[12:16])
			assert not tracks.has_key(track_id)
			tracks[track_id] = TrackData()
			tracks[track_id].track_number = track_id
			current_track = tracks[track_id]
			
			# initialization
			current_track.chunk_offsets = []
			current_track.chunk_lengths = []
			current_track.sample_lengths = []
			track_processed = False
#			print(track_id)
			
		elif atype in ("stco", "co64"):
			# exactly one variant must be present
			assert current_track != None
			(entry_count,) = BE_LONG.unpack(data[4:8])
			if atype == "stco":
				size = 4
				structunp = BE_LONG
			else: # "co64"
				size = 8
				structunp = BE_LONGLONG
			for i in range(entry_count):
				j = 8 + i * size
				(offset,) = structunp.unpack(data[j:j+size])
				current_track.chunk_offsets.append(offset)	
#			print(current_track.chunk_offsets)
				
		elif atype == "stsc": # Sample To Chunk Box
			(entry_count,) = BE_LONG.unpack(data[4:8])
			for i in range(entry_count):
				j = 8 + i * 12
				# first_chunk
				# samples_per_chunk
				# sample_description_index
				result_tuple = struct.unpack(">LLL", data[j:j+12])
				current_track.chunk_lengths.append(result_tuple)
				
			# enlarge compactly coded tables
			current_track.chunk_lengths = stsc(current_track.chunk_lengths)

#			print(current_track.chunk_lengths)
				
		elif atype in ("stsz", "stz2"): # Sample Size Boxes
			(sample_size,) = BE_LONG.unpack(data[4:8])
			(sample_count,) = BE_LONG.unpack(data[8:12])
			if sample_size == 0:
				for i in range(sample_count):
					j = 12 + i * 4
					(out,) = BE_LONG.unpack(data[j:j+4])
					current_track.sample_lengths.append(out)
			else:
				for i in range(sample_count):
					current_track.sample_lengths.append(sample_size)
#			print(current_track.sample_lengths)
	
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
#	assert meta_length == mp4_data.size - data_length
	return tracks

def stsc(samples_chunk):
	"""Decompact compactly coded table."""
	old = samples_chunk
	new = []
	index = 1
	prev_samples_per_chunk = None
	prev_sample_description_index = None
	for (first_chunk, samples_per_chunk, 
		sample_description_index) in old:
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
		
def mp4_profile_sample(mp4_data):
	tracks = profile_mp4(mp4_data)
	# everything except stream data that will be removed
	total_size = mp4_data.other_length
	for _, track in tracks.items():
		total_size += track.data_length

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
		       "       The sample is likely corrupted or incomplete.") 
		raise IncompleteSample(msg)
	
	return tracks, {} #attachments

def mp4_signature_bytes(track, mp4_file):
	"""Returns the signature bytes for a track. The signature bytes are
	the 256 first bytes in the track."""
	previous_samples = 0
	signature_bytes = ""
	# iterate different offsets in the file where data of current track
	# can be found
	for chnb, chunk_offset in enumerate(track.chunk_offsets):
		# each offset is a chunk
		# a chunk exists of a number of samples
		try:
			samples_in_chunk = track.chunk_lengths[chnb][1]
		except IndexError:
			print("-SHOW ME-----------------------------------")
			# last element will contain right amount of samples
			samples_in_chunk = track.chunk_lengths[-1][1]
		# the sizes of the different samples of the chunk
		chunk_size = sum(track.sample_lengths[previous_samples:
		                 previous_samples+samples_in_chunk])
		
		chunk_content = ""
		with open(mp4_file, "rb") as mov:
			mov.seek(chunk_offset)
			chunk_content = mov.read(chunk_size)
		
		lsig = min(SIG_SIZE, len(signature_bytes) + chunk_size)
		signature_bytes += chunk_content[:lsig-len(signature_bytes)]
		
		previous_samples += samples_in_chunk
		if len(signature_bytes) == SIG_SIZE:
			return signature_bytes
	return signature_bytes

def profile_wmv(wmv_data): # FileData object
	"""Reads the necessary track header data 
	and constructs track signatures"""
	tracks = odict()
	
	meta_length = 0
	wmv_data.crc32 = 0x0 # start value CRC
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
			padding_bytes = ""
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack(o.raw_header[i:i+8])
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) / total_data_packets
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				data = ar.read_data_part(start + i * psize, psize)
				wmv_data.crc32 = crc32(data, wmv_data.crc32)
				
				if i % 15 == 0:
					show_spinner(i)
				
				packet = AsfDataPacket()
				packet.data = data
				packet.data_file_offset = start + i * psize
				packet.data_size = len(data) # psize
				
				asf_data_get_packet(packet, psize)
				
				header_data = data[:-packet.payload_data_len]
				payloads_sizes = 0
				headers_sizes = 0
				for payload in packet.payloads:
					header_data += payload.header_data
					
					if not payload.stream_number in tracks:
						#assert False # GUID_STREAM_OBJECT is bad
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
						sig += payload.data[0:lsig-len(sig)]
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
			(flags,) = S_SHORT.unpack(data[i:i+2])
			track_id = flags & 0xF
			assert not tracks.has_key(track_id)
			tracks[track_id] = TrackData()
			tracks[track_id].track_number = track_id
			
		if oguid == GUID_FILE_OBJECT:
			# exact size is stored in one of the header objects
			i = 16
			(file_size,) = S_LONGLONG.unpack(data[i:i+8])
			if (file_size != wmv_data.size):
				print("\nWarning: File size does not appear to be correct!",
				      "\t Expected: %s" % sep(file_size),
				      "\t Found   : %s\n" % sep(wmv_data.size), 
				      sep='\n', file=sys.stderr)
	ar.close()		
	
	wmv_data.other_length = meta_length
	remove_spinner()
	return tracks
	
def wmv_profile_sample(wmv_data):	
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
		       "       The sample is likely corrupted or incomplete.") 
		raise IncompleteSample(msg)
	
	return tracks, {} #attachments

def avi_create_srs(tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		rr = RiffReader(RiffReadMode.AVI, sample)
		while(rr.read()):
			c = rr.current_chunk
			
			srsf.write(c.raw_header)
			
			if rr.chunk_type == RiffChunkType.List:
				# in store mode, create and write our custom chunks 
				# as the first child of LIST movi
				# we put them after the avi headers 
				# so mediainfo can still read them from the SRS
				if c.list_type == "LIST" and c.fourcc == "movi":
					file_chunk = sample_data.serialize_as_riff()
					assert file_chunk
					srsf.write(file_chunk)
					if len(file_chunk) % 2 == 1:
						srsf.write("\0")
						
					for track in tracks.values():
						if big_file:
							track.flags |= TrackData.BIG_FILE
						track_chunk = track.serialize_as_riff()
						srsf.write(track_chunk)
						if len(track_chunk) % 2 == 1:
							srsf.write("\0")
						
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

def mkv_create_srs(tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		er = EbmlReader(EbmlReadMode.MKV, sample)
		while(er.read()):
			e = er.current_element
			
			srsf.write(e.raw_header)
			
			if er.element_type ==  EbmlElementType.Segment:
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
				srsf.write(er.read_contents())
		er.close()

def mp4_create_srs(tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as movf:
		mr = MovReader(MovReadMode.MP4, sample)
		while(mr.read()):
			atom = mr.current_atom
			
			if atom.type == "mdat":
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
			
			if atom.type == "mdat":
				# don't copy stream data
				mr.skip_contents()
			else:
				# do copy everything else
				movf.write(mr.read_contents())
		mr.close()
			
def wmv_create_srs(tracks, sample_data, sample, srs, big_file):
	with open(srs, "wb") as srsf:
		ar = AsfReader(AsfReadMode.WMV, sample)
		while(ar.read()):
			o = ar.current_object
			
			srsf.write(o.raw_header)
			
			if o.type == GUID_DATA_OBJECT:
				i = 16 + 8 + 16
				(total_data_packets,) = S_LONGLONG.unpack(o.raw_header[i:i+8])
				# data packet/media object size
				psize = (o.size - len(o.raw_header)) / total_data_packets
				start = o.start_pos + len(o.raw_header)
				for i in range(total_data_packets):
					data = ar.read_data_part(start + i * psize, psize)
					
					packet = AsfDataPacket()
					packet.data = data
					packet.data_file_offset = start + i * psize
					packet.data_size = len(data) # psize
					
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
					"\x00" * sample_data.padding_amount):
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
		
def avi_find_sample_streams(tracks, main_avi_file):
	rr = RiffReader(RiffReadMode.AVI, main_avi_file)
	block_count = 0
	done = False
	
	while rr.read() and not done:
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else: # normal chunk
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
		if not tracks.has_key(track_number):
			tracks[track_number] = TrackData()
		track = tracks[track_number]
		track.track_number = track_number
		
		if (track.match_offset == 0 or 
			len(track.check_bytes) < len(track.signature_bytes)):
			# It's possible the sample didn't require or contain data
			# for all tracks in the main file. If that happens, 
			# we obviously don't want to try to match the data
			if track.signature_bytes != "":
				if (track.check_bytes != "" and 
				len(track.check_bytes) < len(track.signature_bytes)):
					lcb = min(len(track.signature_bytes),
								rr.current_chunk.length + 
								len(track.check_bytes))
					check_bytes = track.check_bytes
					check_bytes += rr.read_contents()[:lcb-
					                                  len(track.check_bytes)]
					
					# track found!
					if track.signature_bytes[:len(check_bytes)] == check_bytes:
						track.check_bytes = check_bytes
					else:
						# It was only a partial match. Start over.
						track.check_bytes = ""
						track.match_offset = 0
						track.match_length = 0
			
			# this is a bit weird, but if we had a false positive match
			# going and discovered it above, we check this frame again
			# to see if it's the start of a new match 
			# (probably will never happen with AVI, 
			# but it does in MKV, so just in case...)	
			if track.check_bytes == "":
				chunk_bytes = rr.read_contents()
				
				search_byte = track.signature_bytes[0]
				found_pos = chunk_bytes.find(search_byte, 0)
				
				while found_pos > -1:
					lcb = min(len(track.signature_bytes),
								len(chunk_bytes) - found_pos)
					check_bytes = chunk_bytes[found_pos:found_pos+lcb]
					
					# track found!
					if track.signature_bytes[:len(check_bytes)] == check_bytes:
						track.check_bytes = check_bytes
						track.match_offset = (rr.current_chunk.chunk_start_pos
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
	
def mkv_find_sample_streams(tracks, main_mkv_file):
	er = EbmlReader(EbmlReadMode.MKV, main_mkv_file)
	cluster_count = 0
	done = False
	
	while er.read() and not done:
		if er.element_type in (EbmlElementType.Segment, 
			                   EbmlElementType.BlockGroup):
			er.move_to_child()
		elif er.element_type == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while 
			# (cluster is good because they're about 1mb each)
			cluster_count += 1
			show_spinner(cluster_count)
			er.move_to_child()
		elif er.element_type == EbmlElementType.Block:
			tracks, done = _mkv_block_find(tracks, er, done)
		else:
			er.skip_contents()
	
	remove_spinner()
	
	er.close()
	return tracks	

def _mkv_block_find(tracks, er, done):
	# grab track or create new track
	track_number = er.current_element.track_number
	if not tracks.has_key(track_number):
		tracks[track_number] = TrackData()
		tracks[track_number].track_number = track_number
	track = tracks[track_number]
	
	# it's possible the sample didn't require 
	# or contain data for all tracks in the main file
	# if that happens, we obviously don't want to try to match the data
	if track.signature_bytes != "" and (track.match_offset == 0 or
		(len(track.check_bytes) < len(track.signature_bytes))):
		# here, the data we're looking for might not start in the first frame 
		# (lace) of the block, so we need to check them all
		buff = er.read_contents()
		offset = 0
		for i in range(len(er.current_element.frame_lengths)):
			# see if a false positive match was detected
			if track.check_bytes != "" and (len(track.check_bytes) < 
			                                len(track.signature_bytes)):
				lcb = min(len(track.signature_bytes), 
				          er.current_element.frame_lengths[i] + 
				          len(track.check_bytes))
				check_bytes = track.check_bytes
				check_bytes += buff[offset:offset+lcb-len(track.check_bytes)]
				
				if track.signature_bytes[:len(check_bytes)] == check_bytes:
					track.check_bytes = check_bytes
				else:
					# It was only a partial match. Start over.
					track.check_bytes = ""
					track.match_offset = 0
					track.match_length = 0
			# this is a bit weird, but if we had a false positive match going 
			# and discovered it above, we check this frame again
			# to see if it's the start of a new match 
			# (rare problem, but it can happen with subtitles especially)
			
			if track.check_bytes == "":
				lcb = min(len(track.signature_bytes), 
				              er.current_element.frame_lengths[i])
				check_bytes = buff[offset:offset+lcb] 
				
				if track.signature_bytes[:len(check_bytes)] == check_bytes:
					track.check_bytes = check_bytes
					track.match_offset = (er.current_element.element_start_pos
					                      + len(er.current_element.raw_header) 
					                      + len(er.current_element.raw_block_header) 
					                      + offset)
					track.match_length = min(track.data_length, 
					                         er.current_element.frame_lengths[i])
			else:
				track.match_length += min(track.data_length - 
				                          track.match_length,
				                          er.current_element.frame_lengths[i])
				
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
		
	return tracks, done

def mp4_find_sample_stream(track, mtrack, main_mp4_file):
	"""Check if the track from the sample exist in the main file. This is
	done based on the track signature alone, not the whole data stream."""
	mtrack = mp4_add_track_stream(mtrack)
	# open stream here so we open and close the mp4 file just once
	mtrack.trackstream.stream = open_main(main_mp4_file)
	
	data = mtrack.trackstream.read(len(track.signature_bytes))
#	print(data[:].encode('hex'))
#	print(mtrack.trackstream.current_offset())
#	print(track.signature_bytes[:].encode('hex'))
	if data == track.signature_bytes:
		track.match_offset = mtrack.trackstream.current_offset()
	next_chunk = True
	
	# walk through the stream one sample at the time
	while(data != track.signature_bytes and next_chunk):
		next_chunk = mtrack.trackstream.next()
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
		samples_in_chunk = track.chunk_lengths[chnb][1]
		chunk = TrackChunk(chunk_offset, samples_in_chunk, prev_chunk)
		# bidirectional links
		if prev_chunk:
			prev_chunk.next_chunk = chunk
		
		chunk.samples = track.sample_lengths[samples_amount:
		                                     samples_amount+samples_in_chunk]
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
		self._current_offset = 0 # chunk + sample offset
		self._current_chunk = None
		self._current_sample = 0 # of the current chunk
		
	def add_chunk(self, chunk):
		self.chunks.append(chunk)
		
	def current_offset(self):
		return self._current_offset
	
	def seek(self, offset):
		"""The offset must be the beginning of a sample."""
		self._current_offset = offset
		largest = 0
		for chunk in self.chunks:
			if chunk.chunk_offset > largest and chunk.chunk_offset <= offset:
				largest = chunk.chunk_offset
				self._current_chunk = chunk
		assert self._current_chunk
		self._current_sample = self._current_chunk.get_sample_nb(offset)
		
	def read(self, amount):
		"""amount: max amount to read"""
		if self._current_chunk == None: # bootstrap
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
				bytes_read = self.stream.read(min(amount-len(firstb), bl))
				firstb += bytes_read
			return firstb
	
	def next(self):
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
			if (self.chunk_offset + sample_sum >= offset and 
			self.chunk_offset <= offset):
				assert self.chunk_offset + sample_sum == offset
				return count
			count += 1
			sample_sum += sample
		return count

def mp4_find_sample_streams(tracks, main_mp4_file):
	mtracks = profile_mp4(FileData(file_name=main_mp4_file))
	
	# check for each movie track if it contains the sample data
	for mtrack in mtracks.values():
		try:
			track = tracks[mtrack.track_number]
			track = mp4_find_sample_stream(track, mtrack, main_mp4_file)
#			print(track)
#			print(mtrack)
			track.main_track = mtrack
			tracks[mtrack.track_number] = track
		except KeyError:
			# track in main file that is not in the sample file
			# do not search for match
			continue
	return tracks

def wmv_find_sample_streams(tracks, main_wmv_file):
	ar = AsfReader(AsfReadMode.WMV, main_wmv_file)
	done = False
	while ar.read() and not done:
		o = ar.current_object
		
		if o.type == GUID_DATA_OBJECT:
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack(o.raw_header[i:i+8])
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) / total_data_packets
			start = o.start_pos + len(o.raw_header)
			for i in range(total_data_packets):
				if i % 15 == 0:
					show_spinner(i)
				data = ar.read_data_part(start + i * psize, psize)
				
				packet = AsfDataPacket()
				packet.data = data
				packet.data_file_offset = start + i * psize
				packet.data_size = len(data) # psize
				
				asf_data_get_packet(packet, psize, AsfReadMode.WMV)
				
				prev_payloads_size = 0
				for payload in packet.payloads:
					# grab track or create new track
					track_number = payload.stream_number
					if not tracks.has_key(track_number):
						tracks[track_number] = TrackData()
					track = tracks[track_number]
					track.track_number = track_number
					
					if (track.match_offset == 0 or 
						len(track.check_bytes) < len(track.signature_bytes)):
						# It's possible the sample didn't require or contain data
						# for all tracks in the main file. If that happens, 
						# we obviously don't want to try to match the data
						if track.signature_bytes != "":
							if (track.check_bytes != "" and 
							    len(track.check_bytes) 
							    < len(track.signature_bytes)):
								lcb = min(len(track.signature_bytes),
											payload.data_length + 
											len(track.check_bytes))
								check_bytes = track.check_bytes
								check_bytes += payload.data[:lcb-
								                        len(track.check_bytes)]
								
								# track found!
								if (track.signature_bytes[:len(check_bytes)] 
								    == check_bytes):
									track.check_bytes = check_bytes
								else:
									# It was only a partial match. Start over.
									track.check_bytes = ""
									track.match_offset = 0
									track.match_length = 0
						
						# this is a bit weird, but if we had a false positive match
						# going and discovered it above, we check this payload again
						# to see if it's the start of a new match 
						# (probably will never happen with AVI 
						# but it does in MKV, so just in case...)	
						if track.check_bytes == "":
							payload_bytes = payload.data
							
							search_byte = track.signature_bytes[0]
							found_pos = payload_bytes.find(search_byte, 0)
							
							while found_pos > -1:
								lcb = min(len(track.signature_bytes),
											len(payload_bytes) - found_pos)
								check_bytes = payload_bytes[found_pos:
								                          found_pos+lcb]
								
								# track found!
								if (track.signature_bytes[:len(check_bytes)] 
								    == check_bytes):
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


def avi_extract_sample_streams(tracks, movie):
	rr = RiffReader(RiffReadMode.AVI, movie)
	
	# TODO: never used start_offset?
	# search for first match offset
	start_offset = 2 ** 63 # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)
	
	block_count = 0
	done = False
	
	while rr.read() and not done:
		if rr.chunk_type == RiffChunkType.List:
			rr.move_to_child()
		else: # normal chunk
			tracks, block_count, done = _avi_normal_chunk_extract(tracks, rr, 
			                                      block_count, done)
	remove_spinner()
	
	rr.close()
	return tracks, {} #attachments

def _avi_normal_chunk_extract(tracks, rr, block_count, done):
	if rr.chunk_type == RiffChunkType.Movi:
		block_count += 1
		show_spinner(block_count)
		
		# grab track or create new track
		track_number = rr.current_chunk.stream_number
		if not tracks.has_key(track_number):
			tracks[track_number] = TrackData()
			tracks[track_number].track_number = track_number
		track = tracks[track_number]
		
		if (rr.current_chunk.chunk_start_pos + 
		len(rr.current_chunk.raw_header) + 
		rr.current_chunk.length > track.match_offset):
			if track.track_file == None:
				track.track_file = tempfile.TemporaryFile()
				
			if track.track_file.tell() < track.data_length:
				if (rr.current_chunk.chunk_start_pos + 
				len(rr.current_chunk.raw_header) >= track.match_offset):
					track.track_file.write(
					    rr.read_contents()[:rr.current_chunk.length])
				else:
					chunk_offset = (track.match_offset - 
					                (rr.current_chunk.chunk_start_pos + 
					                len(rr.current_chunk.raw_header)))
					track.track_file.write(rr.read_contents()[chunk_offset:
					                       rr.current_chunk.length])
	
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

def mkv_extract_sample_streams(tracks, movie):
	er = EbmlReader(EbmlReadMode.MKV, movie)
	
	# search for first offset so we can skip unnecessary clusters later on
	start_offset = 2 ** 63 # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)
			
	attachments = {}
	current_attachment = None
	cluster_count = 0
	done = False
	while er.read() and not done:
		if er.element_type in (EbmlElementType.Segment, 
		                       EbmlElementType.AttachmentList,
		                       EbmlElementType.Attachment,
		                       EbmlElementType.BlockGroup):
			er.move_to_child()
		elif er.element_type == EbmlElementType.Cluster:
			# simple progress indicator since this can take a while 
			# (cluster is good because they're about 1mb each)
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
		elif er.element_type == EbmlElementType.AttachedFileName:
			current_attachment = er.read_contents()
			if not attachments.has_key(current_attachment):
				att = AttachmentData(current_attachment)
				attachments[current_attachment] = att
		elif er.element_type == EbmlElementType.AttachedFileData:
			attachement = attachments[current_attachment]
			attachement.size = er.current_element.length
			
			# in extract mode, 
			# extract all attachments in case we need them later
			if attachement.attachement_file == None:
				attachement.attachement_file = tempfile.TemporaryFile()
				attachement.attachement_file.write(er.read_contents())
				attachement.attachement_file.seek(0)
		elif er.element_type == EbmlElementType.Block:
			tracks, done = _mkv_block_extract(tracks, er, done)
		else:
			er.skip_contents()

	remove_spinner()
	
	er.close()
	return tracks, attachments

def _mkv_block_extract(tracks, er, done):
	track = tracks[er.current_element.track_number]
	
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
				track.track_file.write(buff[offset:offset+
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
		
	return tracks, done

def mp4_extract_sample_streams(tracks, main_mp4_file):
	mtracks = profile_mp4(FileData(file_name=main_mp4_file))
	
	for track_nb, track in tracks.items():
		mtrack = mtracks[track_nb]
		track = mp4_extract_sample_stream(track, mtrack, main_mp4_file)
		tracks[track_nb] = track
		
	return tracks, {} # attachments

def open_main(big_file):
	if utility.is_rar(big_file):
		return rarstream.RarStream(big_file)
	else:
		return open(big_file, "rb")
		
def mp4_extract_sample_stream(track, mtrack, main_mp4_file):
	track.track_file = tempfile.TemporaryFile()
	mtrack = mp4_add_track_stream(mtrack)
	mtrack.trackstream.stream = open_main(main_mp4_file)
		
	mtrack.trackstream.seek(track.match_offset)
	track.track_file.write(mtrack.trackstream.read(track.data_length))
	
	mtrack.trackstream.stream.close()
	return track

def wmv_extract_sample_streams(tracks, main_wmv_file):
	ar = AsfReader(AsfReadMode.Sample, main_wmv_file)
	
	# search for first match offset
	start_offset = 2 ** 63 # long.MaxValue + 1
	for track in tracks.values():
		if track.match_offset > 0:
			start_offset = min(track.match_offset, start_offset)
			
	done = False
	while ar.read() and not done:
		o = ar.current_object
		oguid = ar.object_guid
		
		if oguid == GUID_DATA_OBJECT:
			i = 16 + 8 + 16
			(total_data_packets,) = S_LONGLONG.unpack(o.raw_header[i:i+8])
			# data packet/media object size
			psize = (o.size - len(o.raw_header)) / total_data_packets
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
				packet.data_size = len(data) # psize
				
				tmp = asf_data_get_packet(packet, psize)
				assert tmp == packet.length == psize
				
				prev_payloads_size = 0
				for payload in packet.payloads:
					# grab track or create new track
					track_number = payload.stream_number
					if not tracks.has_key(track_number):
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
	
	return tracks, {} #attachments
	
	
def avi_rebuild_sample(srs_data, tracks, attachments, srs, out_folder):
	crc = 0 # Crc32.StartValue
	rr = RiffReader(RiffReadMode.SRS, path=srs)
	
	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)
	
	sample_file = os.path.join(out_folder, srs_data.name)
	with open(sample_file, "wb") as sample:
		block_count = 0
		while rr.read():
			# skip over our custom chunks in rebuild mode 
			# (only read it in load mode)
			if (rr.current_chunk.fourcc == "SRSF" or 
			    rr.current_chunk.fourcc == "SRST"):
				rr.skip_contents()
				continue
			
			sample.write(rr.current_chunk.raw_header)
			crc = crc32(rr.current_chunk.raw_header, crc) & 0xFFFFFFFF
			
			if rr.chunk_type == RiffChunkType.List:
				rr.move_to_child()
			else: # normal chunk
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
	
	ofile = FileData(file_name=sample_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	
	if ofile.crc32 != srs_data.crc32:
		#TODO: try again with the correct interleaving for LOL samples
		pass
	
	rr.close()
	return ofile

def mkv_rebuild_sample(srs_data, tracks, attachments, srs, out_folder):
	crc = 0 # Crc32.StartValue
	er = EbmlReader(RiffReadMode.SRS, path=srs)
	
	for track in tracks.values():
		#TODO: track_file can not be initialized here
		track.track_file.seek(0)
	
	sample_file = os.path.join(out_folder, srs_data.name)
	with open(sample_file, "wb") as sample:
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
				buff = attachment.attachement_file.read()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF
				if srs_data.flags & FileData.ATTACHEMENTS_REMOVED != 0:
					er.move_to_child() # really means do nothing in this case
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
				er.move_to_child() # really means do nothing in this case
			else:
				# anything not caught above is considered metadata, 
				# so we copy it as is
				buff = er.read_contents()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFFF
				
	er.close()
	remove_spinner()	
	
	ofile = FileData(file_name=sample_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def mp4_rebuild_sample(srs_data, tracks, attachments, srs, out_folder):
	crc = 0 # Crc32.StartValue
	
	tracks = profile_mp4_srs(srs, tracks)
	for track in tracks.values():
		track.track_file.seek(0)
		track = mp4_add_track_stream(track) # for the sorting later on
	
	mr = MovReader(MovReadMode.SRS, path=srs)
	
	sample_file = os.path.join(out_folder, srs_data.name)
	with open(sample_file, "wb") as sample:
		while mr.read():
			# we don't want the SRS elements copied into the new sample.
			if mr.atom_type in ("SRSF", "SRST"):
				mr.skip_contents()
				continue
			
			sample.write(mr.current_atom.raw_header)
			crc = crc32(mr.current_atom.raw_header, crc) & 0xFFFFFFFF
			
			if mr.atom_type == "mdat":
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
	
	ofile = FileData(file_name=sample_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

def order_chunks(tracks):
	all_chunks = []
	for track in tracks.values():
		for chunk in track.trackstream.chunks:
			all_chunks.append((chunk, track.track_number))
		
	all_chunks = sorted(all_chunks, key=lambda c: c[0].chunk_offset)
	return all_chunks
	
def profile_mp4_srs(srs, tracks): #XXX: copy paste edit from other function
	"""Reads the necessary track header data 
	and adds this info to the tracks"""
	current_track = None
	track_processed = False
	mr = MovReader(MovReadMode.SRS, srs)
	while mr.read():
		atype = mr.atom_type
		
		# doing body
		if atype in ("moov", "trak", "mdia", "minf", "stbl"):
			mr.move_to_child()
		elif atype == "mdat":
			mr.move_to_child()
		else:
			data = mr.read_contents()
		
		if atype in ("tkhd",):
			# grab track id 
			(track_id,) = BE_LONG.unpack(data[12:16])
			current_track = tracks[track_id]
			
			# initialization
			current_track.chunk_offsets = []
			current_track.chunk_lengths = []
			current_track.sample_lengths = []
			track_processed = False
		elif atype in ("stco", "co64"):
			# exactly one variant must be present
			assert current_track != None
			(entry_count,) = BE_LONG.unpack(data[4:8])
			if atype == "stco":
				size = 4
				structunp = BE_LONG
			else: # "co64"
				size = 8
				structunp = BE_LONGLONG
			for i in range(entry_count):
				j = 8 + i * size
				(offset,) = structunp.unpack(data[j:j+size])
				current_track.chunk_offsets.append(offset)	
		elif atype == "stsc": # Sample To Chunk Box
			(entry_count,) = BE_LONG.unpack(data[4:8])
			for i in range(entry_count):
				j = 8 + i * 12
				# first_chunk
				# samples_per_chunk
				# sample_description_index
				result_tuple = struct.unpack(">LLL", data[j:j+12])
				current_track.chunk_lengths.append(result_tuple)
				
			# enlarge compactly coded tables
			current_track.chunk_lengths = stsc(current_track.chunk_lengths)
		elif atype in ("stsz", "stz2"): # Sample Size Boxes
			(sample_size,) = BE_LONG.unpack(data[4:8])
			(sample_count,) = BE_LONG.unpack(data[8:12])
			if sample_size == 0:
				for i in range(sample_count):
					j = 12 + i * 4
					(out,) = BE_LONG.unpack(data[j:j+4])
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

def wmv_rebuild_sample(srs_data, tracks, attachments, srs, out_folder):
	crc = 0 # Crc32.StartValue
	ar = AsfReader(AsfReadMode.SRS, path=srs)
	padding_index = 0
	
	# set cursor for temp files back at the beginning
	for track in tracks.values():
		track.track_file.seek(0)
	
	sample_file = os.path.join(out_folder, srs_data.name)
	with open(sample_file, "wb") as sample:
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
				(total_data_packets,) = S_LONGLONG.unpack(o.raw_header[i:i+8])
				# data packet/media object size
				psize = (o.osize - len(o.raw_header)) / total_data_packets
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
						          padding_index+packet.padding_length]
						sample.write(data)
						crc = crc32(data, crc) & 0xFFFFFFFF
						padding_index += packet.padding_length
					except AttributeError:
						data = "\x00" * packet.padding_length
						sample.write(data)
						crc = crc32(data, crc) & 0xFFFFFFFF
			
				ar.skip_contents()	
			else:
				buff = ar.read_contents()
				sample.write(buff)
				crc = crc32(buff, crc) & 0xFFFFFFF
	ar.close()
	remove_spinner()	
	
	ofile = FileData(file_name=sample_file)
	ofile.crc32 = crc & 0xFFFFFFFF
	return ofile

if __name__ == "__main__":
	unittest.main()