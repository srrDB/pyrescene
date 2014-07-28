#!/usr/bin/python -OO
# -*- coding: latin-1 -*-

# Copyright 2008-2011 The SABnzbd-Team <team@sabnzbd.org>
# Copyright 2011 pyReScene
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

# http://www.yenc.org/yenc-draft.1.3.txt

from zlib import crc32

import logging # http://docs.python.org/library/logging.html
import re
import sys

try: # check for the compiled C library
	import _yenc
	HAVE_YENC = True
	print("Using FAST yEnc implementation.")
except ImportError:
	HAVE_YENC = False
	print("Using SLOW yEnc implementation.")
	
# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behaviour
	range = xrange #@ReservedAssignment

#------------------------------------------------------------------------------

class CrcError(Exception):
	def __init__(self, needcrc, gotcrc, data):
		Exception.__init__(self)
		self.needcrc = needcrc
		self.gotcrc = gotcrc
		self.data = data

class YencException(Exception):
	def __init__(self, *args, **kwargs):
		Exception.__init__(self, *args, **kwargs)

#------------------------------------------------------------------------------

YDEC_TRANS = bytearray(range(256 - 42, 256)) + bytearray(range(256 - 42))

def decode(data, seg_part=False, ignore_crc=False):
	data = strip(data)
	# No point in continuing if we don't have any data left
	if data:
		yenc, data = yCheck(data)
		ybegin, ypart, yend = yenc
		decoded_data = None
		
		#Deal with non-yencoded posts
		if not ybegin:
			print("Non yEnc encoded data found!")
			found = False
			for i in range(10):
				if data[i].startswith(b'begin '):
					found = True
					break
			if found:
				for _ in range(i):
					data.pop(0)
			if data[-1] == b'end':
				data.pop()
				if data[-1] == b'`':
					data.pop()

			decoded_data = b'\r\n'.join(data)

		#Deal with yenc encoded posts
		elif ybegin and (yend or (not yend and seg_part)):
			if not b'name' in ybegin:
				logging.debug("Possible corrupt header detected "
							  "=> ybegin: %s", ybegin)
			# Decode data
			if HAVE_YENC:
				decoded_data, crc = _yenc.decode_string(b''.join(data))[:2] #@UndefinedVariable
				partcrc = (crc ^ -1) & 0xFFFFFFFF
			else:
				data = b''.join(data)
				for i in (0, 9, 10, 13, 27, 32, 46, 61):
					j = b'=' + bytearray((i + 64,))
					i = bytearray((i,))
					data = data.replace(j, i)
				decoded_data = data.translate(YDEC_TRANS)
				if not seg_part:
					crc = crc32(decoded_data)
					partcrc = crc & 0xFFFFFFFF

			# we don't need to check all the CRC stuff if it isn't there
			if not seg_part and not ignore_crc:
				if ypart:
					crcname = b'pcrc32'
				else:
					crcname = b'crc32'

				try:
					_partcrc = int(yend[crcname], 16)
				except (LookupError, ValueError):
					_partcrc = None
					logging.debug("Corrupt header detected "
								  "=> yend: %s", yend)
	
				if not (_partcrc == partcrc):
					raise CrcError(_partcrc, partcrc, decoded_data)
		else:
			#print(yenc)
			# ({'total': '15', 'line': '128', 'part': '15', 
			#   'name': 'mdj.104-diff.r00', 'size': '15000000'}, 
			#  {'begin': '14000001', 'end': '15000000'}, 
			#  None)
			raise YencException("No =yend: segment data is not all there")
		
		# '=ypart begin=400001 end=500000' line can be omitted
		if not ypart: # fill it in ourselves
			ypart = {b'begin': 1, b'end': ybegin[b'size']}
			# in this case are 2 =ybegin parameters 'missing' too:
			# =ybegin line=128 size=3566 name=k-9-vrs.sfv
			# part= and total= (but these are optional according to the spec)
			ybegin.setdefault(b'part', 1)
		
		#print(ybegin, ypart, yend)
		# ({'line': '128', 'part': '1', 'name': 
		# 'Fringe S01E07 X264 720p 2Audio (2009-12-06).nfo', 'size': '3554'}, 
		# {'begin': '1', 'end': '3554'}, 
		# {'part': '1', 'pcrc32': '13fca903', 'size': '3554'})

		return {
			'data': decoded_data,
			# KeyError: 'part'
			'part_number': int(ybegin[b'part']),
			'part_begin': int(ypart[b'begin']), # in the the joined file
			'part_end': int(ypart[b'end']), # counts from 1 onwards
			'part_size': int(ypart[b'end']) - int(ypart[b'begin']) + 1,
			'file_size': int(ybegin[b'size']),
		}

def yCheck(data):
	ybegin = None
	ypart = None
	yend = None
	
	## Check head
	for i in range(10):
		try:
			if data[i].startswith(b'=ybegin '):
				splits = 3
				if data[i].find(b' part=') > 0:
					splits += 1
				if data[i].find(b' total=') > 0:
					splits += 1

				ybegin = ySplit(data[i], splits)

				if data[i+1].startswith(b'=ypart '):
					ypart = ySplit(data[i+1])
					data = data[i+2:]
					break
				else:
					data = data[i+1:]
					break
		except IndexError:
			break

	## Check tail
	for i in range(-1, -11, -1):
		try:
			if data[i].startswith(b'=yend '):
				yend = ySplit(data[i])
				data = data[:i]
				break
		except IndexError:
			break
	
	return ((ybegin, ypart, yend), data)

# Example: =ybegin part=1 line=128 size=123 name=-=DUMMY=- abc.par
YSPLIT_RE = re.compile(br'([a-zA-Z0-9]+)=')

def ySplit(line, splits = None):
	fields = {}

	if splits:
		parts = YSPLIT_RE.split(line, splits)[1:]
	else:
		parts = YSPLIT_RE.split(line)[1:]

	if len(parts) % 2:
		return fields

	for i in range(0, len(parts), 2):
		key, value = parts[i], parts[i+1]
		fields[key] = value.strip()

	return fields

def strip(data):
	while data and not data[0]:
		data.pop(0)

	while data and not data[-1]:
		data.pop()

	# http://www.yenc.org/develop.htm
	# the NNTP-protocol requires to double a dot in the first colum 
	# when a line is sent - and to detect a double dot (and remove one of them)
	# when receiving a line.
	for i in range(len(data)):
		if data[i].startswith(b'..'):
			data[i] = data[i][1:]
	return data

"""
It shows which yEnc version you are using by running this code directly.

The _yenc C module: _yenc.so (
  * yenc-fred: fastest version for posting
    http://www.file-upload.net/download-3645696/PosterPack_07_08_2011.rar.html
    
  * yenc-vanilla 0.3: We have to do the . quoting for posting ourselves. 
    This is about 50% slower.

Pure Python code:
  * python-psyco: speeds up part encoding 25-30% (only Python 2.6)
  * python-vanilla: slowest
"""
if __name__ == '__main__':
	try:
		import _yenc
		
		if ('Freddie' in _yenc.__doc__): #@UndefinedVariable
			print("Using Freddie's version (fastest).")
		else: # https://bitbucket.org/dual75/yenc
			print("C module for yEnc encoding and decoding.")
	except ImportError:
		print("Pure Python yEnc encoding and decoding.")
		try:
			import psyco #@UnusedImport
		except ImportError:
			print("No Psyco available: 25-30% slower.")
