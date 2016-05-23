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

import optparse
import sys
import tempfile
import os
from os.path import join, dirname, basename

try:
	import _preamble
except ImportError:
	pass

from rescene.main import info, extract_files
from resample.main import file_type_info, sample_class_factory, FileType
from rescene.utility import empty_folder

def main(options, args):
	if not options.txt and not options.verify:
		print("Add the parameter -t or -s.")

	tempdir = tempfile.mkdtemp(prefix="pyReScene-srs_bad-")
	for dirpath, dirnames, filenames in os.walk(args[0]):
		dirnames.sort()
		for sfile in filenames:
			if sfile[-4:].lower() == ".srr":
				srrf = os.path.join(dirpath, sfile)
				handle_srr(srrf, options, tempdir)
	os.rmdir(tempdir)

def handle_srr(srr_file, options, temporary_directory):
	srrinfo = info(srr_file)
	extracting_needed = False
	printout = set()

	# check txt files/check if extraction is needed
	for stored_file in srrinfo["stored_files"].keys():
		if stored_file.endswith(".srs") and options.verify:
			extracting_needed = True
		elif (stored_file.endswith(".txt") and stored_file[:-4].endswith((
			".mp3", ".flac", ".mkv", ".mp4", ".avi", ".wmv"))) and options.txt:
			printout.add(stored_file)

	if extracting_needed:
		extract_files(srr_file, temporary_directory, extract_paths=False)
		for value in srrinfo["stored_files"].values():
			fn = basename(value.file_name)
			if fn.endswith(".srs"):
				srsf = join(temporary_directory, fn)
				ft = file_type_info(srsf).file_type
				if ft not in [FileType.MP3, FileType.FLAC]:
					sample = sample_class_factory(ft)
					_srs_data, tracks = sample.load_srs(srsf)
					for track in tracks.values():
						if track.match_offset == 0:
							printout.add(fn)

		# clean out temp dir
		empty_folder(temporary_directory)

	if len(printout):
		if options.simple:
			print(basename(srr_file)[:-4])
		elif options.path:
			print(dirname(srr_file))
		else:
			print(srr_file)
			for srs in sorted(printout):
				print("-> %s" % srs)

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog directory options'\n"
		"This tool will list SRR files with 'sample' issues.\n"
		"It works recursively and will write many temporary files on disk.",
		version="%prog 0.1 (2013-12-02)")  # --help, --version
	# 0.1 (2013-12-02)

	parser.add_option("-s", dest="verify", action="store_true",
					help="not verified against main movie file and not music")
	parser.add_option("-t", dest="txt", action="store_true",
					help="sample or music txt files are included")
	parser.add_option("-l", dest="simple", action="store_true",
					help="list only the release names")
	parser.add_option("-p", dest="path", action="store_true",
					help="list only the release paths")

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
