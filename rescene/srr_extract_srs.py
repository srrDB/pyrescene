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
import os
from os.path import join, dirname, realpath

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

import rescene

def main(options, args):
	if len(args) < 2:
		raise AttributeError("Not enough parameters.")
	srr = args[0]
	output_folder = args[1]
	
	if not srr.endswith(".srr"):
		raise AttributeError("The first parameter must be an SRR file.")
	if not os.path.isdir(output_folder):
		raise AttributeError("The second attribute must be a directory.")
	
	srs_files = []
	for sfile in rescene.info(srr)["stored_files"].keys():
		if sfile.endswith(".srs"):
			srs_files.append(sfile)
	
	for srs in srs_files:
		print(srs)
		rescene.extract_files(srr, output_folder, 
		                      extract_paths=True, packed_name=srs)
			
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog file.srr output_directory'\n"
		"This tool will extract only .srs files from an SRR file.",
		version="%prog 1.0 (2013-11-21)") # --help, --version

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)