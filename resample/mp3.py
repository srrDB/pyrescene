#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013 pyReScene
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
		
		# parse the whole file immediately!
		# 1) check for ID3v2 (beginning of mp3 file)
		#The ID3v2 tag size is the size of the complete tag after
		#unsychronisation, including padding, excluding the header but not
		#excluding the extended header (total tag size - 10). Only 28 bits
		#(representing up to 256MB) are used in the size description to avoid
		#the introduction of 'false syncsignals'.
		first = self._mp3_stream.read(3)
		if first == b"ID3":
			self._mp3_stream.seek(3, os.SEEK_CUR)
			sbytes = self._mp3_stream.read(4)
			size = decode_id3_size(sbytes)
			
			begin_main_content = size + 10
			idv2_block = Block(begin_main_content, "ID3", 0)
			self.blocks.append(idv2_block)
			
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
		self._mp3_stream.seek(end_meta_data_offset - 6 - 9, os.SEEK_SET)
		lyrics_footer = self._mp3_stream.read(6 + 9)
		if lyrics_footer[6:] == b"LYRICS200":
			lyrics_size = int(lyrics_footer[:6]) # only header + body
			lyrics3v2_block = Block(lyrics_size + 6 + 9, "LYRICS200",
			                     end_meta_data_offset - (lyrics_size + 6 + 9))
			self.blocks.append(lyrics3v2_block)
			end_meta_data_offset -= (lyrics_size + 6 + 9)
		
		# 4) check for http://id3.org/Lyrics3
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
			
		# in between is SRS or MP3 data
		self._mp3_stream.seek(begin_main_content, os.SEEK_SET)
		(sync,) = BE_SHORT.unpack(self._mp3_stream.read(2))
		main_size = end_meta_data_offset - begin_main_content
		if sync & 0xFFE0 == 0xFFE0:
			mp3_data_block = Block(main_size, "MP3", begin_main_content)
			self.blocks.append(mp3_data_block)
		else: # SRS data blocks
			cur_pos = begin_main_content
			while(cur_pos < begin_main_content + main_size):
				self._mp3_stream.seek(cur_pos, os.SEEK_SET)
				# SRSF, SRST and SRSP
				try:
					marker = self._mp3_stream.read(4)
					# size includes the 8 bytes header
					if marker == b"fLaC": # FLAC with ID3 tags
						size = end_meta_data_offset - cur_pos
					else:
						(size,) = S_LONG.unpack(self._mp3_stream.read(4))
				except:
					raise InvalidDataException("Not enough SRS data")
				srs_block = Block(size, marker.decode(),
					cur_pos)
				self.blocks.append(srs_block)
				cur_pos += size
				if size == 0:
					raise InvalidDataException("SRS size field is zero")
			
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
			