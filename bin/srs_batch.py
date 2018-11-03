#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2015 pyReScene
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

import os
import sys
import optparse

try:
	import _preamble
except ImportError:
	pass

from resample.srs import main as srsmain

def main(options):
	if not options.input_dir or not options.output_dir:
		print("Input and output parameters are required.")
		exit(1)

	indir = os.path.normpath(os.path.abspath(options.input_dir))
	outdir = os.path.normpath(os.path.abspath(options.output_dir))
	print("Input: {0}".format(indir))
	print("Output: {0}".format(outdir))

	for dirpath, _dirnames, filenames in os.walk(indir):
		subdirs = os.path.relpath(dirpath, indir)
		for pfile in filenames:
			if pfile.lower().endswith(
					(".avi", ".mkv", ".wmv", ".mp4", ".vob", ".m2ts")):
				create_srs(dirpath, pfile, outdir, subdirs)

def create_srs(sample_dir, sample_file, output_dir, path):
	print(sample_dir)
	dest_dir = os.path.join(output_dir, path)
	sample = os.path.join(sample_dir, sample_file)

	if not os.path.isdir(dest_dir):
		os.makedirs(dest_dir)

	original_stderr = sys.stderr
	txt_error_file = os.path.join(dest_dir, sample_file) + ".txt"
	sys.stderr = open(txt_error_file, "wt")
	keep_txt = False
	try:
		srsmain([sample, "-y", "-o", dest_dir], True)
	except ValueError:
		keep_txt = True

	sys.stderr.close()
	if not keep_txt:
		os.unlink(txt_error_file)

	sys.stderr = original_stderr

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog -i input_directory -o output_directory\n"
		"This tool creates .srs or .txt files for video files"
		" found in the input directory.\nOverwrites existing files.",
		version="%prog 1.2 (2018-11-03)")  # --help, --version

	parser.add_option("-i", dest="input_dir", metavar="DIRECTORY",
					help="folder with release folders")
	parser.add_option("-o", dest="output_dir", metavar="DIRECTORY",
					help="places the .srs files in this directory")

	# no arguments given
	if len(sys.argv) == 1:
		print(parser.format_help())
	else:
		(options, _args) = parser.parse_args()
		main(options)
