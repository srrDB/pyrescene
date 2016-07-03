#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""Certain releases posted to Usenet have been modified to avoid detection
and prevent against DMCA takedown notices. They have no release name
associated with the post and the hash won't match the original release.
After renaming and rescening the file, you will end up with a RAR that fails
the SFV check.

This script tries to fix these mkv files.

* The Info element must have the Title removed
* SeekHead order is changed: reference to the Info block is last in the list.
* EbmlVoid must come before the Info element

On a FLEET release: TODO

* The Info segment is after the Tracks in the raped file
* Void before Tracks has to be removed (replace by smaller Info segment)
* Larger void again between Tracks and Cluster

Tools used:

* EBML Viewer 2.0 (Java)
* mkvinfo GUI (included in mkvtoolnix)

Author: Gfy"""

import optparse
import sys
import time
import shutil
from os.path import join, dirname, basename, realpath, exists

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

try:
	import resample
except ImportError:
	print("Could not find the resample project code.")
	sys.exit(1)

class ToFixData():
	start_seekhead = 0
	start_info_element = 0
	start_void_element = 0
	seekhead_data = b""
	info_element_data = b""
	void_element_data = b""
	seeks = []
	header_seekhead = b""
	header_info = b""
	header_void = b""
	title_skip_data = b""
	
	def __str__(self, *args, **kwargs):
		return ("<seekhead=%d, info=%d>" % 
			(self.start_seekhead, self.start_info_element))

class Seek():
	def __init__(self, header):
		self.raw_header = header
	id = b""
	position = 0
	header_id = b""
	header_position = b""
	
def get_data(mkv):
	data = ToFixData()
	
	def got_data():
		return data.seekhead_data and data.info_element_data and not removing_title
	
	current_seek = None
	removing_title = False
	er = resample.EbmlReader(resample.EbmlReadMode.MKV, path=mkv)
	while er.read(): # and not got_data():
		e = er.current_element
		
		if er.element_type == resample.EbmlElementType.Segment:
			er.move_to_child()
		elif er.element_type == resample.EbmlElementType.SeekHead:
			data.start_seekhead = e.element_start_pos
			data.header_seekhead = e.raw_header
			data.seekhead_data = er.read_contents()
			print("Seek head", len(data.header_seekhead), len(data.seekhead_data))
			er.move_to_child()

		elif er.element_type == resample.EbmlElementType.Seek:
			print("Seek")
			current_seek = Seek(e.raw_header)
			data.seeks.append(current_seek)
			er.move_to_child()
		elif er.element_type == resample.EbmlElementType.SeekID:
			current_seek.id = er.read_contents()
			current_seek.header_id = e.raw_header
		elif er.element_type == resample.EbmlElementType.SeekPosition:
			current_seek.position = er.read_contents()
			current_seek.header_position = e.raw_header
			
		elif er.element_type == resample.EbmlElementType.Void:
			data.start_void_element = e.element_start_pos
			data.void_element_data = er.read_contents()
			data.header_void = e.raw_header
			print("Void", len(data.header_void), len(data.void_element_data))
			er.skip_contents()
			
		elif er.element_type == resample.EbmlElementType.SegmentInfo:
			data.start_info_element = e.element_start_pos
			data.header_info = e.raw_header
			# info_element_data will get skipped
			print("Segment info", len(data.header_info), len(er.read_contents()))
			er.move_to_child()
			removing_title = e.element_start_pos + e.length
		elif er.element_type == resample.EbmlElementType.Title:
			# removing title data for the fix here!
			removing_title = False
			data.title_skip_data = e.raw_header + er.read_contents()
			
		elif er.element_type == resample.EbmlElementType.TrackList:
			break
		elif er.element_type == resample.EbmlElementType.Cluster:
			break
		else:
			if removing_title:
# 				# break when there is no title and nothing wrong
# 				if removing_title <= e.element_start_pos:
# 					break
				data.info_element_data += e.raw_header
				data.info_element_data += er.read_contents()
			else:
				er.skip_contents()

		print(e)
# 	print(data)	
# 	print(data.seeks)
	er.close()
	return data

def check_fixable(data):
	last_seek = data.seeks[-1]
	return last_seek.id == resample.EbmlID.SEGMENT_INFO
		
def fix_usenet(mkv, data):
	orig_size_seekhead = len(data.header_seekhead) + len(data.seekhead_data)
	orig_size_info = (len(data.header_info) + len(data.info_element_data) + 
		len(data.title_skip_data))
	orig_size_void = len(data.header_void) + len(data.void_element_data)
	total = orig_size_seekhead + orig_size_info + orig_size_void
	print("orig seekhead", orig_size_seekhead)
	print("orig size info", orig_size_info)
	print("orig size void", orig_size_void)
	print("orig total", total)
	
	# info segment
	info_segment = resample.EbmlID.SEGMENT_INFO
	info_segment += resample.MakeEbmlUInt(len(data.info_element_data))
	info_segment += data.info_element_data
	total_info = len(info_segment)
	
	# seek head
	seek_head_data = b""
	order = sorted(data.seeks, key=lambda x: x.position, reverse=True)
	for seek in order:
		if seek.id == resample.EbmlID.SEGMENT_INFO:
			# fix size for title removal
			# before Tracks
			offset_before_next = total - total_info
			print("new offset", offset_before_next)
			
			# assuming 2 bytes
			infoloc = resample.BE_SHORT.pack(offset_before_next)
			
			edited_seek = (seek.header_id + seek.id + 
				resample.EbmlID.SEEK_POSITION +
				resample.MakeEbmlUInt(len(infoloc)) + infoloc)
			
			seek_head_data += resample.EbmlID.SEEK 
			seek_head_data += resample.MakeEbmlUInt(len(edited_seek))
			seek_head_data += edited_seek
		else:
			# no modification
			seek_head_data += seek.raw_header 
			seek_head_data += seek.header_id + seek.id
			seek_head_data += seek.header_position + seek.position
	seek_head_data = (resample.EbmlID.SEEK_HEAD + 
		resample.MakeEbmlUInt(len(seek_head_data)) + seek_head_data)	
	total_seekhead = len(seek_head_data)
	
	# void: left over space (assuming the size is always 2)
	total_void = total - total_info - total_seekhead
	void_header = resample.EbmlID.VOID + resample.MakeEbmlUInt(total_void - 3)
	void_segment_data = void_header + b"\x00" * (total_void - 3)
	
	fixed_data = seek_head_data + void_segment_data + info_segment
	overwrite_from = data.start_seekhead
	
	return overwrite_from, fixed_data

def main(options, args):
	mkv = realpath(args[0])
	if not exists(mkv):
		print("MKV file does not exist:")
		print(mkv)
		sys.exit(1)
		
	data = get_data(mkv)
	possible_to_fix = check_fixable(data)
	
	if possible_to_fix:
		print("Attempting to fix!")
		(overwrite_from, fixed_data) = fix_usenet(mkv, data)
		
# 		# copy files to test on
# 		goodr = "file.mkv"
# 		good = join(dirname(mkv), "good.mkv")
# 		out = join(dirname(mkv), "testing.mkv")
# 		with open(goodr, "rb") as goodf:
# 			good_data = goodf.read(5000)
# 			with open(good, "wb") as tocopy:
# 				tocopy.write(good_data)
# 			with open(out, "wb") as tocopy:
# 				tocopy.write(good_data)

		print("Copying file:")
		print(mkv)
		out = join(dirname(mkv), "fixed_" + basename(mkv))
		shutil.copyfile(mkv, out)
		print(out)
			
		# do the actual fixing
		with open(out, "r+b") as fix:
			fix.seek(overwrite_from)
			fix.write(fixed_data)
		print("Maybe it's fixed!")
		print("If not, it's a FLEET release or some custom muxer?")
	else:
		print("Not possible to fix")
	
	print(mkv)
	
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog file_name.mkv\n"
		"This tool tries to fix raped mkv files.\n",
		version="%prog 0.1 (2016-07-03)")  # --help, --version

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		start_time = time.time()
		(options, args) = parser.parse_args()
		main(options, args)
		print("--- %.3f seconds ---" % (time.time() - start_time))
