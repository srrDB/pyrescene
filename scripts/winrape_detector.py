#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 pyReScene
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

""" MediaInfo shows this line in its output:

Xtra                                     : WM/MediaClassPrimaryID

Problem:
It is wmpnetwk.exe (Windows Media Player Network Sharing Service) writing
and corrupting the files. It adds 2 "tags" to the UDTA box in the file.
https://social.technet.microsoft.com/Forums/lync/en-US/74adc717-7778-45d6-a779-573eaab9cd30/mp4-file-corruption
https://social.technet.microsoft.com/Forums/windows/en-US/74adc717-7778-45d6-a779-573eaab9cd30/mp4-file-corruption?forum=w7itpromedia
https://social.technet.microsoft.com/Forums/en-US/74adc717-7778-45d6-a779-573eaab9cd30/mp4-file-corruption?forum=w7itpromedia
https://superuser.com/questions/1331832/mp4-files-unplayable-after-renaming-or-copy-pasting

Avoid the problem alltogether by using TeraCopy!
https://www.codesector.com/teracopy

NO solutions yet to completely undo the rape!

https://www.softpedia.com/get/Multimedia/Video/Other-VIDEO-Tools/MP4XtraAtomRemover.shtml
https://superuser.com/questions/862421/windows-media-player-streaming-doesnt-open-all-video-files-on-tv
-> tested mp4 file not playable anymore

http://atomicparsley.sourceforge.net/
AtomicParsley.exe file.mp4 --manualAtomRemove "udta" --freefree 1
-> removes the trailing free atom while it keeps the newly created 'free' atom in its place
   It fails to remove the free space itself.

https://gpac.wp.imt.fr/
https://github.com/gpac/gpac/issues/560
mp4box.exe file.mp4 -dump-udta Xtra
[iso file] Unknown box type Xtra
-> Shows what's being added: WM/EncodingTime,
   WM/MediaClassSecondaryID, WM/MediaClassPrimaryID

mp4box.exe file.mp4 -udta 0:type=meta
mp4box.exe file.mp4 -udta 0:type=Xtra
-> removes atoms in udta, but container still left in

I wrote a C# script that removes the WMP tags from the MP4 files, 
making them playable again: http://pastebin.com/VJgi20vP
You can either compile as an exe or run it with cscs.exe. -- Mnerec
-> DeleteWMPTagsFromMP4.cs cleaned sample does not play anymore
"""

import os
import sys
import optparse
from os.path import join, dirname, realpath

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

from rescene.utility import FileType
from resample import file_type_info
from resample.mov import MovReader, MovReadMode, InvalidDataException

def is_raped_mp4(mp4file):
	raped = False
	mr = MovReader(MovReadMode.Sample, mp4file)
	while mr.read():
		if mr.atom_type == b"moov":
			mr.move_to_child()
		if mr.atom_type == b"udta":
			mr.move_to_child()
		if mr.atom_type == b"Xtra":
			raped = True
			break
		else:
			mr.skip_contents()
	mr.close()
	return raped
	
def main(_options, args):
	folder = args[0]
	print("Checking folder: %s" % folder)
	for dirpath, _dirnames, filenames in os.walk(folder):
		for filename in filenames:
			f = join(dirpath, filename)
			try:
				if filename.endswith('.mp4') and is_raped_mp4(f):
					print("RAPED: %s" % f)
			except InvalidDataException:
				ftype_info = file_type_info(f)
				if ftype_info.file_type == FileType.MP4:
					# Note: this does not detect all broken mp4 files,
					# just those with very bad corruption
					print("BROKEN: %s" % f)
				else:
					# file with the wrong extension
					print("MISMATCH: %s is of type %s" % (
						f, ftype_info.file_type))
			except Exception as ex:
				print("Unexpected error occured!")
				print(ex)

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog FOLDER\n"
		"This tool will test MP4 files for Windows rape.\n",
		version="%prog 1.0 (2018-12-09)")  # --help, --version

	# no argument given
	if len(sys.argv) < 1:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)