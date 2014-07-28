#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 pyReScene
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

# http://mp3val.sourceforge.net/
# http://phwip.wordpress.com/home/audio/
# http://wiki.hydrogenaudio.org/index.php?title=APE_Tags_Header

import os
import struct

from rescene.utility import is_rar
from rescene.rarstream import RarStream
from functools import reduce

def decode_id3_size(sbytes):
	# "This size is encoded using 28 bits rather than a multiple of 8,
	# such as 32 bits, because an ID3 tag can't contain the byte #xff
	# followed by a byte with the top 3 bits on because that pattern
	# has a special meaning to MP3 decoders. None of the other fields
	# in the ID3 header could possibly contain such a byte sequence,
	# but if you encoded the tag size as a regular unsigned-integer,
	# it might. To avoid that possibility, the size is encoded using
	# only the bottom seven bits of each byte, with the top bit always
	# zero."
	return reduce(lambda x, y: x*128 + y,
	              (ord(sbytes[i:i + 1]) for i in range(4)))
	
def encode_id3_size(size):
	result = bytearray(4)
	# adds groups of last 7 bytes to the result
	for i in range(4):
		byte = (size >> (i*7)) & 0x7F
		result[-1 - i] = byte
	return result

S_LONG = struct.Struct('<L') # unsigned long: 4 bytes
BE_SHORT = struct.Struct('>H')
BE_LONG = struct.Struct('>L') # unsigned long: 4 bytes

class InvalidDataException(ValueError):
	pass
	
class Block(object):
	def __init__(self, size, block_type, start_pos):
		self.size = size
		self.type = block_type
		self.start_pos = start_pos
	
	def __repr__(self, *args, **kwargs):
		return "<Block type=%s size=%d start_pos=%d>" % (self.type, 
		                                self.size, self.start_pos)
		
class Mp3Reader(object):
	"""Implements a simple Reader class that reads through MP3 
	or MP3-SRS files one block at a time."""
	def __init__(self, path=None, stream=None):
		assert path or stream
		if path:
			if is_rar(path):
				self._mp3_stream = RarStream(path)
			else:
				self._mp3_stream = open(path, 'rb')
		elif stream:
			self._mp3_stream = stream
		self._mp3_stream.seek(0, 2)
		self._file_length = self._mp3_stream.tell()
		self._mp3_stream.seek(0)

		self.current_block = None
		
		self.blocks = []
		begin_main_content = 0
		
		# easier for corner case ("ID3" multiple times before sync)
		id3v2_block = None
		
		# parse the whole file immediately!
		# 1) check for ID3v2 (beginning of mp3 file)
		#The ID3v2 tag size is the size of the complete tag after
		#unsychronisation, including padding, excluding the header but not
		#excluding the extended header (total tag size - 10). Only 28 bits
		#(representing up to 256MB) are used in the size description to avoid
		#the introduction of 'false syncsignals'.
		# http://id3.org/id3v2.4.0-structure
		first = self._mp3_stream.read(3)
		if first == b"ID3":
			# skip ID3v2 version (2 bytes) and flags (1 byte)
			self._mp3_stream.seek(3, os.SEEK_CUR)
			sbytes = self._mp3_stream.read(4)
			size = decode_id3_size(sbytes)
			
			begin_main_content = size + 10 # 3 + 3 + 4
			id3v2_block = Block(begin_main_content, "ID3", 0)
			self.blocks.append(id3v2_block)
			
		# 2) check for ID3v1 (last 128 bytes of mp3 file)
		end_meta_data_offset = self._file_length
		self._mp3_stream.seek(-128, os.SEEK_END)
		idv1_start_offset = self._mp3_stream.tell()
		first = self._mp3_stream.read(3)
		if first == b"TAG":
			idv1_block = Block(128, "TAG", idv1_start_offset)
			self.blocks.append(idv1_block)
			end_meta_data_offset = idv1_start_offset
			
		# 3) check for http://id3.org/Lyrics3v2
		# "The Lyrics3 block, after the MP3 audio and before the ID3 tag, 
		# begins with the word "LYRICSBEGIN" after which a number of field 
		# records follows. The Lyrics3 block ends with a six character size 
		# descriptor and the string "LYRICS200". The size value includes the 
		# "LYRICSBEGIN" string, but does not include the 6 character size 
		# descriptor and the trailing "LYRICS200" string.
		if end_meta_data_offset - 6 - 9 >= 0:
			self._mp3_stream.seek(end_meta_data_offset - 6 - 9, os.SEEK_SET)
			lyrics_footer = self._mp3_stream.read(6 + 9)
			if lyrics_footer[6:] == b"LYRICS200":
				lyrics_size = int(lyrics_footer[:6]) # only header + body
				lyrics3v2_block = Block(lyrics_size + 6 + 9, "LYRICS200",
				                        end_meta_data_offset -
				                        (lyrics_size + 6 + 9))
				self.blocks.append(lyrics3v2_block)
				end_meta_data_offset -= (lyrics_size + 6 + 9)
		
		# 4) check for http://id3.org/Lyrics3
		if end_meta_data_offset - 9 >= 0:
			self._mp3_stream.seek(end_meta_data_offset - 9, os.SEEK_SET)
			if b"LYRICSEND" == self._mp3_stream.read(9):
				self._mp3_stream.seek(end_meta_data_offset - 5100, os.SEEK_SET)
				lyrics_data = self._mp3_stream.read(5100)
				index = lyrics_data.find(b"LYRICSBEGIN")
				if index == -1:
					raise InvalidDataException(
							"Unable to find start of LyricsV1 block")
				start_block = end_meta_data_offset - 5100 + index
				lyrics3_block = Block(end_meta_data_offset - start_block,
				                      "LYRICS", start_block)
				self.blocks.append(lyrics3_block)
				end_meta_data_offset -= lyrics3_block.size
			
		# 5) APE tags
		# "Tag size in bytes including footer and all tag items excluding 
		# the header to be as compatible as possible with APE Tags 1.000"
		# "An APEv1 tag at the end of a file must have at least a footer, APEv1 
		# tags may never be used at the beginning of a file 
		# (unlike APEv2 tags)."
		if end_meta_data_offset - 32 >= 0:
			self._mp3_stream.seek(end_meta_data_offset - 32, os.SEEK_SET)
			if b"APETAGEX" == self._mp3_stream.read(8):
				(version,) = S_LONG.unpack(self._mp3_stream.read(4))
				if version == 2000:
					header = 32
				else: # 1000
					header = 0
				(size,) = S_LONG.unpack(self._mp3_stream.read(4))
				start_block = end_meta_data_offset - size - header
				apev2_block = Block(end_meta_data_offset - start_block,
				                    "APE%s" % version, start_block)
				self.blocks.append(apev2_block)
				end_meta_data_offset -= apev2_block.size
		
		def marker_has_issues(marker):
			if len(marker) != 4:
				return True
			(sync,) = BE_SHORT.unpack(marker[:2])
			if (sync & 0xFFE0 != 0xFFE0 and 
			    marker not in (b"RIFF", b"SRSF")):
				return True
					
		# in between is SRS or MP3 data
		self._mp3_stream.seek(begin_main_content, os.SEEK_SET)
		marker = self._mp3_stream.read(4)

		if id3v2_block and marker_has_issues(marker):
			# problem with (angelmoon)-hes_all_i_want_cd_pg2k-bmi
			# The .mp3 files contain ID3+nfo before the real ID3 starts
			# And it's also a RIFF mp3, so it won't play without removing
			# the bad initial tag first.
			# This can cause the space between the "ID3" and the end tag
			# to be empty. (or just wrong)
			# This does not handle repeating of ID3v2 tags.
			# Mickey_K.-Distracted-(DNR019F8)-WEB-2008-B2R has the 'ID3' string
			# in the ID3v2 tag for 02-mickey_k.-distracted_-_dub_mix.mp3
			last_id3 = last_id3v2_before_sync(self._mp3_stream,
			                                  self._file_length)
			if last_id3 != 0: # dupe ID3 string
				self._mp3_stream.seek(last_id3 + 3 + 3, os.SEEK_SET)
				sbytes = self._mp3_stream.read(4)
				size = decode_id3_size(sbytes)
				
				begin_main_content = last_id3 + 10 + size # 3 + 3 + 4
				id3v2_block.size = begin_main_content
		
		self._mp3_stream.seek(begin_main_content, os.SEEK_SET)
		marker = self._mp3_stream.read(4)
		
		if not len(marker):
			# there still is something horribly wrong
			# (unless you think that an mp3 without any music data is possible)
			raise InvalidDataException("Tagging fucked up big time!")
		
		(sync,) = BE_SHORT.unpack(marker[:2])
		main_size = end_meta_data_offset - begin_main_content
		if marker[:3] == b"SRS": # SRS data blocks
			cur_pos = begin_main_content
			while(cur_pos < begin_main_content + main_size):
				self._mp3_stream.seek(cur_pos, os.SEEK_SET)
				# SRSF, SRST and SRSP
				try:
					marker = self._mp3_stream.read(4)
					# size includes the 8 bytes header
					(size,) = S_LONG.unpack(self._mp3_stream.read(4))
				except:
					raise InvalidDataException("Not enough SRS data")
				srs_block = Block(size, marker.decode(),
					cur_pos)
				self.blocks.append(srs_block)
				cur_pos += size
				if size == 0:
					raise InvalidDataException("SRS size field is zero")
				if size > begin_main_content + main_size:
					raise InvalidDataException("Broken SRS")
		elif sync & 0xFFE0 == 0xFFE0 or marker == b"RIFF":
			# first 11 bits all 1 for MP3 frame marker
			mp3_data_block = Block(main_size, "MP3", begin_main_content)
			self.blocks.append(mp3_data_block)
		else:
			print("WARNING: MP3 file is not valid!")
			data_block = Block(main_size, "MP3", begin_main_content)
			self.blocks.append(data_block)
						
		# the order of which we add blocks doesn't matter this way
		self.blocks.sort(key=lambda block: block.start_pos)
			
	def read(self):
		for block in self.blocks:
			self.current_block = block
			#print(block)
			yield block
	
	def read_contents(self):
		self._mp3_stream.seek(self.current_block.start_pos, os.SEEK_SET)
		return self._mp3_stream.read(self.current_block.size)

	def read_part(self, size, offset=0):
		if (self.current_block.start_pos + offset + size >
			self.current_block.start_pos + self.current_block.size):
			raise ValueError("Can't read beyond end of block.")
		self._mp3_stream.seek(self.current_block.start_pos + offset, os.SEEK_SET)
		return self._mp3_stream.read(size)
		
	def close(self):
		try: # close the file/stream
			self._mp3_stream.close()
		except:
			pass	
		
	def __del__(self):
		try: # close the file/stream
			self._mp3_stream.close()
		except:
			pass
			
def last_id3v2_before_sync(stream, length):
	"""Return the index of the last ID3v2 marker found before any
	mp3 sync bytes or RIFF container.
	The stream is assumed to contain an "ID3" marker.
	length: the maximum length of the stream to search"""
	last_good_id3 = 0
	current = 0
	id3 = 0
	
	# loop will probably run only once before encountering the sync bytes
	while current < length:
		stream.seek(current, os.SEEK_SET)
		bytespart = stream.read(0x10000 + 3) # +3 for border cases
		
		# search for first frame marker
		sync = -1
		c = bytespart.find(b"\xFF", 0)
		while -1 < c < (0x10000 + 3):
			match = bytespart[c:c+2]
			if (len(match) == 2 and # last byte could match
				BE_SHORT.unpack(match)[0] & 0xFFE0 == 0xFFE0):
				sync = c
				break
			else:
				c += 1 # prevent infinite loop
			c = bytespart.find(b"\xFF", c)
		riff = bytespart.find(b"RIFF")
		if sync != -1 or riff != -1:
			sync = max(sync, riff)
			
		imatch = bytespart.rfind(b"ID3")
		if imatch > 0:
			imatch += current
		id3 = max(imatch, id3)
		if id3 > last_good_id3 and sync != -1 and id3 < current + sync:
			last_good_id3 = id3
			
		if sync != -1:
			return last_good_id3
		
		current += 0x10000 # 64KiB batches
	
	# when no frame marker is found
	return last_good_id3
