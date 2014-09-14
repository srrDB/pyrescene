#!/usr/bin/env python
# encoding: utf-8

# Copyright (c) 2014 pyReScene
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

"""
This tool fixes the tags of music files.

To do:
	- error handling
	- issue with capitals on *nix
	- path support (now path info gets ignored)
	- testing
	- rescene.extract_files does not ask/overwrites files -> implement method
"""

from optparse import OptionParser
import sys
import os

try:
	import _preamble
except ImportError:
	pass

import rescene
from resample.srs import main as srsmain
from resample.main import get_file_type, sample_class_factory

def fix_tags(srr_file, input_dir, output_dir, always_yes=False):
	if not srr_file.endswith(".srr"):
		raise AttributeError("The first parameter must be an SRR file.")
	if not os.path.isdir(input_dir):
		raise AttributeError("The input location must be a directory.")
	if not os.path.isdir(output_dir):
		try:
			os.makedirs(output_dir)
		except:
			pass
		if not os.path.isdir(output_dir):
			raise AttributeError("Could not create output location.")
	
	stored_files = rescene.info(srr_file)['stored_files']
	
	# extract files
	srs_files = []
	for sfile in stored_files.keys():
		if sfile.endswith(".srs"):
			srs_files.append(sfile)
		else:
			print("Extracting %s" % sfile)
			rescene.extract_files(srr_file, output_dir, False, sfile)
	
	for srs in srs_files:
		print("Extracting %s" % srs)
		rescene.extract_files(srr_file, output_dir, False, srs)
		
	# fix music files that can be found
	successes = 0
	failures = 0
	for srs in srs_files:
		srsf = os.path.join(output_dir, os.path.basename(srs))
		srs_info = get_srs_info(srsf)
		original_name = srs_info.sample_name
		print("Fixing %s" % original_name)
		# TODO: will fail on *nix when capitals differ
		musicf = os.path.join(input_dir, original_name)
		
		srs_parameters = [srsf, musicf, "-o", output_dir]
		if always_yes:
			srs_parameters.append("-y")
		try:
			srsmain(srs_parameters, no_exit=True)
			successes += 1
		except ValueError: # pexit() only throws ValueError
			failures += 1
		
		os.remove(srsf)
		
	print("\n\n%d/%d files succeeded. %d failures." % 
		(successes, failures + successes, failures))
		
def get_srs_info(srs_file):
	# TODO: get_file_type can be unknown
	sample = sample_class_factory(get_file_type(srs_file))
	srs_data, _tracks = sample.load_srs(srs_file)
	return srs_data

def main(argv=None):
	parser = OptionParser(
	usage=("Usage: %prog srr-file -i input_dir -o output_dir\n"
	"This tool fixes the tags of music files.\n"
	"Example usage: %prog rls.srr --output D:\\rls\\"), 
	version="%prog " + rescene.__version__) # --help, --version
	
	parser.add_option("-i", "--input", dest="input_dir", metavar="DIR",
					default=".", help="Specifies input directory. "
					"The default input path is the current directory.")
	parser.add_option("-o", "--output", dest="output_dir", metavar="DIR",
					default=".", help="Specifies output directory. "
					"The default output path is the current directory.")
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					action="store_true",
					help="assume Yes for all prompts")
	
	if argv is None:
		argv = sys.argv[1:]
		
	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return 0
	
	(options, args) = parser.parse_args(args=argv)
	
	# no SRR file provided
	if not len(args):
		parser.print_help()
		return 1
	
	if fix_tags(args[0], options.input_dir, options.output_dir, 
	            options.always_yes):
		return 0
	else:
		return 1

if __name__ == "__main__":
	sys.exit(main())
	